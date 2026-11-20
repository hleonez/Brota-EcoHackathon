"""M07 · Puntos (Moneda Verde): acreditación interna, saldo y movimientos.

No existe endpoint para "enviar puntos": la acreditación la dispara un hecho validado
(resultado humano o entrega directa confirmada). `clave_aplicacion` garantiza un abono
por hecho aunque se reintente o cambie la versión de la regla.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.paginacion import Paginacion, paginacion, paginar
from app.core.seguridad import Actor, actor_participante
from app.core.tipos import Instante, InstanteEntrada, PuntosSalida, Salida
from app.db import get_db
from app.models import (
    MovimientoPuntos,
    Orden,
    ResultadoOrden,
    Solicitud,
    VersionReglaIncentivo,
)

router = APIRouter(tags=["puntos"])

Evaluacion = Literal["acreditada", "no_aplica", "pendiente", "requiere_revision"]


@dataclass
class ResultadoAcreditacion:
    evaluacion: Evaluacion
    puntos: Decimal | None = None
    movimiento_id: uuid.UUID | None = None
    nuevo: bool = False


def regla_vigente(
    db: Session, modalidad: str, en: datetime, gremio_id: uuid.UUID | None, conjunto_id: uuid.UUID | None
) -> VersionReglaIncentivo | None | Literal["ambigua"]:
    """Prioridad explícita: conjunto > gremio > global. Dos reglas del mismo nivel = ambigua."""
    filas = (
        db.execute(
            select(VersionReglaIncentivo).where(
                VersionReglaIncentivo.modalidad == modalidad,
                VersionReglaIncentivo.vigente_desde <= en,
                or_(VersionReglaIncentivo.vigente_hasta.is_(None), VersionReglaIncentivo.vigente_hasta > en),
            )
        )
        .scalars()
        .all()
    )
    for ambito, id_ in (("conjunto", conjunto_id), ("gremio", gremio_id), ("global", None)):
        candidatas = [r for r in filas if r.ambito_tipo == ambito and r.ambito_id == id_]
        if len(candidatas) > 1:
            return "ambigua"
        if candidatas:
            return candidatas[0]
    return None


def acreditar(
    db: Session,
    *,
    modalidad: str,
    clave: str,
    participante_id: uuid.UUID | None,
    unidad_id: uuid.UUID | None,
    torre_id: uuid.UUID | None,
    gremio_id: uuid.UUID | None,
    conjunto_id: uuid.UUID | None,
    ocurrido_at: datetime,
    resultado_orden_id: uuid.UUID | None = None,
    entrega_directa_id: uuid.UUID | None = None,
    pesaje_id: uuid.UUID | None = None,
) -> ResultadoAcreditacion:
    if participante_id is None:
        return ResultadoAcreditacion("no_aplica")
    regla = regla_vigente(db, modalidad, ocurrido_at, gremio_id, conjunto_id)
    if regla == "ambigua":
        return ResultadoAcreditacion("requiere_revision")
    if regla is None:
        return ResultadoAcreditacion("pendiente")
    try:
        puntos = Decimal(str(regla.parametros.get("puntos")))
    except (InvalidOperation, TypeError):
        return ResultadoAcreditacion("requiere_revision")
    if puntos <= 0:
        return ResultadoAcreditacion("requiere_revision")
    mov_id = db.execute(
        pg_insert(MovimientoPuntos)
        .values(
            participante_id=participante_id,
            unidad_id=unidad_id,
            torre_id=torre_id,
            delta=puntos,
            detalle_calculo={"modalidad": modalidad, "cantidad": "1", "puntos_por_entrega": str(puntos), "total": str(puntos), "regla_codigo": regla.codigo, "regla_id": str(regla.id), "nota": "Regla propuesta del equipo; valores sujetos a validación FSD"},
            tipo="abono",
            version_regla_id=regla.id,
            resultado_orden_id=resultado_orden_id,
            entrega_directa_id=entrega_directa_id,
            pesaje_id=pesaje_id,
            clave_aplicacion=clave,
            ocurrido_at=ocurrido_at,
        )
        .on_conflict_do_nothing(index_elements=["clave_aplicacion"])
        .returning(MovimientoPuntos.id)
    ).scalar_one_or_none()
    if mov_id is None:
        existente = db.execute(
            select(MovimientoPuntos).where(MovimientoPuntos.clave_aplicacion == clave)
        ).scalar_one()
        return ResultadoAcreditacion("acreditada", existente.delta, existente.id, nuevo=False)
    return ResultadoAcreditacion("acreditada", puntos, mov_id, nuevo=True)


def saldo(db: Session, participante_id: uuid.UUID) -> Decimal:
    total = db.execute(
        select(func.coalesce(func.sum(MovimientoPuntos.delta), 0)).where(
            MovimientoPuntos.participante_id == participante_id
        )
    ).scalar_one()
    return Decimal(total)


# --------------------------------------------------------------------------- rutas


class SaldoOut(Salida):
    saldo: PuntosSalida
    titularidad: Literal["personal"] = "personal"
    movimientos: int


class MovimientoOut(Salida):
    detalle_calculo: dict | None = None
    id: uuid.UUID
    delta: PuntosSalida
    tipo: str
    regla_codigo: str | None
    codigo_pasaporte: str | None
    resultado_orden_id: uuid.UUID | None
    entrega_directa_id: uuid.UUID | None
    ocurrido_at: Instante


@router.get("/me/puntos")
def get_mis_puntos(actor: Actor = Depends(actor_participante), db: Session = Depends(get_db)):
    n = db.execute(
        select(func.count()).select_from(MovimientoPuntos).where(MovimientoPuntos.participante_id == actor.participante_id)
    ).scalar_one()
    return {"data": SaldoOut(saldo=saldo(db, actor.participante_id), movimientos=n).model_dump(mode="json")}  # type: ignore[arg-type]


@router.get("/me/movimientos-puntos")
def get_mis_movimientos(
    desde: InstanteEntrada | None = Query(None),
    hasta: InstanteEntrada | None = Query(None),
    actor: Actor = Depends(actor_participante),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
):
    stmt = (
        select(MovimientoPuntos, VersionReglaIncentivo.codigo, Solicitud.codigo_pasaporte)
        .outerjoin(VersionReglaIncentivo, VersionReglaIncentivo.id == MovimientoPuntos.version_regla_id)
        .outerjoin(ResultadoOrden, ResultadoOrden.id == MovimientoPuntos.resultado_orden_id)
        .outerjoin(Orden, Orden.id == ResultadoOrden.orden_id)
        .outerjoin(Solicitud, Solicitud.id == Orden.solicitud_id)
        .where(MovimientoPuntos.participante_id == actor.participante_id)
        .order_by(MovimientoPuntos.ocurrido_at.desc(), MovimientoPuntos.id.desc())
    )
    if desde is not None:
        stmt = stmt.where(MovimientoPuntos.ocurrido_at >= desde)
    if hasta is not None:
        stmt = stmt.where(MovimientoPuntos.ocurrido_at < hasta)

    def conv(fila) -> dict:
        m, regla, pasaporte = fila
        return MovimientoOut(
            id=m.id,
            delta=m.delta,
            detalle_calculo=m.detalle_calculo,
            tipo=m.tipo,
            regla_codigo=regla,
            codigo_pasaporte=pasaporte,
            resultado_orden_id=m.resultado_orden_id,
            entrega_directa_id=m.entrega_directa_id,
            ocurrido_at=m.ocurrido_at,
        ).model_dump(mode="json")

    return paginar(db, stmt, pag, conv, escalar=False)
