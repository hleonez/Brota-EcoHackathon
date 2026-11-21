"""Hoja de ruta del día, en PDF, para quien va a recoger.

Sale de órdenes en estado ``programada`` cuya asignación vigente empieza ese día
en la zona de la API (America/Bogota). No tiene tabla propia.

La usa la coordinación de ese gremio: lleva ubicación operativa y nombre de contacto.
No lleva el celular del residente; la bandeja tampoco se lo muestra. El teléfono del
recolector, si ya está en su ficha, va en el encabezado para que coordinación lo llame.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from fpdf import FPDF
from sqlalchemy import and_, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.core.errores import invalido, prohibido
from app.core.seguridad import Actor
from app.core.tipos import zona
from app.models import Asignacion, Gremio, Orden, Solicitud, SolicitudResiduo, TipoServicio
from app.modulos.comun import obtener

_FECHA = re.compile(r"(?P<anio>[0-9]{4})-(?P<mes>[0-9]{2})-(?P<dia>[0-9]{2})")
_SIN_PARADAS = "No hay paradas programadas para este día."


@dataclass
class _Parada:
    inicio: datetime
    fin: datetime | None
    ubicacion: str
    contacto: str | None
    servicios: list[str]
    materiales: list[str]


@dataclass
class _Grupo:
    nombre: str
    telefono: str | None
    paradas: list[_Parada] = field(default_factory=list)


def periodo_dia(fecha: str) -> tuple[datetime, datetime, str]:
    """Día ``AAAA-MM-DD`` en la zona de la API. ``hasta`` es exclusivo."""
    encontrado = _FECHA.fullmatch((fecha or "").strip())
    if encontrado is None:
        raise invalido({"fecha": "Usa el formato AAAA-MM-DD, por ejemplo 2026-11-20"})
    anio = int(encontrado.group("anio"))
    mes = int(encontrado.group("mes"))
    dia = int(encontrado.group("dia"))
    tz = zona(get_settings().zona_horaria)
    try:
        desde = datetime(anio, mes, dia, tzinfo=tz)
    except ValueError:
        raise invalido({"fecha": "Usa el formato AAAA-MM-DD, por ejemplo 2026-11-20"}) from None
    return desde, desde + timedelta(days=1), desde.date().isoformat()


def exigir_hoja(actor: Actor, gremio_id: uuid.UUID) -> None:
    """Coordinación de ese gremio, o administración (el resumen ya le deja ver todo)."""
    if actor.es_admin or gremio_id in actor.gremios_coordinados:
        return
    raise prohibido("La hoja de ruta la descarga la coordinación de ese gremio o la administración.")


def _texto(valor: str) -> str:
    return valor.encode("latin-1", errors="replace").decode("latin-1")


def _hora(dt: datetime) -> str:
    return dt.astimezone(zona(get_settings().zona_horaria)).strftime("%H:%M")


def _franja(parada: _Parada) -> str:
    if parada.fin is None:
        return _hora(parada.inicio)
    return f"{_hora(parada.inicio)}-{_hora(parada.fin)}"


def paradas_del_dia(db: Session, gremio_id: uuid.UUID, desde: datetime, hasta: datetime) -> list[_Grupo]:
    ordenes = db.execute(
        select(Orden)
        .join(Asignacion, and_(Asignacion.orden_id == Orden.id, Asignacion.vigente_hasta.is_(None)))
        .where(
            Orden.gremio_id == gremio_id,
            Orden.estado == "programada",
            Asignacion.inicio.is_not(None),
            Asignacion.inicio >= desde,
            Asignacion.inicio < hasta,
        )
        .options(
            selectinload(Orden.asignaciones).selectinload(Asignacion.recolector),
            selectinload(Orden.solicitud).selectinload(Solicitud.participante),
            selectinload(Orden.solicitud).selectinload(Solicitud.servicios),
            selectinload(Orden.solicitud).selectinload(Solicitud.residuos).selectinload(SolicitudResiduo.residuo),
        )
        .order_by(Asignacion.inicio, Orden.id)
    ).scalars().unique().all()
    tipo_ids = {
        servicio.tipo_servicio_id
        for orden in ordenes
        for servicio in orden.solicitud.servicios
        if servicio.orden_id == orden.id
    }
    nombres_tipo = (
        dict(db.execute(select(TipoServicio.id, TipoServicio.nombre).where(TipoServicio.id.in_(tipo_ids))).all())
        if tipo_ids
        else {}
    )
    grupos: dict[uuid.UUID, _Grupo] = {}
    for orden in ordenes:
        vigente = next((a for a in orden.asignaciones if a.vigente_hasta is None), None)
        if vigente is None or vigente.inicio is None or not (desde <= vigente.inicio < hasta):
            continue
        participante = orden.solicitud.participante
        contacto = participante.nombre if participante is not None and participante.estado != "eliminado" else None
        servicios = sorted(
            nombres_tipo[s.tipo_servicio_id]
            for s in orden.solicitud.servicios
            if s.orden_id == orden.id and s.tipo_servicio_id in nombres_tipo
        )
        materiales = sorted(sr.residuo.nombre for sr in orden.solicitud.residuos if sr.orden_id == orden.id)
        grupo = grupos.get(vigente.recolector_id)
        if grupo is None:
            grupo = _Grupo(nombre=vigente.recolector.nombre, telefono=vigente.recolector.telefono_contacto)
            grupos[vigente.recolector_id] = grupo
        grupo.paradas.append(
            _Parada(
                inicio=vigente.inicio,
                fin=vigente.fin,
                ubicacion=orden.solicitud.ubicacion_operativa,
                contacto=contacto,
                servicios=servicios,
                materiales=materiales,
            )
        )
    salida = sorted(grupos.values(), key=lambda g: (g.nombre.lower(), g.nombre))
    for grupo in salida:
        grupo.paradas.sort(key=lambda p: (p.inicio, p.ubicacion))
    return salida


def _linea(pdf: FPDF, texto: str, size: int = 11, estilo: str = "", alto: float = 6) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", estilo, size)
    pdf.multi_cell(0, alto, _texto(texto), new_x="LMARGIN", new_y="NEXT")


def render_pdf(gremio_nombre: str, dia: str, zona_nombre: str, grupos: list[_Grupo]) -> bytes:
    pdf = FPDF(format="A4", unit="mm")
    pdf.set_compression(False)
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_title(f"Hoja de ruta {dia}")
    pdf.set_author("Brota")
    pdf.set_creator("Brota")
    pdf.add_page()

    pdf.set_fill_color(27, 94, 32)
    pdf.rect(0, 0, 210, 28, style="F")
    pdf.set_y(8)
    pdf.set_text_color(255, 255, 255)
    _linea(pdf, "Hoja de ruta", size=18, estilo="B", alto=8)
    _linea(pdf, "Paradas programadas del día", size=10, alto=5)
    pdf.set_y(34)
    pdf.set_text_color(33, 33, 33)

    _linea(pdf, gremio_nombre, size=13, estilo="B", alto=7)
    _linea(pdf, f"Fecha: {dia}", size=11)
    _linea(pdf, f"Zona horaria: {zona_nombre}.", size=9)
    pdf.ln(2)

    if not grupos:
        _linea(pdf, _SIN_PARADAS, size=12, estilo="B")
    else:
        for grupo in grupos:
            _linea(pdf, f"Recolector: {grupo.nombre}", size=12, estilo="B", alto=7)
            if grupo.telefono:
                _linea(pdf, f"Tel. recolector: {grupo.telefono}", size=10)
            for i, parada in enumerate(grupo.paradas, start=1):
                _linea(pdf, f"{i}. {_franja(parada)}", size=11, estilo="B")
                _linea(pdf, f"Ubicación: {parada.ubicacion}", size=10)
                _linea(pdf, f"Contacto: {parada.contacto or 'Sin nombre'}", size=10)
                if parada.servicios:
                    _linea(pdf, "Servicio: " + ", ".join(parada.servicios), size=10)
                if parada.materiales:
                    _linea(pdf, "Materiales: " + ", ".join(parada.materiales), size=10)
            pdf.ln(1)

    raw = pdf.output()
    return raw.encode("latin-1") if isinstance(raw, str) else bytes(raw)


def generar_hoja_ruta(db: Session, actor: Actor, gremio_id: uuid.UUID, fecha: str) -> tuple[bytes, str]:
    desde, hasta, dia = periodo_dia(fecha)
    gremio = obtener(db, Gremio, gremio_id, "gremio")
    exigir_hoja(actor, gremio.id)
    grupos = paradas_del_dia(db, gremio.id, desde, hasta)
    nombre = f"hoja-ruta-{dia}.pdf"
    return render_pdf(gremio.nombre, dia, get_settings().zona_horaria, grupos), nombre
