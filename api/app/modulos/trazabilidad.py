"""Trazabilidad: el tablero (Kanban) de órdenes y la historia de cada una.

Solo lectura. La administración observa el recorrido completo (de la solicitud por WhatsApp al
cierre) de todos los gremios; cada coordinación ve solo las órdenes de su gremio (RN-01). Asignar,
programar y cerrar sigue en la bandeja de la coordinación. Nunca devuelve celulares: el contacto va
por nombre y los textos se limpian.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errores import invalido, no_encontrado, prohibido
from app.core.seguridad import Actor, actor_operador
from app.core.tipos import InstanteEntrada, _utc, ahora
from app.db import get_db
from app.models import (
    Asignacion,
    EventoDominio,
    EventoSalida,
    Gremio,
    MotivoRechazo,
    MovimientoPuntos,
    Orden,
    Participante,
    Pesaje,
    PesajeOrden,
    Recolector,
    Residuo,
    ResultadoOrden,
    Solicitud,
    SolicitudResiduo,
    SolicitudServicio,
    TipoServicio,
)
from app.modulos.eventos import _actor_nombre, _limpiar, _nombres_actores
from app.modulos.solicitudes import ABIERTAS

router = APIRouter(tags=["trazabilidad (administración)"])

ESTADOS = ("nueva", "asignada", "programada", "recogida", "rechazada", "cancelada")
DIAS_CERRADAS = 30
MAXIMO = 500


def _alcance(actor: Actor) -> set[uuid.UUID] | None:
    """None: todos los gremios (administración). Si no, los gremios que coordina."""
    if actor.es_admin:
        return None
    if actor.gremios_coordinados:
        return actor.gremios_coordinados
    raise prohibido("El recorrido de las solicitudes es para administración y coordinación.")


def _tarjetas(db: Session, ordenes: list[tuple[Orden, Solicitud]]) -> list[dict[str, Any]]:
    """Datos mínimos de cada orden, en pocas consultas (no una por tarjeta)."""
    if not ordenes:
        return []
    ids = [o.id for o, _ in ordenes]
    gremios = {g.id: g.nombre for g in db.execute(select(Gremio)).scalars()}

    asignaciones: dict[uuid.UUID, tuple[Asignacion, str]] = {}
    reasignaciones: dict[uuid.UUID, int] = defaultdict(int)
    for a, nombre in db.execute(
        select(Asignacion, Recolector.nombre)
        .join(Recolector, Recolector.id == Asignacion.recolector_id)
        .where(Asignacion.orden_id.in_(ids))
        .order_by(Asignacion.vigente_desde)
    ):
        previa = asignaciones.get(a.orden_id)
        if previa is not None and previa[0].recolector_id != a.recolector_id:
            reasignaciones[a.orden_id] += 1
        asignaciones[a.orden_id] = (a, nombre)

    resultados = {
        r.orden_id: (r, motivo)
        for r, motivo in db.execute(
            select(ResultadoOrden, MotivoRechazo.nombre)
            .outerjoin(MotivoRechazo, MotivoRechazo.id == ResultadoOrden.motivo_rechazo_id)
            .where(ResultadoOrden.orden_id.in_(ids))
        )
    }

    # Lo que el vecino declaró (residuos); si pidió por tipo de servicio, el nombre del servicio.
    residuos: dict[uuid.UUID, list[str]] = defaultdict(list)
    for oid, emoji, nombre in db.execute(
        select(SolicitudResiduo.orden_id, Residuo.emoji, Residuo.nombre)
        .join(Residuo, Residuo.id == SolicitudResiduo.residuo_id)
        .where(SolicitudResiduo.orden_id.in_(ids))
        .order_by(Residuo.orden, Residuo.nombre)
    ):
        residuos[oid].append(f"{emoji} {nombre}".strip())
    servicios: dict[uuid.UUID, list[str]] = defaultdict(list)
    for oid, nombre in db.execute(
        select(SolicitudServicio.orden_id, TipoServicio.nombre)
        .join(TipoServicio, TipoServicio.id == SolicitudServicio.tipo_servicio_id)
        .where(SolicitudServicio.orden_id.in_(ids))
        .order_by(TipoServicio.nombre)
    ):
        servicios[oid].append(nombre)

    contactos = {
        p.id: p.nombre
        for p in db.execute(
            select(Participante).where(Participante.id.in_({s.participante_id for _, s in ordenes if s.participante_id}))
        ).scalars()
        if p.estado != "eliminado"
    }
    ultimo = dict(
        db.execute(
            select(EventoDominio.orden_id, func.max(EventoDominio.ocurrido_at))
            .where(EventoDominio.orden_id.in_(ids))
            .group_by(EventoDominio.orden_id)
        ).all()
    )
    avisos: dict[uuid.UUID, dict[str, int]] = defaultdict(lambda: {"pendientes": 0, "fallidos": 0})
    for oid, estado, n in db.execute(
        select(EventoSalida.orden_id, EventoSalida.estado, func.count())
        .where(EventoSalida.orden_id.in_(ids), EventoSalida.estado.in_(("pendiente", "en_envio", "fallido")))
        .group_by(EventoSalida.orden_id, EventoSalida.estado)
    ):
        avisos[oid]["fallidos" if estado == "fallido" else "pendientes"] += n

    salida = []
    for o, s in ordenes:
        a = asignaciones.get(o.id)
        vigente = a if a and a[0].vigente_hasta is None else None
        r = resultados.get(o.id)
        desde = ultimo.get(o.id) or o.created_at
        salida.append(
            {
                "orden_id": str(o.id),
                "solicitud_id": str(s.id),
                "codigo_pasaporte": s.codigo_pasaporte,
                "estado": o.estado,
                "gremio_id": str(o.gremio_id),
                "gremio_nombre": gremios.get(o.gremio_id, ""),
                "canal_origen": s.canal_origen,
                "creada_at": _utc(o.created_at),
                "en_estado_desde": _utc(desde),
                "ubicacion": s.ubicacion_operativa,
                "contacto_nombre": contactos.get(s.participante_id) if s.participante_id else None,
                "que": residuos.get(o.id) or servicios.get(o.id) or [],
                "preferencia_horaria": s.preferencia_horaria,
                "observacion": _limpiar(s.observacion) if s.observacion else None,
                "recolector_nombre": vigente[1] if vigente else None,
                "inicio": _utc(vigente[0].inicio) if vigente and vigente[0].inicio else None,
                "fin": _utc(vigente[0].fin) if vigente and vigente[0].fin else None,
                "reasignaciones": reasignaciones.get(o.id, 0),
                "motivo_rechazo": r[1] if r else None,
                "cerrada_at": _utc(r[0].ocurrido_at) if r else None,
                "avisos_pendientes": avisos[o.id]["pendientes"] if o.id in avisos else 0,
                "avisos_fallidos": avisos[o.id]["fallidos"] if o.id in avisos else 0,
            }
        )
    return salida


@router.get("/trazabilidad")
def get_tablero(
    gremio_id: uuid.UUID | None = Query(None),
    desde: InstanteEntrada | None = Query(None, description="Sin fechas: todas las abiertas y las cerradas de los últimos 30 días"),
    hasta: InstanteEntrada | None = Query(None),
    q: str | None = Query(None, max_length=60, description="Código BR-… o ubicación"),
    actor: Actor = Depends(actor_operador),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Tablero de órdenes (todos los gremios para administración; el propio para coordinación)."""
    alcance = _alcance(actor)
    if gremio_id is not None and alcance is not None and gremio_id not in alcance:
        raise prohibido("Fuera de tu gremio.")
    if desde and hasta and hasta <= desde:
        raise invalido({"hasta": "Debe ser posterior a desde"})
    condiciones: list[Any] = []
    if desde or hasta:
        if desde:
            condiciones.append(Orden.created_at >= desde)
        if hasta:
            condiciones.append(Orden.created_at < hasta)
    else:
        condiciones.append(or_(Orden.estado.in_(ABIERTAS), Orden.updated_at >= ahora() - timedelta(days=DIAS_CERRADAS)))
    if gremio_id:
        condiciones.append(Orden.gremio_id == gremio_id)
    elif alcance is not None:
        condiciones.append(Orden.gremio_id.in_(alcance))
    if q and q.strip():
        patron = f"%{q.strip()}%"
        condiciones.append(or_(Solicitud.codigo_pasaporte.ilike(patron), Solicitud.ubicacion_operativa.ilike(patron)))

    unir = Solicitud.id == Orden.solicitud_id
    conteo = {e: 0 for e in ESTADOS}
    for estado, n in db.execute(
        select(Orden.estado, func.count()).join(Solicitud, unir).where(*condiciones).group_by(Orden.estado)
    ):
        conteo[estado] = n
    filas = db.execute(
        select(Orden, Solicitud).join(Solicitud, unir).where(*condiciones)
        .order_by(Orden.created_at.desc(), Orden.id.desc()).limit(MAXIMO + 1)
    ).all()
    return {
        "data": {
            "tarjetas": _tarjetas(db, [(o, s) for o, s in filas[:MAXIMO]]),
            "resumen": {"por_estado": conteo, "total": sum(conteo.values()), "truncado": len(filas) > MAXIMO,
                        "ventana_dias_cerradas": None if (desde or hasta) else DIAS_CERRADAS},
        }
    }


