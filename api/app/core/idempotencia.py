"""Idempotency-Key: misma clave + mismo cuerpo = misma respuesta, sin repetir la escritura.

La fila de la clave se inserta en la misma transacción que la escritura. Dos peticiones
simultáneas con la misma clave se serializan por el índice único: la segunda espera al commit
de la primera y luego devuelve la respuesta guardada.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errores import AppError
from app.core.seguridad import Actor
from app.core.tipos import ahora
from app.models import OperacionIdempotente

Resultado = tuple[int, dict[str, Any]]


def huella(cuerpo: Any) -> str:
    return hashlib.sha256(json.dumps(cuerpo, sort_keys=True, default=str).encode()).hexdigest()


def ejecutar_idempotente(
    db: Session, actor_clave: str, ruta: str, clave: str, cuerpo: Any, fn: Callable[[], Resultado]
) -> tuple[Resultado, bool]:
    """Devuelve ((codigo_http, cuerpo_json), repetida)."""
    h = huella(cuerpo)
    expira = ahora() + timedelta(hours=get_settings().idempotencia_retencion_horas)
    for _ in range(2):
        ins = (
            pg_insert(OperacionIdempotente)
            .values(actor=actor_clave, ruta=ruta, clave=clave, huella=h, estado="en_proceso", expira_at=expira)
            .on_conflict_do_nothing(index_elements=["actor", "ruta", "clave"])
            .returning(OperacionIdempotente.id)
        )
        op_id = db.execute(ins).scalar_one_or_none()
        if op_id is not None:
            break
        previa = db.execute(
            select(OperacionIdempotente).where(
                OperacionIdempotente.actor == actor_clave,
                OperacionIdempotente.ruta == ruta,
                OperacionIdempotente.clave == clave,
            )
        ).scalar_one()
        if previa.expira_at <= ahora():
            db.execute(delete(OperacionIdempotente).where(OperacionIdempotente.id == previa.id))
            continue
        db.rollback()
        if previa.huella != h:
            raise AppError(
                409,
                "IDEMPOTENCY_CONFLICT",
                "Esta Idempotency-Key ya se usó con otro contenido. Genera una clave nueva para otra operación.",
            )
        return (previa.codigo_http or 200, previa.respuesta or {}), True
    else:  # pragma: no cover - solo si la fila expirada reaparece en carrera
        raise AppError(409, "IDEMPOTENCY_CONFLICT", "Operación en curso con la misma clave.")

    try:
        codigo, respuesta = fn()
    except Exception:
        db.rollback()
        raise
    db.execute(
        update(OperacionIdempotente)
        .where(OperacionIdempotente.id == op_id)
        .values(estado="completada", codigo_http=codigo, respuesta=respuesta)
    )
    db.commit()
    return (codigo, respuesta), False


def clave_de(request: Request) -> str:
    clave = (request.headers.get("idempotency-key") or "").strip()
    if not 1 <= len(clave) <= 128:
        raise AppError(
            400,
            "IDEMPOTENCY_KEY_REQUIRED",
            "Envía la cabecera Idempotency-Key (1 a 128 caracteres) para esta escritura.",
        )
    return clave


def escritura(
    request: Request,
    db: Session,
    actor: Actor,
    cuerpo: BaseModel | dict[str, Any] | None,
    fn: Callable[[], BaseModel],
    status: int = 200,
) -> JSONResponse:
    """Envuelve una escritura de dominio con Idempotency-Key y la respuesta `{"data": ...}`."""
    clave = clave_de(request)
    ruta = f"{request.method} {request.scope.get('path', request.url.path)}"
    if isinstance(cuerpo, BaseModel):
        datos_cuerpo: Any = cuerpo.model_dump(mode="json")
    else:
        datos_cuerpo = cuerpo or {}

    def _run() -> Resultado:
        return status, {"data": fn().model_dump(mode="json")}

    (codigo, resp), repetida = ejecutar_idempotente(db, actor.clave, ruta, clave, datos_cuerpo, _run)
    headers = {"Idempotent-Replayed": "true"} if repetida else None
    return JSONResponse(resp, status_code=codigo, headers=headers)
