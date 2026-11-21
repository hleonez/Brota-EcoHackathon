"""Conversaciones de Brisa vistas por Administración, con privacidad.

- El bot registra cada mensaje entrante y saliente con `POST /v1/canal/mensajes` (solo el token de
  servicio, sin `X-Canal-Celular`). El `wamid` hace la escritura idempotente.
- Administración las lee agrupadas por contacto. Ninguna respuesta lleva el celular completo: cada
  conversación se identifica con una `clave` opaca (HMAC del celular) y el número sale enmascarado.
- Retención: en cada registro se borran los mensajes con más de `CONVERSACIONES_RETENCION_DIAS`.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import uuid
from datetime import timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Path
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errores import AppError, invalido, no_encontrado, prohibido
from app.core.paginacion import Paginacion, paginacion, paginar
from app.core.seguridad import Actor, _secreto, actor_admin, get_actor, normalizar_celular
from app.core.tipos import Entrada, _utc, ahora
from app.db import get_db
from app.models import CuentaOperadora, MensajeConversacion, Participante

router = APIRouter(tags=["conversaciones (administración)"])
canal = APIRouter(prefix="/canal", tags=["canal WhatsApp (bot)"])

MAX_TEXTO = 4000
MAX_RESUMEN = 120
SIN_REGISTRO = "Vecino sin registrar"


# --------------------------------------------------------------------------- privacidad


def clave_de_celular(celular: str) -> str:
    """Identificador opaco y estable de una conversación. No deja deducir el número."""
    return hmac.new(_secreto().encode(), celular.encode(), hashlib.sha256).hexdigest()[:24]


def enmascarar_celular(celular: str) -> str:
    """'+573001234567' → '+57 300 ••• 4567'."""
    digitos = re.sub(r"\D", "", celular or "")
    if len(digitos) > 10:
        pais, nacional = digitos[:-10], digitos[-10:]
    else:
        pais, nacional = "", digitos
    prefijo = f"+{pais} " if pais else ""
    if len(nacional) >= 10:
        return f"{prefijo}{nacional[:3]} ••• {nacional[-4:]}"
    return f"{prefijo}••• {nacional[-4:]}"


def _ocultar_numero(texto: str, celular: str) -> str:
    """Si el texto menciona el propio número del contacto, lo reemplaza por su versión enmascarada."""
    digitos = celular.lstrip("+")
    variantes = {celular, digitos}
    if len(digitos) > 10:
        variantes.add(digitos[-10:])
    for v in sorted(variantes, key=len, reverse=True):
        if v and v in texto:
            texto = texto.replace(v, enmascarar_celular(celular))
    return texto


def _resumen(texto: str) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= MAX_RESUMEN else texto[: MAX_RESUMEN - 1] + "…"


# --------------------------------------------------------------------------- registro (bot)


class MensajeIn(Entrada):
    celular: str = Field(min_length=1, max_length=32)
    direccion: Literal["entrante", "saliente"]
    tipo: Literal["texto", "audio", "imagen", "interactivo", "plantilla", "sistema"]
    texto: str = ""
    wamid: str | None = Field(default=None, max_length=120)


def _purgar_vencidos(db: Session) -> None:
    dias = get_settings().conversaciones_retencion_dias
    db.execute(delete(MensajeConversacion).where(MensajeConversacion.created_at < ahora() - timedelta(days=dias)))


@canal.post("/mensajes", status_code=201)
def post_mensaje(datos: MensajeIn, actor: Actor = Depends(get_actor), db: Session = Depends(get_db)):
    """Registra un mensaje de la conversación. Mismo `wamid` = mismo registro (200)."""
    if actor.tipo != "servicio_bot":
        raise prohibido("Solo el servicio del bot registra mensajes (sin X-Canal-Celular).")
    try:
        celular = normalizar_celular(datos.celular)
    except AppError:
        raise invalido({"celular": "Celular inválido (E.164 o móvil colombiano de 10 dígitos)"}) from None
    wamid = (datos.wamid or "").strip() or None

    _purgar_vencidos(db)
    participante_id = db.execute(
        select(Participante.id).where(
            Participante.celular_normalizado == celular, Participante.estado != "eliminado"
        )
    ).scalar_one_or_none()
    valores = dict(
        celular_normalizado=celular, participante_id=participante_id, direccion=datos.direccion,
        tipo=datos.tipo, texto=datos.texto[:MAX_TEXTO], wamid=wamid,
    )
    ins = pg_insert(MensajeConversacion).values(id=uuid.uuid4(), **valores)
    if wamid:
        ins = ins.on_conflict_do_nothing(index_elements=["wamid"])
    nuevo_id = db.execute(ins.returning(MensajeConversacion.id)).scalar_one_or_none()
    status = 201
    if nuevo_id is None:  # el wamid ya estaba: respuesta idempotente
        nuevo_id = db.execute(
            select(MensajeConversacion.id).where(MensajeConversacion.wamid == wamid)
        ).scalar_one()
        status = 200
    db.commit()
    return JSONResponse({"data": {"id": str(nuevo_id)}}, status_code=status)


# --------------------------------------------------------------------------- lectura (administración)


def _nombres(db: Session, celulares: list[str]) -> dict[str, str]:
    """Nombre vigente de cada celular: cuenta operadora (coordinación) o participante."""
    if not celulares:
        return {}
    nombres: dict[str, str] = {}
    for cel, nombre in db.execute(
        select(Participante.celular_normalizado, Participante.nombre).where(
            Participante.celular_normalizado.in_(celulares), Participante.estado != "eliminado"
        )
    ):
        nombres[cel] = nombre
    for cel, nombre in db.execute(
        select(CuentaOperadora.celular_normalizado, CuentaOperadora.nombre).where(
            CuentaOperadora.celular_normalizado.in_(celulares), CuentaOperadora.activo.is_(True)
        )
    ):
        nombres[cel] = nombre
    return nombres


@router.get("/conversaciones")
def get_conversaciones(
    _actor: Actor = Depends(actor_admin),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Una fila por contacto, la del último mensaje más reciente primero."""
    M = MensajeConversacion
    ultimos = (
        select(M.celular_normalizado, M.texto, M.direccion, M.created_at)
        .distinct(M.celular_normalizado)
        .order_by(M.celular_normalizado, M.created_at.desc(), M.id.desc())
        .subquery()
    )
    totales = (
        select(M.celular_normalizado, func.count().label("total")).group_by(M.celular_normalizado).subquery()
    )
    stmt = (
        select(ultimos.c.celular_normalizado, ultimos.c.texto, ultimos.c.direccion, ultimos.c.created_at,
               totales.c.total)
        .join(totales, totales.c.celular_normalizado == ultimos.c.celular_normalizado)
        .order_by(ultimos.c.created_at.desc(), ultimos.c.celular_normalizado)
    )
    resultado = paginar(db, stmt, pag, lambda f: f, escalar=False)
    filas = resultado["data"]
    nombres = _nombres(db, [f.celular_normalizado for f in filas])
    resultado["data"] = [
        {
            "clave": clave_de_celular(f.celular_normalizado),
            "nombre": nombres.get(f.celular_normalizado, SIN_REGISTRO),
            "celular_enmascarado": enmascarar_celular(f.celular_normalizado),
            "ultimo_texto": _resumen(_ocultar_numero(f.texto, f.celular_normalizado)),
            "ultimo_at": _utc(f.created_at),
            "ultima_direccion": f.direccion,
            "total": int(f.total),
            "registrado": f.celular_normalizado in nombres,
        }
        for f in filas
    ]
    return resultado


def _celular_de_clave(db: Session, clave: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{24}", clave):
        raise no_encontrado("conversación")
    celulares = db.execute(select(MensajeConversacion.celular_normalizado).distinct()).scalars()
    for cel in celulares:
        if hmac.compare_digest(clave_de_celular(cel), clave):
            return cel
    raise no_encontrado("conversación")


@router.get("/conversaciones/{clave}/mensajes")
def get_mensajes(
    clave: str = Path(max_length=64),
    _actor: Actor = Depends(actor_admin),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Mensajes de una conversación en orden cronológico (el más antiguo primero)."""
    celular = _celular_de_clave(db, clave)
    M = MensajeConversacion
    stmt = select(M).where(M.celular_normalizado == celular).order_by(M.created_at.asc(), M.id.asc())
    return paginar(
        db, stmt, pag,
        lambda m: {
            "id": str(m.id),
            "direccion": m.direccion,
            "tipo": m.tipo,
            "texto": _ocultar_numero(m.texto, celular),
            "created_at": _utc(m.created_at),
        },
    )