_DESTINO = Literal["vecino", "coordinacion", "sin_destino"]
_PASO = {
    "solicitud_creada": 0, "orden_creada": 1, "nueva_orden": 2, "orden_asignada": 3, "orden_reasignada": 4,
    "orden_programada": 5, "orden_reprogramada": 6, "asignacion": 7,
}


def _destino(a: EventoSalida) -> _DESTINO:
    if a.participante_id:
        return "vecino"
    if a.cuenta_operadora_id:
        return "coordinacion"
    return "sin_destino"


@router.get("/trazabilidad/{orden_id}")
def get_historia(orden_id: uuid.UUID, actor: Actor = Depends(actor_operador), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Historia completa de una orden: eventos, avisos de Brisa, pesajes y puntos."""
    alcance = _alcance(actor)
    fila = db.execute(
        select(Orden, Solicitud).join(Solicitud, Solicitud.id == Orden.solicitud_id).where(Orden.id == orden_id)
    ).first()
    if fila is None or (alcance is not None and fila[0].gremio_id not in alcance):
        raise no_encontrado("orden")
    o, s = fila
    tarjeta = _tarjetas(db, [(o, s)])[0]

    eventos = list(
        db.execute(
            select(EventoDominio)
            .where(or_(EventoDominio.orden_id == o.id,
                       (EventoDominio.solicitud_id == s.id) & EventoDominio.orden_id.is_(None)))
            .order_by(EventoDominio.ocurrido_at, EventoDominio.id)
        ).scalars()
    )
    nombres = _nombres_actores(db, eventos)
    ids_recolector = {
        uuid.UUID(e.datos["recolector_id"]) for e in eventos
        if isinstance(e.datos, dict) and isinstance(e.datos.get("recolector_id"), str)
    }
    recolectores = (
        dict(db.execute(select(Recolector.id, Recolector.nombre).where(Recolector.id.in_(ids_recolector))).all())
        if ids_recolector else {}
    )
    linea: list[dict[str, Any]] = []
    for e in eventos:
        datos = _limpiar(e.datos or {})
        rid = datos.get("recolector_id") if isinstance(datos, dict) else None
        if rid:
            datos["recolector_nombre"] = recolectores.get(uuid.UUID(rid))
        linea.append({
            "clase": "evento", "tipo": e.tipo, "ocurrido_at": _utc(e.ocurrido_at),
            "actor_tipo": e.actor_tipo, "actor_nombre": _actor_nombre(e, nombres), "datos": datos,
        })
    for a in db.execute(
        select(EventoSalida)
        .where(or_(EventoSalida.orden_id == o.id,
                   (EventoSalida.solicitud_id == s.id) & EventoSalida.orden_id.is_(None)))
        .order_by(EventoSalida.created_at)
    ).scalars():
        texto = (a.datos or {}).get("texto_sugerido")
        linea.append({
            "clase": "aviso", "tipo": a.tipo, "ocurrido_at": _utc(a.enviado_at or a.created_at),
            "destino": _destino(a), "estado": a.estado, "intentos": a.intentos,
            "texto": _limpiar(texto) if isinstance(texto, str) else None,
        })
    # Lo de una misma transacción comparte la hora exacta: el empate sigue el orden del flujo.
    linea.sort(key=lambda x: (x["ocurrido_at"], x["clase"] == "aviso", _PASO.get(x["tipo"], 50)))

    # La coordinación ve que la solicitud también va a otro gremio, pero no abre esa orden.
    otras = [
        {"orden_id": str(oid) if alcance is None or g in alcance else None, "gremio_nombre": nombre, "estado": estado}
        for oid, g, nombre, estado in db.execute(
            select(Orden.id, Orden.gremio_id, Gremio.nombre, Orden.estado).join(Gremio, Gremio.id == Orden.gremio_id)
            .where(Orden.solicitud_id == s.id, Orden.id != o.id)
        )
    ]
    pesajes = [
        {"codigo": p.codigo, "estado": p.estado, "fecha_medicion": _utc(p.fecha_medicion)}
        for p in db.execute(
            select(Pesaje).join(PesajeOrden, PesajeOrden.pesaje_id == Pesaje.id)
            .where(PesajeOrden.orden_id == o.id, Pesaje.estado != "borrador")
            .order_by(Pesaje.fecha_medicion)
        ).scalars()
    ]
    puntos = db.execute(
        select(func.coalesce(func.sum(MovimientoPuntos.delta), 0))
        .join(ResultadoOrden, ResultadoOrden.id == MovimientoPuntos.resultado_orden_id)
        .where(ResultadoOrden.orden_id == o.id)
    ).scalar_one()
    return {
        "data": {
            **tarjeta,
            "tipo_generador": s.tipo_generador,
            "otras_ordenes": otras,
            "pesajes": pesajes,
            "puntos_otorgados": f"{puntos:.2f}",
            "linea": linea,
        }
    }
