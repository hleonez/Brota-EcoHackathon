"""Utilidades compartidas por los módulos de dominio."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errores import AppError, conflicto_version, invalido, no_encontrado
from app.core.seguridad import Actor
from app.core.tipos import ahora, zona
from app.models import (
    Base,
    Consentimiento,
    CuentaOperadora,
    EventoDominio,
    EventoSalida,
    PermisoOperador,
    Torre,
    Unidad,
    VinculoUnidad,
)

M = TypeVar("M", bound=Base)


def obtener(db: Session, modelo: type[M], id_: uuid.UUID, recurso: str, bloquear: bool = False) -> M:
    if bloquear:
        obj = db.execute(select(modelo).where(modelo.id == id_).with_for_update()).scalar_one_or_none()  # type: ignore[attr-defined]
    else:
        obj = db.get(modelo, id_)
    if obj is None:
        raise no_encontrado(recurso)
    return obj


def referencia_activa(db: Session, modelo: type[M], id_: uuid.UUID | None, campo: str, recurso: str) -> M:
    """Busca un catálogo referenciado en un cuerpo: inexistente o inactivo es 422, no 404."""
    obj = db.get(modelo, id_) if id_ is not None else None
    if obj is None or not getattr(obj, "activo", True):
        raise invalido({campo: f"{recurso} inexistente o inactivo"})
    return obj


def verificar_version(esperada: int, actual: int) -> None:
    if esperada != actual:
        raise conflicto_version(esperada, actual)


def etiqueta_unidad(unidad: Unidad, torre: Torre | None = None) -> str:
    torre = torre or unidad.torre
    if unidad.tipo == "hogar" and torre is not None:
        nombre_torre = torre.nombre or f"Torre {torre.codigo}"
        return f"{nombre_torre} · Apto {unidad.referencia_local}"
    if unidad.direccion_referencia:
        return f"{unidad.referencia_local} · {unidad.direccion_referencia}"
    return unidad.referencia_local


def unidades_vigentes(db: Session, participante_id: uuid.UUID) -> list[Unidad]:
    return list(
        db.execute(
            select(Unidad)
            .join(VinculoUnidad, VinculoUnidad.unidad_id == Unidad.id)
            .where(VinculoUnidad.participante_id == participante_id, VinculoUnidad.vigente_hasta.is_(None))
            .order_by(VinculoUnidad.vigente_desde)
        ).scalars()
    )


def consentimiento_vigente(db: Session, participante_id: uuid.UUID) -> Consentimiento | None:
    return db.execute(
        select(Consentimiento)
        .where(Consentimiento.participante_id == participante_id)
        .order_by(Consentimiento.registrado_at.desc(), Consentimiento.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def exigir_consentimiento(db: Session, participante_id: uuid.UUID) -> None:
    c = consentimiento_vigente(db, participante_id)
    if c is None or c.decision != "aceptado":
        raise AppError(
            403, "CONSENT_REQUIRED", "Necesitamos tu autorización de datos antes de continuar."
        )


def registrar_evento(
    db: Session,
    tipo: str,
    actor: Actor | None,
    *,
    solicitud_id: uuid.UUID | None = None,
    orden_id: uuid.UUID | None = None,
    pesaje_id: uuid.UUID | None = None,
    datos: dict[str, Any] | None = None,
) -> None:
    db.add(
        EventoDominio(
            tipo=tipo,
            solicitud_id=solicitud_id,
            orden_id=orden_id,
            pesaje_id=pesaje_id,
            actor_tipo=actor.tipo_publico if actor else "sistema",
            actor_id=actor.actor_id if actor else None,
            datos=datos or {},
        )
    )


def encolar_aviso(
    db: Session,
    tipo: str,
    participante_id: uuid.UUID | None,
    datos: dict[str, Any],
    *,
    solicitud_id: uuid.UUID | None = None,
    orden_id: uuid.UUID | None = None,
) -> EventoSalida | None:
    """Guarda el aviso en la misma transacción que el hecho; se entrega al bot después del commit."""
    if participante_id is None:
        return None
    ev = EventoSalida(
        tipo=tipo, participante_id=participante_id, solicitud_id=solicitud_id, orden_id=orden_id, datos=datos
    )
    db.add(ev)
    return ev


def encolar_aviso_coordinacion(
    db: Session,
    tipo: str,
    gremio_id: uuid.UUID,
    datos: dict[str, Any],
    *,
    solicitud_id: uuid.UUID | None = None,
    orden_id: uuid.UUID | None = None,
) -> int:
    """Un aviso por cada cuenta activa de coordinación del gremio que opera por WhatsApp."""
    cuentas = db.execute(
        select(CuentaOperadora.id)
        .join(PermisoOperador, PermisoOperador.cuenta_id == CuentaOperadora.id)
        .where(
            PermisoOperador.rol == "coordinacion",
            PermisoOperador.gremio_id == gremio_id,
            CuentaOperadora.activo.is_(True),
            CuentaOperadora.celular_normalizado.is_not(None),
        )
        .distinct()
    ).scalars().all()
    for cuenta_id in cuentas:
        db.add(
            EventoSalida(
                tipo=tipo, cuenta_operadora_id=cuenta_id, solicitud_id=solicitud_id, orden_id=orden_id, datos=datos
            )
        )
    return len(cuentas)


# --------------------------------------------------------------------------- textos en voz de Brisa


def _hora(d: datetime) -> str:
    h = d.hour % 12 or 12
    sufijo = "a. m." if d.hour < 12 else "p. m."
    return f"{h}:{d.minute:02d} {sufijo}"


def _dia(d: datetime) -> str:
    hoy = ahora().astimezone(d.tzinfo).date()
    if d.date() == hoy:
        return "hoy"
    if d.date() == hoy + timedelta(days=1):
        return "mañana"
    return f"el {d.day:02d}/{d.month:02d}"


def franja_texto(inicio: datetime | None, fin: datetime | None) -> str | None:
    if inicio is None or fin is None:
        return None
    tz = zona(get_settings().zona_horaria)
    i, f = inicio.astimezone(tz), fin.astimezone(tz)
    return f"{_dia(i)} entre {_hora(i)} y {_hora(f)}"
