"""M08 · Educación y avisos al residente (integración con el bot de WhatsApp).

Los avisos nacen en la misma transacción que el hecho (asignación, recogida, rechazo,
entrega directa) y se entregan al bot después del commit, con reintentos:

- Modo **pull** (por defecto): el bot llama `POST /v1/canal/avisos/reservas`, envía cada
  mensaje por WhatsApp y confirma con `POST /v1/canal/avisos/{id}/resultado`.
- Modo **webhook**: la API hace POST a `BOT_WEBHOOK_URL` con firma HMAC-SHA256
  (`X-Brota-Firma: sha256=<hex>`); un 2xx marca el aviso como enviado.

Una reserva vence a los `AVISOS_RESERVA_SEGUNDOS`: si el bot se cae, el aviso vuelve a quedar
disponible. El bot debe deduplicar por `id` de aviso (puede recibir uno repetido tras un vencimiento).
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errores import no_encontrado, transicion_invalida
from app.core.paginacion import Paginacion, paginacion, paginar
from app.core.seguridad import Actor, actor_bot, actor_operador, get_actor_opcional
from app.core.tipos import Entrada, Instante, Salida, ahora
from app.db import get_db
from app.models import (
    ContenidoEducativo,
    ContenidoMaterial,
    ContenidoMotivo,
    CuentaOperadora,
    EventoSalida,
    Participante,
)
from app.modulos.coordinacion import orden_de_coordinacion

router = APIRouter(tags=["educación y avisos"])
canal = APIRouter(prefix="/canal", tags=["canal WhatsApp (bot)"])

# --------------------------------------------------------------------------- esquemas


class DestinoOut(Salida):
    tipo: Literal["participante", "operador"] = "participante"
    participante_id: uuid.UUID | None = None
    cuenta_operadora_id: uuid.UUID | None = None
    celular: str
    nombre: str


class AvisoOut(Salida):
    id: uuid.UUID
    tipo: str
    estado: str
    intentos: int
    destino: DestinoOut | None = None
    solicitud_id: uuid.UUID | None
    orden_id: uuid.UUID | None
    datos: dict[str, Any]
    created_at: Instante
    reservado_hasta: Instante | None = None


class AvisoEstadoOut(Salida):
    id: uuid.UUID
    tipo: str
    estado: str
    intentos: int
    enviado_at: Instante | None
    ultimo_error: str | None
    created_at: Instante


class ReservaIn(Entrada):
    limite: int = Field(default=10, ge=1, le=50)


class ResultadoAvisoIn(Entrada):
    estado: Literal["enviado", "fallido"]
    id_externo: str | None = Field(default=None, max_length=200)
    error: str | None = Field(default=None, max_length=500)
    reintentar: bool = True


class ContenidoOut(Salida):
    id: uuid.UUID
    tema: str
    version: int
    titulo: str
    tipo: str
    recurso: str | None
    texto: str | None
    general: bool


# --------------------------------------------------------------------------- servicio


def _destino(db: Session, ev: EventoSalida) -> DestinoOut | None:
    """Resuelve el celular al momento de entregar (no se copia en el aviso)."""
    if ev.participante_id:
        p = db.get(Participante, ev.participante_id)
        if p is None or p.estado == "eliminado" or not p.celular_normalizado:
            return None
        return DestinoOut(participante_id=p.id, celular=p.celular_normalizado, nombre=p.nombre)
    if ev.cuenta_operadora_id:
        c = db.get(CuentaOperadora, ev.cuenta_operadora_id)
        if c is None or not c.activo or not c.celular_normalizado:
            return None
        return DestinoOut(tipo="operador", cuenta_operadora_id=c.id, celular=c.celular_normalizado, nombre=c.nombre)
    return None


def reservar(db: Session, limite: int) -> list[AvisoOut]:
    """Toma avisos pendientes (o con reserva vencida) sin bloquear a otros consumidores."""
    s = get_settings()
    t = ahora()
    # now() de Postgres, el mismo reloj con el que nace la fila.
    filas = (
        db.execute(
            select(EventoSalida)
            .where(EventoSalida.estado.in_(("pendiente", "en_envio")), EventoSalida.proximo_intento_at <= func.now())
            .order_by(EventoSalida.proximo_intento_at, EventoSalida.created_at)
            .limit(limite)
            .with_for_update(skip_locked=True)
        )
        .scalars()
        .all()
    )
    salida: list[AvisoOut] = []
    for ev in filas:
        destino = _destino(db, ev)
        if destino is None:
            ev.estado = "descartado"
            ev.ultimo_error = "Destino sin celular, inactivo o eliminado"
            continue
        if ev.intentos >= s.avisos_max_intentos:
            ev.estado = "fallido"
            ev.ultimo_error = ev.ultimo_error or "Reserva vencida sin confirmación"
            continue
        ev.estado = "en_envio"
        ev.intentos += 1
        ev.proximo_intento_at = t + timedelta(seconds=s.avisos_reserva_segundos)
        salida.append(
            AvisoOut(
                id=ev.id,
                tipo=ev.tipo,
                estado=ev.estado,
                intentos=ev.intentos,
                destino=destino,
                solicitud_id=ev.solicitud_id,
                orden_id=ev.orden_id,
                datos=ev.datos,
                created_at=ev.created_at,
                reservado_hasta=ev.proximo_intento_at,
            )
        )
    db.commit()
    return salida


def registrar_resultado_envio(
    db: Session, aviso_id: uuid.UUID, estado: str, id_externo: str | None, error: str | None, reintentar: bool
) -> EventoSalida:
    s = get_settings()
    ev = db.execute(select(EventoSalida).where(EventoSalida.id == aviso_id).with_for_update()).scalar_one_or_none()
    if ev is None:
        raise no_encontrado("aviso")
    if ev.estado == "enviado":
        return ev  # confirmación repetida: idempotente
    if ev.estado not in ("en_envio", "pendiente"):
        raise transicion_invalida(f"El aviso está {ev.estado}.")
    t = ahora()
    if estado == "enviado":
        ev.estado = "enviado"
        ev.enviado_at = t
        ev.id_externo = id_externo
        ev.ultimo_error = None
    else:
        ev.ultimo_error = (error or "Error sin detalle")[:500]
        if reintentar and ev.intentos < s.avisos_max_intentos:
            ev.estado = "pendiente"
            ev.proximo_intento_at = t + timedelta(seconds=min(15 * 2 ** max(ev.intentos - 1, 0), 3600))
        else:
            ev.estado = "fallido"
    db.commit()
    return ev


# --------------------------------------------------------------------------- rutas del bot


@canal.post("/avisos/reservas")
def post_reservas(datos: ReservaIn, actor: Actor = Depends(actor_bot), db: Session = Depends(get_db)):
    """Reserva avisos para enviarlos por WhatsApp. No requiere Idempotency-Key: repetir solo reserva otros."""
    return {"data": [a.model_dump(mode="json") for a in reservar(db, datos.limite)]}


@canal.post("/avisos/{aviso_id}/resultado")
def post_resultado_aviso(
    aviso_id: uuid.UUID, datos: ResultadoAvisoIn, actor: Actor = Depends(actor_bot), db: Session = Depends(get_db)
):
    ev = registrar_resultado_envio(db, aviso_id, datos.estado, datos.id_externo, datos.error, datos.reintentar)
    return {"data": AvisoEstadoOut.model_validate(ev).model_dump(mode="json")}


@canal.get("/avisos")
def get_avisos_canal(
    estado: Literal["pendiente", "en_envio", "enviado", "fallido", "descartado"] | None = Query(None),
    actor: Actor = Depends(actor_bot),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
):
    """Consulta de diagnóstico para el bot (no reserva)."""
    stmt = select(EventoSalida).order_by(EventoSalida.created_at.desc(), EventoSalida.id.desc())
    if estado:
        stmt = stmt.where(EventoSalida.estado == estado)
    return paginar(db, stmt, pag, lambda e: AvisoEstadoOut.model_validate(e).model_dump(mode="json"))


# --------------------------------------------------------------------------- rutas generales


@router.get("/ordenes/{orden_id}/avisos")
def get_avisos_orden(
    orden_id: uuid.UUID,
    actor: Actor = Depends(actor_operador),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
):
    orden_de_coordinacion(db, actor, orden_id)
    stmt = (
        select(EventoSalida)
        .where(EventoSalida.orden_id == orden_id)
        .order_by(EventoSalida.created_at.desc(), EventoSalida.id.desc())
    )
    return paginar(db, stmt, pag, lambda e: AvisoEstadoOut.model_validate(e).model_dump(mode="json"))


@router.get("/contenidos-educativos")
def get_contenidos(
    tema: Literal["separacion", "huerta", "horarios_rutas", "servicio"] | None = Query(None),
    material_id: uuid.UUID | None = Query(None),
    motivo_rechazo_id: uuid.UUID | None = Query(None),
    _actor: Actor | None = Depends(get_actor_opcional),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
):
    stmt = select(ContenidoEducativo).where(
        ContenidoEducativo.activo.is_(True),
        ContenidoEducativo.publicado.is_(True),
        or_(ContenidoEducativo.vigente_desde.is_(None), ContenidoEducativo.vigente_desde <= ahora()),
        or_(ContenidoEducativo.vigente_hasta.is_(None), ContenidoEducativo.vigente_hasta > ahora()),
    )
    if tema:
        stmt = stmt.where(ContenidoEducativo.tema == tema)
    if motivo_rechazo_id:
        stmt = stmt.where(
            or_(
                ContenidoEducativo.id.in_(
                    select(ContenidoMotivo.contenido_id).where(ContenidoMotivo.motivo_rechazo_id == motivo_rechazo_id)
                ),
                ContenidoEducativo.general.is_(True),
            )
        )
    if material_id:
        stmt = stmt.where(
            or_(
                ContenidoEducativo.id.in_(
                    select(ContenidoMaterial.contenido_id).where(ContenidoMaterial.material_id == material_id)
                ),
                ContenidoEducativo.general.is_(True),
            )
        )
    stmt = stmt.order_by(ContenidoEducativo.general, ContenidoEducativo.created_at.desc(), ContenidoEducativo.id)
    return paginar(db, stmt, pag, lambda c: ContenidoOut.model_validate(c).model_dump(mode="json"))
