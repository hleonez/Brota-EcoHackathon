"""M03 · Solicitudes y Pasaporte Circular.

Una solicitud ("Los dos") crea una orden por gremio en una sola transacción.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field
from sqlalchemy import exists, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.core.errores import AppError, invalido, no_encontrado, prohibido
from app.core.idempotencia import escritura
from app.core.paginacion import Paginacion, paginacion, paginar
from app.core.seguridad import Actor, actor_participante, get_actor
from app.core.tipos import Entrada, Instante, PuntosSalida, Salida
from app.db import get_db
from app.models import (
    Asignacion,
    EventoDominio,
    Gremio,
    MotivoRechazo,
    MovimientoPuntos,
    Orden,
    Participante,
    Pesaje,
    PesajeOrden,
    ResultadoOrden,
    Solicitud,
    SolicitudServicio,
    TipoServicio,
    Unidad,
    solicitud_pasaporte_seq,
)
from app.modulos.comun import (
    etiqueta_unidad,
    exigir_consentimiento,
    registrar_evento,
    unidades_vigentes,
)

router = APIRouter(tags=["solicitudes"])

ABIERTAS = ("nueva", "asignada")
FINALES = ("recogida", "rechazada")

# --------------------------------------------------------------------------- esquemas


class SolicitudIn(Entrada):
    unidad_id: uuid.UUID | None = Field(
        default=None, description="Opcional si el participante tiene exactamente una unidad vinculada"
    )
    tipo_servicio_ids: list[uuid.UUID] = Field(min_length=1, max_length=5)
    observacion: str | None = Field(default=None, max_length=500)


class AsignacionOut(Salida):
    recolector_id: uuid.UUID
    recolector_nombre: str
    inicio: Instante | None
    fin: Instante | None
    forma_aviso: str
    vigente_desde: Instante


class ResultadoOut(Salida):
    resultado: str
    motivo_rechazo_id: uuid.UUID | None
    motivo_rechazo_nombre: str | None
    observacion: str | None
    ocurrido_at: Instante
    confirmado_at: Instante


class OrdenOut(Salida):
    id: uuid.UUID
    created_at: Instante
    version: int
    estado: str
    gremio_id: uuid.UUID
    gremio_nombre: str
    solicitud_id: uuid.UUID
    codigo_pasaporte: str
    tipo_servicio_ids: list[uuid.UUID]
    asignacion: AsignacionOut | None = None
    reasignaciones: int = 0
    resultado: ResultadoOut | None = None


class OrdenBandejaOut(OrdenOut):
    """Vista de coordinación: datos mínimos para prestar el servicio."""

    unidad_id: uuid.UUID
    ubicacion_operativa: str
    torre_id: uuid.UUID | None
    contacto_nombre: str | None
    observacion: str | None


class AvanceOut(Salida):
    ordenes_totales: int
    ordenes_finalizadas: int
    estado_general: Literal["pendiente", "en_curso", "parcial", "atendida"]
    alcance: Literal["propio", "gremio"]


class SolicitudOut(Salida):
    id: uuid.UUID
    created_at: Instante
    version: int
    codigo_pasaporte: str
    unidad_id: uuid.UUID
    ubicacion_operativa: str
    canal_origen: str
    observacion: str | None
    tipo_servicio_ids: list[uuid.UUID]
    avance: AvanceOut
    ordenes: list[OrdenOut]


class EventoPasaporte(Salida):
    tipo: str
    orden_id: uuid.UUID | None
    pesaje_id: uuid.UUID | None
    ocurrido_at: Instante


class PesajeRef(Salida):
    pesaje_id: uuid.UUID
    codigo: str
    orden_id: uuid.UUID
    estado: str
    fecha_medicion: Instante
    nota: str = "Lote de procedencia: los kilos del lote no se reparten por hogar."


class PuntosRef(Salida):
    orden_id: uuid.UUID
    delta: PuntosSalida
    tipo: str
    ocurrido_at: Instante


class PasaporteOut(Salida):
    solicitud: SolicitudOut
    eventos: list[EventoPasaporte]
    pesajes: list[PesajeRef]
    puntos: list[PuntosRef]


# --------------------------------------------------------------------------- serialización


def _gremio_nombres(db: Session) -> dict[uuid.UUID, str]:
    return {g.id: g.nombre for g in db.execute(select(Gremio)).scalars()}


def orden_out(db: Session, o: Orden, gremios: dict[uuid.UUID, str] | None = None, bandeja: bool = False) -> OrdenOut:
    gremios = gremios or _gremio_nombres(db)
    vigente = next((a for a in o.asignaciones if a.vigente_hasta is None), None)
    asign = None
    if vigente is not None:
        asign = AsignacionOut(
            recolector_id=vigente.recolector_id,
            recolector_nombre=vigente.recolector.nombre,
            inicio=vigente.inicio,
            fin=vigente.fin,
            forma_aviso=vigente.forma_aviso,
            vigente_desde=vigente.vigente_desde,
        )
    res = None
    if o.resultado is not None:
        r = o.resultado
        motivo = db.get(MotivoRechazo, r.motivo_rechazo_id) if r.motivo_rechazo_id else None
        res = ResultadoOut(
            resultado=r.resultado,
            motivo_rechazo_id=r.motivo_rechazo_id,
            motivo_rechazo_nombre=motivo.nombre if motivo else None,
            observacion=r.observacion,
            ocurrido_at=r.ocurrido_at,
            confirmado_at=r.confirmado_at,
        )
    servicios = [s.tipo_servicio_id for s in o.solicitud.servicios if s.orden_id == o.id]
    base = dict(
        id=o.id,
        created_at=o.created_at,
        version=o.version,
        estado=o.estado,
        gremio_id=o.gremio_id,
        gremio_nombre=gremios.get(o.gremio_id, ""),
        solicitud_id=o.solicitud_id,
        codigo_pasaporte=o.solicitud.codigo_pasaporte,
        tipo_servicio_ids=servicios,
        asignacion=asign,
        reasignaciones=max(len(o.asignaciones) - 1, 0),
        resultado=res,
    )
    if not bandeja:
        return OrdenOut(**base)
    s = o.solicitud
    contacto = db.get(Participante, s.participante_id) if s.participante_id else None
    return OrdenBandejaOut(
        **base,
        unidad_id=s.unidad_id,
        ubicacion_operativa=s.ubicacion_operativa,
        torre_id=s.unidad.torre_id,
        contacto_nombre=contacto.nombre if contacto and contacto.estado != "eliminado" else None,
        observacion=s.observacion,
    )


def _estado_general(ordenes: list[Orden]) -> str:
    finales = sum(1 for o in ordenes if o.estado in FINALES)
    if ordenes and finales == len(ordenes):
        return "atendida"
    if finales:
        return "parcial"
    if any(o.estado == "asignada" for o in ordenes):
        return "en_curso"
    return "pendiente"


def solicitud_out(db: Session, s: Solicitud, actor: Actor) -> SolicitudOut:
    gremios = _gremio_nombres(db)
    if actor.es_operador:
        visibles = [o for o in s.ordenes if actor.coordina(o.gremio_id)]
        alcance = "gremio"
    else:
        visibles = list(s.ordenes)
        alcance = "propio"
    return SolicitudOut(
        id=s.id,
        created_at=s.created_at,
        version=s.version,
        codigo_pasaporte=s.codigo_pasaporte,
        unidad_id=s.unidad_id,
        ubicacion_operativa=s.ubicacion_operativa,
        canal_origen=s.canal_origen,
        observacion=s.observacion,
        tipo_servicio_ids=[x.tipo_servicio_id for x in s.servicios],
        avance=AvanceOut(
            ordenes_totales=len(visibles),
            ordenes_finalizadas=sum(1 for o in visibles if o.estado in FINALES),
            estado_general=_estado_general(visibles),  # type: ignore[arg-type]
            alcance=alcance,  # type: ignore[arg-type]
        ),
        ordenes=[orden_out(db, o, gremios) for o in visibles],
    )


def _opciones_carga():
    return (
        selectinload(Solicitud.ordenes).selectinload(Orden.asignaciones).selectinload(Asignacion.recolector),
        selectinload(Solicitud.ordenes).selectinload(Orden.resultado),
        selectinload(Solicitud.servicios),
    )


# --------------------------------------------------------------------------- servicio


def crear_solicitud(db: Session, actor: Actor, datos: SolicitudIn) -> SolicitudOut:
    assert actor.participante_id is not None
    exigir_consentimiento(db, actor.participante_id)
    propias = unidades_vigentes(db, actor.participante_id)
    if datos.unidad_id is None:
        if len(propias) != 1:
            raise invalido(
                {"unidad_id": "Indica la unidad" if propias else "No tienes una unidad vinculada; regístrala primero"}
            )
        unidad_id = propias[0].id
    else:
        if datos.unidad_id not in {u.id for u in propias}:
            raise no_encontrado("unidad")
        unidad_id = datos.unidad_id

    # Serializa solicitudes concurrentes del mismo hogar (regla de solicitud abierta).
    unidad = db.execute(select(Unidad).where(Unidad.id == unidad_id).with_for_update()).scalar_one()
    if not unidad.activo:
        raise invalido({"unidad_id": "Unidad inactiva"})

    ids = datos.tipo_servicio_ids
    if len(set(ids)) != len(ids):
        raise invalido({"tipo_servicio_ids": "Servicios repetidos"})
    servicios = db.execute(select(TipoServicio).where(TipoServicio.id.in_(ids))).scalars().all()
    por_id = {t.id: t for t in servicios}
    faltan = [str(i) for i in ids if i not in por_id or not por_id[i].activo]
    if faltan:
        raise invalido({"tipo_servicio_ids": f"Servicio inexistente o inactivo: {', '.join(faltan)}"})

    if get_settings().regla_solicitud_abierta:
        abierta = db.execute(
            select(Solicitud.id, Solicitud.codigo_pasaporte)
            .join(SolicitudServicio, SolicitudServicio.solicitud_id == Solicitud.id)
            .join(Orden, Orden.id == SolicitudServicio.orden_id)
            .where(
                Solicitud.unidad_id == unidad_id,
                SolicitudServicio.tipo_servicio_id.in_(ids),
                Orden.estado.in_(ABIERTAS),
            )
            .limit(1)
        ).first()
        if abierta is not None:
            raise AppError(
                409,
                "OPEN_REQUEST_EXISTS",
                f"Ya tienes una solicitud abierta ({abierta.codigo_pasaporte}). Te avisamos cuando pasen.",
                extra={"solicitud_id": str(abierta.id), "codigo_pasaporte": abierta.codigo_pasaporte},
            )

    n = db.execute(select(solicitud_pasaporte_seq.next_value())).scalar_one()
    s = Solicitud(
        codigo_pasaporte=f"BR-{n:05d}",
        unidad_id=unidad_id,
        participante_id=actor.participante_id,
        canal_origen=actor.canal,
        observacion=datos.observacion,
        ubicacion_operativa=etiqueta_unidad(unidad),
    )
    db.add(s)
    db.flush()
    ordenes: dict[uuid.UUID, Orden] = {}
    for tid in ids:
        g = por_id[tid].gremio_id
        if g not in ordenes:
            ordenes[g] = Orden(solicitud_id=s.id, gremio_id=g)
            db.add(ordenes[g])
    db.flush()
    for tid in ids:
        db.add(SolicitudServicio(solicitud_id=s.id, tipo_servicio_id=tid, orden_id=ordenes[por_id[tid].gremio_id].id))
    registrar_evento(
        db, "solicitud_creada", actor, solicitud_id=s.id, datos={"ordenes": len(ordenes), "canal": actor.canal}
    )
    for o in ordenes.values():
        registrar_evento(db, "orden_creada", actor, solicitud_id=s.id, orden_id=o.id)
    db.flush()
    db.expire(s)
    return solicitud_out(db, cargar_solicitud(db, s.id), actor)


def cargar_solicitud(db: Session, solicitud_id: uuid.UUID) -> Solicitud:
    s = db.execute(
        select(Solicitud)
        .where(Solicitud.id == solicitud_id)
        .options(*_opciones_carga())
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if s is None:
        raise no_encontrado("solicitud")
    return s


def _filtro_visibilidad(stmt, actor: Actor, db: Session):
    if actor.tipo == "participante":
        propias = [u.id for u in unidades_vigentes(db, actor.participante_id)]  # type: ignore[arg-type]
        return stmt.where(Solicitud.unidad_id.in_(propias or [uuid.uuid4()]))
    if actor.es_operador and actor.gremios_coordinados:
        return stmt.where(
            exists().where(Orden.solicitud_id == Solicitud.id, Orden.gremio_id.in_(actor.gremios_coordinados))
        )
    raise prohibido("Las solicitudes son visibles para su residente y la coordinación del gremio.")


def solicitud_visible(db: Session, actor: Actor, solicitud_id: uuid.UUID) -> Solicitud:
    stmt = _filtro_visibilidad(select(Solicitud.id).where(Solicitud.id == solicitud_id), actor, db)
    if db.execute(stmt).first() is None:
        raise no_encontrado("solicitud")
    return cargar_solicitud(db, solicitud_id)


# --------------------------------------------------------------------------- rutas


@router.post("/solicitudes", status_code=201)
def post_solicitud(
    datos: SolicitudIn, request: Request, actor: Actor = Depends(actor_participante), db: Session = Depends(get_db)
):
    return escritura(request, db, actor, datos, lambda: crear_solicitud(db, actor, datos), status=201)


@router.get("/solicitudes")
def get_solicitudes(
    unidad_id: uuid.UUID | None = Query(None),
    abiertas: bool | None = Query(None, description="true: con alguna orden nueva/asignada"),
    actor: Actor = Depends(get_actor),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
):
    stmt = _filtro_visibilidad(select(Solicitud.id), actor, db)
    if unidad_id is not None:
        stmt = stmt.where(Solicitud.unidad_id == unidad_id)
    if abiertas is not None:
        cond = exists().where(Orden.solicitud_id == Solicitud.id, Orden.estado.in_(ABIERTAS))
        stmt = stmt.where(cond if abiertas else ~cond)
    stmt = stmt.order_by(Solicitud.created_at.desc(), Solicitud.id.desc())
    return paginar(
        db, stmt, pag, lambda sid: solicitud_out(db, cargar_solicitud(db, sid), actor).model_dump(mode="json")
    )


@router.get("/solicitudes/{solicitud_id}")
def get_solicitud(solicitud_id: uuid.UUID, actor: Actor = Depends(get_actor), db: Session = Depends(get_db)):
    s = solicitud_visible(db, actor, solicitud_id)
    return {"data": solicitud_out(db, s, actor).model_dump(mode="json")}


@router.get("/solicitudes/{solicitud_id}/pasaporte")
def get_pasaporte(solicitud_id: uuid.UUID, actor: Actor = Depends(get_actor), db: Session = Depends(get_db)):
    s = solicitud_visible(db, actor, solicitud_id)
    salida = solicitud_out(db, s, actor)
    orden_ids = [o.id for o in salida.ordenes]
    eventos = db.execute(
        select(EventoDominio)
        .where(
            (EventoDominio.orden_id.in_(orden_ids))
            | ((EventoDominio.solicitud_id == s.id) & EventoDominio.orden_id.is_(None))
        )
        .order_by(EventoDominio.ocurrido_at, EventoDominio.id)
    ).scalars()
    pesajes = db.execute(
        select(Pesaje, PesajeOrden.orden_id)
        .join(PesajeOrden, PesajeOrden.pesaje_id == Pesaje.id)
        .where(PesajeOrden.orden_id.in_(orden_ids), Pesaje.estado != "borrador")
        .order_by(Pesaje.fecha_medicion)
    ).all()
    puntos: list[PuntosRef] = []
    if actor.tipo == "participante":
        filas = db.execute(
            select(MovimientoPuntos, ResultadoOrden.orden_id)
            .join(ResultadoOrden, ResultadoOrden.id == MovimientoPuntos.resultado_orden_id)
            .where(ResultadoOrden.orden_id.in_(orden_ids), MovimientoPuntos.participante_id == actor.participante_id)
        ).all()
        puntos = [PuntosRef(orden_id=oid, delta=m.delta, tipo=m.tipo, ocurrido_at=m.ocurrido_at) for m, oid in filas]
    out = PasaporteOut(
        solicitud=salida,
        eventos=[EventoPasaporte.model_validate(e) for e in eventos],
        pesajes=[
            PesajeRef(pesaje_id=p.id, codigo=p.codigo, orden_id=oid, estado=p.estado, fecha_medicion=p.fecha_medicion)
            for p, oid in pesajes
        ],
        puntos=puntos,
    )
    return {"data": out.model_dump(mode="json")}


