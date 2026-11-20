"""M03b · Fichas de residuos: qué se recibe, cómo prepararlo y qué preguntar antes de pedir.

Brisa las usa para enseñar antes de crear una solicitud; la solicitud guarda lo que el vecino
declaró (`solicitud_residuo`) y la coordinación lo ve en su bandeja. El catálogo decide si algo se
recibe; la IA (fase 2) solo propone qué residuo mencionó la persona.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.seguridad import Actor, get_actor
from app.core.tipos import Entrada, Salida
from app.db import get_db
from app.models import Residuo, SolicitudResiduo, TipoServicio

router = APIRouter(tags=["residuos"])


class OpcionOut(Salida):
    id: str
    texto: str
    resultado: Literal["listo", "preparar", "no", "revision"]
    consejo: str | None = None


class VerificacionOut(Salida):
    id: str
    pregunta: str
    opciones: list[OpcionOut]


class ResiduoOut(Salida):
    id: uuid.UUID
    codigo: str
    nombre: str
    emoji: str
    categoria: Literal["reciclable", "organico", "peligroso", "no_aprovechable"]
    acepta: Literal["si", "no", "revision"]
    gremio_id: uuid.UUID | None
    tipo_servicio_id: uuid.UUID | None
    sinonimos: list[str]
    preparacion: str | None
    evitar: str | None
    alternativa: str | None
    verificaciones: list[VerificacionOut]
    en_menu: bool
    orden: int


class ResiduoDeclaradoIn(Entrada):
    residuo_id: uuid.UUID
    estado: Literal["listo", "revision"] = "listo"
    respuestas: dict[str, str] = Field(default_factory=dict, max_length=10)
    cantidad: str | None = Field(default=None, max_length=80)
    fuente: Literal["lista", "texto", "foto", "audio"] = "lista"


class ResiduoSolicitudOut(Salida):
    residuo_id: uuid.UUID
    codigo: str
    nombre: str
    emoji: str
    estado: Literal["listo", "revision"]
    cantidad: str | None
    fuente: str
    chequeos: list[str] = Field(description="Respuestas del vecino, legibles: «Seco y limpio: Sí, está listo»")


def servicio_por_gremio(db: Session) -> dict[uuid.UUID, uuid.UUID]:
    """Gremio → su tipo de servicio activo (reciclables → Asorescatar, orgánicos → huerta)."""
    salida: dict[uuid.UUID, uuid.UUID] = {}
    for t in db.execute(select(TipoServicio).where(TipoServicio.activo.is_(True)).order_by(TipoServicio.codigo)).scalars():
        salida.setdefault(t.gremio_id, t.id)
    return salida


def residuo_out(r: Residuo, servicios: dict[uuid.UUID, uuid.UUID]) -> ResiduoOut:
    return ResiduoOut(
        id=r.id,
        codigo=r.codigo,
        nombre=r.nombre,
        emoji=r.emoji,
        categoria=r.categoria,  # type: ignore[arg-type]
        acepta=r.acepta,  # type: ignore[arg-type]
        gremio_id=r.gremio_id,
        tipo_servicio_id=servicios.get(r.gremio_id) if r.gremio_id else None,
        sinonimos=list(r.sinonimos or []),
        preparacion=r.preparacion,
        evitar=r.evitar,
        alternativa=r.alternativa,
        verificaciones=[VerificacionOut.model_validate(v) for v in (r.verificaciones or [])],
        en_menu=r.en_menu,
        orden=r.orden,
    )


def chequeos_legibles(r: Residuo, respuestas: dict[str, str]) -> list[str]:
    salida = []
    for v in r.verificaciones or []:
        elegida = respuestas.get(v["id"])
        if elegida is None:
            continue
        opcion: dict[str, Any] = next((o for o in v["opciones"] if o["id"] == elegida), {"texto": elegida})
        salida.append(f"{v['pregunta']} {opcion['texto']}")
    return salida


def residuo_solicitud_out(sr: SolicitudResiduo) -> ResiduoSolicitudOut:
    r = sr.residuo
    return ResiduoSolicitudOut(
        residuo_id=r.id,
        codigo=r.codigo,
        nombre=r.nombre,
        emoji=r.emoji,
        estado=sr.estado,  # type: ignore[arg-type]
        cantidad=sr.cantidad,
        fuente=sr.fuente,
        chequeos=chequeos_legibles(r, sr.respuestas or {}),
    )


@router.get("/residuos")
def get_residuos(actor: Actor = Depends(get_actor), db: Session = Depends(get_db)) -> dict:
    """Catálogo vigente de fichas (pocas decenas; sin paginar)."""
    servicios = servicio_por_gremio(db)
    filas = db.execute(
        select(Residuo).where(Residuo.activo.is_(True)).order_by(Residuo.orden, Residuo.nombre)
    ).scalars()
    return {"data": [residuo_out(r, servicios).model_dump(mode="json") for r in filas]}
