"""Certificado Verde mensual en PDF.

Salida agregada, calculada al vuelo. No se persiste la emisión.

Cifras, y de dónde salen:
- Kilos: ``linea_pesaje`` de pesajes en estado ``confirmado`` (no borrador, no anulado),
  con ``fecha_medicion`` dentro del mes local y ``torre_origen_id`` de una torre del conjunto.
- Tipo de aprovechamiento: gremio del material, clasificado con ``tipo_servicio``
  (``RECICLABLES`` = kilos aprovechados, ``ORGANICOS`` = kilos compostados).
- Tasa de rechazo por peso: kilos rechazados / kilos pesados de esas mismas líneas.
- Hogares: la misma regla que el resumen (recogida cerrada o entrega directa con pesaje confirmado).
- Torres: torres del conjunto con al menos un pesaje confirmado en el mes.

Un sync pendiente no entra: el pesaje sigue en borrador hasta que se confirma.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from fpdf import FPDF
from sqlalchemy import distinct, false, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errores import invalido
from app.core.tipos import ahora, zona
from app.models import Conjunto, Gremio, LineaPesaje, Material, Pesaje, TipoServicio, Torre
from app.modulos.comun import obtener

FORMULA = "certificado_verde_v1"
_MES = re.compile(r"(?P<anio>[0-9]{4})-(?P<mes>0[1-9]|1[0-2])")
_MESES = (
    "",
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
_TIPO_RECICLABLES = "reciclables"
_TIPO_ORGANICOS = "organicos"
_TIPO_OTRO = "otro"
_ETIQUETA_TIPO = {
    _TIPO_RECICLABLES: "reciclables",
    _TIPO_ORGANICOS: "orgánicos",
    _TIPO_OTRO: "otro",
}


@dataclass
class _GremioCifra:
    codigo: str
    nombre: str
    tipo: str
    kg_aceptados: Decimal = Decimal(0)
    kg_rechazados: Decimal = Decimal(0)


@dataclass
class _MaterialCifra:
    codigo: str
    nombre: str
    gremio_codigo: str
    kg_aceptados: Decimal
    kg_rechazados: Decimal


@dataclass
class _Cifras:
    conjunto_nombre: str
    conjunto_id: uuid.UUID
    mes: str
    etiqueta_mes: str
    desde: datetime
    hasta: datetime
    zona: str
    corte: datetime
    kg_aprovechados: Decimal
    kg_compostados: Decimal
    kg_otros: Decimal
    kg_aceptados: Decimal
    kg_rechazados: Decimal
    tasa_pct: str
    tasa_ratio: str
    hogares: int
    torres: int
    sin_pesajes: bool
    gremios: list[_GremioCifra] = field(default_factory=list)
    materiales: list[_MaterialCifra] = field(default_factory=list)


def periodo_mes(mes: str) -> tuple[datetime, datetime, str]:
    """Mes calendario ``AAAA-MM`` en la zona de la API. ``hasta`` es exclusivo."""
    encontrado = _MES.fullmatch((mes or "").strip())
    if encontrado is None:
        raise invalido({"mes": "Usa el formato AAAA-MM, por ejemplo 2026-11"})
    anio = int(encontrado.group("anio"))
    mes_n = int(encontrado.group("mes"))
    tz = zona(get_settings().zona_horaria)
    try:
        desde = datetime(anio, mes_n, 1, tzinfo=tz)
        if mes_n == 12:
            hasta = datetime(anio + 1, 1, 1, tzinfo=tz)
        else:
            hasta = datetime(anio, mes_n + 1, 1, tzinfo=tz)
    except ValueError:
        raise invalido({"mes": "Usa el formato AAAA-MM, por ejemplo 2026-11"}) from None
    return desde, hasta, f"{_MESES[mes_n]} de {anio}"


def slug_conjunto(nombre: str, conjunto_id: uuid.UUID) -> str:
    base = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower()[:60]
    return base or conjunto_id.hex[:12]


def _fmt_kg(valor: Decimal) -> str:
    return f"{Decimal(valor).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP):.3f}"


def _tasa(aceptados: Decimal, rechazados: Decimal) -> tuple[str, str]:
    total = aceptados + rechazados
    if total == 0:
        return "0 %", "0.0000"
    ratio = (rechazados / total).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    pct = (ratio * Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{pct} %", f"{ratio:.4f}"


def _texto(valor: str) -> str:
    """Helvetica solo cubre Latin-1. Un emoji de catálogo no puede romper el PDF."""
    return valor.encode("latin-1", errors="replace").decode("latin-1")


def _clasificar(codigos: set[str]) -> str:
    organico = "ORGANICOS" in codigos
    reciclable = "RECICLABLES" in codigos
    if organico and not reciclable:
        return _TIPO_ORGANICOS
    if reciclable and not organico:
        return _TIPO_RECICLABLES
    return _TIPO_OTRO


def _tipos_por_gremio(db: Session) -> dict[uuid.UUID, str]:
    mapa: dict[uuid.UUID, set[str]] = {}
    for gremio_id, codigo in db.execute(select(TipoServicio.gremio_id, TipoServicio.codigo)):
        mapa.setdefault(gremio_id, set()).add(codigo)
    return {gremio_id: _clasificar(codigos) for gremio_id, codigos in mapa.items()}


def _hogares(db: Session, desde: datetime, hasta: datetime, torre_ids: list[uuid.UUID]) -> int:
    if not torre_ids:
        return 0
    # Misma cohorte que GET /reportes/resumen: no se duplica la consulta en este módulo.
    from app.modulos.reportes import _hogares_participantes

    hogares = _hogares_participantes(db, desde, hasta, torre_ids, None)
    return int(db.execute(select(func.count(distinct(hogares.c.unidad_id)))).scalar_one())


def _cifras(db: Session, conjunto_id: uuid.UUID, mes: str) -> _Cifras:
    desde, hasta, etiqueta = periodo_mes(mes)
    conjunto = obtener(db, Conjunto, conjunto_id, "conjunto")
    torre_ids = list(db.execute(select(Torre.id).where(Torre.conjunto_id == conjunto_id)).scalars())
    filtros = [
        Pesaje.estado == "confirmado",
        Pesaje.fecha_medicion >= desde,
        Pesaje.fecha_medicion < hasta,
        Pesaje.torre_origen_id.in_(torre_ids) if torre_ids else false(),
    ]
    filas = db.execute(
        select(
            Gremio.id,
            Gremio.codigo,
            Gremio.nombre,
            Material.codigo,
            Material.nombre,
            func.sum(LineaPesaje.kg_aceptados),
            func.sum(LineaPesaje.kg_rechazados),
        )
        .select_from(LineaPesaje)
        .join(Pesaje, Pesaje.id == LineaPesaje.pesaje_id)
        .join(Material, Material.id == LineaPesaje.material_id)
        .join(Gremio, Gremio.id == Material.gremio_id)
        .where(*filtros)
        .group_by(Gremio.id, Gremio.codigo, Gremio.nombre, Material.id, Material.codigo, Material.nombre)
        .order_by(Gremio.nombre, Material.nombre)
    ).all()
    tipos = _tipos_por_gremio(db)
    gremios: dict[str, _GremioCifra] = {}
    materiales: list[_MaterialCifra] = []
    for gremio_id, g_codigo, g_nombre, m_codigo, m_nombre, kg_a, kg_r in filas:
        aceptados = Decimal(kg_a or 0)
        rechazados = Decimal(kg_r or 0)
        cifra = gremios.get(g_codigo)
        if cifra is None:
            cifra = _GremioCifra(codigo=g_codigo, nombre=g_nombre, tipo=tipos.get(gremio_id, _TIPO_OTRO))
            gremios[g_codigo] = cifra
        cifra.kg_aceptados += aceptados
        cifra.kg_rechazados += rechazados
        materiales.append(
            _MaterialCifra(
                codigo=m_codigo,
                nombre=m_nombre,
                gremio_codigo=g_codigo,
                kg_aceptados=aceptados,
                kg_rechazados=rechazados,
            )
        )
    aprovechados = compostados = otros = aceptados_total = rechazados_total = Decimal(0)
    for cifra in gremios.values():
        aceptados_total += cifra.kg_aceptados
        rechazados_total += cifra.kg_rechazados
        if cifra.tipo == _TIPO_RECICLABLES:
            aprovechados += cifra.kg_aceptados
        elif cifra.tipo == _TIPO_ORGANICOS:
            compostados += cifra.kg_aceptados
        else:
            otros += cifra.kg_aceptados
    tasa_pct, tasa_ratio = _tasa(aceptados_total, rechazados_total)
    torres = 0
    if torre_ids:
        torres = int(
            db.execute(select(func.count(distinct(Pesaje.torre_origen_id))).where(*filtros)).scalar_one()
        )
    return _Cifras(
        conjunto_nombre=conjunto.nombre,
        conjunto_id=conjunto.id,
        mes=mes.strip(),
        etiqueta_mes=etiqueta,
        desde=desde,
        hasta=hasta,
        zona=get_settings().zona_horaria,
        corte=ahora(),
        kg_aprovechados=aprovechados,
        kg_compostados=compostados,
        kg_otros=otros,
        kg_aceptados=aceptados_total,
        kg_rechazados=rechazados_total,
        tasa_pct=tasa_pct,
        tasa_ratio=tasa_ratio,
        hogares=_hogares(db, desde, hasta, torre_ids),
        torres=torres,
        sin_pesajes=not filas,
        gremios=list(gremios.values()),
        materiales=materiales,
    )


class _PDF(FPDF):
    def footer(self) -> None:
        self.set_y(-16)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(70, 70, 70)
        self.cell(
            0,
            4,
            _texto("No sustituye el aforo de la empresa de aseo."),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.cell(0, 4, _texto(f"Brota · fórmula {FORMULA}"), align="C")


def _linea(
    pdf: FPDF, texto: str, size: int = 11, estilo: str = "", alto: float = 6, relleno: bool = False
) -> None:
    limpio = _texto(texto)
    for tamano in range(size, 7, -1):
        pdf.set_font("Helvetica", estilo, tamano)
        if pdf.get_string_width(limpio) <= pdf.epw:
            pdf.cell(0, alto, limpio, fill=relleno, new_x="LMARGIN", new_y="NEXT")
            return
    pdf.set_font("Helvetica", estilo, 8)
    pdf.multi_cell(0, 4, limpio, fill=relleno)


def render_pdf(cifras: _Cifras) -> bytes:
    pdf = _PDF(format="A4", unit="mm")
    pdf.set_compression(False)
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.set_title(f"Certificado Verde {cifras.mes}")
    pdf.set_author("Brota")
    pdf.set_creator("Brota")
    pdf.add_page()

    pdf.set_fill_color(27, 94, 32)
    pdf.rect(0, 0, 210, 28, style="F")
    pdf.set_y(8)
    pdf.set_text_color(255, 255, 255)
    _linea(pdf, "Certificado Verde", size=18, estilo="B", alto=8)
    _linea(pdf, "Informe mensual del conjunto", size=10, alto=5)
    pdf.set_y(34)
    pdf.set_text_color(33, 33, 33)

    _linea(pdf, f"Conjunto: {cifras.conjunto_nombre}", size=13, estilo="B", alto=7)
    _linea(pdf, f"Período: {cifras.etiqueta_mes} ({cifras.mes})", size=11)
    _linea(pdf, f"Desde {cifras.desde.isoformat()} hasta {cifras.hasta.isoformat()} (exclusivo).", size=9)
    _linea(pdf, f"Zona horaria: {cifras.zona}. Corte de datos: {cifras.corte.isoformat()}.", size=9)
    pdf.ln(2)

    _linea(pdf, f"Kilos aprovechados (reciclables): {_fmt_kg(cifras.kg_aprovechados)} kg", estilo="B")
    _linea(pdf, f"Kilos compostados (orgánicos): {_fmt_kg(cifras.kg_compostados)} kg", estilo="B")
    if cifras.kg_otros:
        _linea(pdf, f"Kilos aceptados de otro aprovechamiento: {_fmt_kg(cifras.kg_otros)} kg", estilo="B")
    _linea(pdf, f"Kilos aceptados en total: {_fmt_kg(cifras.kg_aceptados)} kg")
    _linea(pdf, f"Kilos rechazados: {_fmt_kg(cifras.kg_rechazados)} kg")
    _linea(pdf, f"Tasa de rechazo por peso: {cifras.tasa_pct} ({cifras.tasa_ratio} del total pesado)")
    _linea(pdf, f"Hogares participantes: {cifras.hogares}")
    _linea(pdf, f"Torres con pesaje confirmado: {cifras.torres}")
    pdf.ln(2)

    pdf.set_fill_color(255, 248, 225)
    pdf.set_text_color(90, 45, 0)
    _linea(
        pdf,
        "Este certificado es apoyo documental para la tarifa multiusuario.",
        size=10,
        estilo="B",
        relleno=True,
    )
    _linea(
        pdf,
        "No determina la tarifa ni sustituye el aforo de la empresa de aseo.",
        size=10,
        estilo="B",
        relleno=True,
    )
    pdf.set_text_color(33, 33, 33)
    pdf.ln(2)

    _linea(pdf, "Origen: pesajes confirmados con torre de origen de este conjunto.", size=9)
    _linea(pdf, "Los kilos salen de las líneas de esos pesajes, según el gremio del material.", size=9)
    _linea(pdf, "Reciclables: servicio RECICLABLES. Compostados: servicio ORGANICOS.", size=9)
    _linea(pdf, "Hogares: recogidas cerradas o entregas directas con pesaje confirmado.", size=9)
    _linea(pdf, "No entran borradores, pesajes anulados ni pendientes de sincronizar.", size=9)
    pdf.ln(2)

    _linea(pdf, "Detalle por gremio", size=12, estilo="B", alto=7)
    if cifras.sin_pesajes:
        _linea(pdf, "Sin pesajes confirmados en este período.", size=11)
        _linea(pdf, "Kilos en cero: 0.000 kg aprovechados, 0.000 kg compostados, 0.000 kg rechazados.", size=10)
    else:
        for gremio in cifras.gremios:
            _linea(
                pdf,
                f"{gremio.codigo} ({_ETIQUETA_TIPO[gremio.tipo]}): aceptados {_fmt_kg(gremio.kg_aceptados)} kg, "
                f"rechazados {_fmt_kg(gremio.kg_rechazados)} kg",
                size=10,
            )
            _linea(pdf, f"Gremio: {gremio.nombre}", size=9)
        pdf.ln(1)
        _linea(pdf, "Detalle por material", size=12, estilo="B", alto=7)
        for material in cifras.materiales:
            _linea(
                pdf,
                f"{material.codigo} ({material.gremio_codigo}): aceptados {_fmt_kg(material.kg_aceptados)} kg, "
                f"rechazados {_fmt_kg(material.kg_rechazados)} kg",
                size=10,
            )
            _linea(pdf, f"Material: {material.nombre}", size=9)

    pdf.ln(3)
    _linea(pdf, f"Identificador del conjunto: {cifras.conjunto_id}", size=8)
    raw = pdf.output()
    return raw.encode("latin-1") if isinstance(raw, str) else bytes(raw)


def generar_certificado(db: Session, conjunto_id: uuid.UUID, mes: str) -> tuple[bytes, str]:
    cifras = _cifras(db, conjunto_id, mes)
    nombre = f"certificado-verde-{slug_conjunto(cifras.conjunto_nombre, cifras.conjunto_id)}-{cifras.mes}.pdf"
    return render_pdf(cifras), nombre
