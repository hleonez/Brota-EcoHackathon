"""Actividad (auditoría): lectura de `evento_dominio` para Administración.

`actor_tipo` toma los valores de `registrar_evento`: `operador`, `participante`, `servicio`
(token del bot sin celular), `no_registrado` (contacto de WhatsApp sin registro) y `sistema`
(sin actor). Los datos nunca devuelven un celular completo.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errores import invalido
from app.core.paginacion import Paginacion, paginacion, paginar
from app.core.seguridad import Actor, actor_admin
from app.core.tipos import InstanteEntrada, _utc
from app.db import get_db
from app.models import CuentaOperadora, EventoDominio, Participante
from app.modulos.conversaciones import enmascarar_celular

router = APIRouter(tags=["actividad (administración)"])

_CLAVE_TELEFONO = re.compile(r"celular|telefono|teléfono|phone|wa_id|whatsapp", re.IGNORECASE)
# Un número suelto de 10 a 15 dígitos (no parte de un UUID, un código o un decimal).
_NUMERO = re.compile(r"(?<![\w.\-+])\+?\d{10,15}(?![\w.\-])")


def _limpiar(valor: Any, clave: str = "") -> Any:
    """Enmascara celulares en los datos del evento (por nombre de campo o por forma)."""
    if isinstance(valor, dict):
        return {k: _limpiar(v, str(k)) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_limpiar(v, clave) for v in valor]
    if isinstance(valor, str):
        if _CLAVE_TELEFONO.search(clave) and re.sub(r"\D", "", valor):
            return enmascarar_celular(valor)
        return _NUMERO.sub(lambda m: enmascarar_celular(m.group(0)), valor)
    return valor


def _nombres_actores(db: Session, eventos: list[EventoDominio]) -> dict[tuple[str, uuid.UUID], str]:
    ids_operador = {e.actor_id for e in eventos if e.actor_tipo == "operador" and e.actor_id}
    ids_participante = {e.actor_id for e in eventos if e.actor_tipo == "participante" and e.actor_id}
    nombres: dict[tuple[str, uuid.UUID], str] = {}
    if ids_operador:
        for i, n in db.execute(select(CuentaOperadora.id, CuentaOperadora.nombre).where(CuentaOperadora.id.in_(ids_operador))):
            nombres[("operador", i)] = n
    if ids_participante:
        for i, n in db.execute(select(Participante.id, Participante.nombre).where(Participante.id.in_(ids_participante))):
            nombres[("participante", i)] = n
    return nombres


def _actor_nombre(e: EventoDominio, nombres: dict[tuple[str, uuid.UUID], str]) -> str | None:
    if e.actor_tipo in ("servicio", "servicio_bot"):
        return "Brisa"
    if e.actor_tipo == "sistema":
        return "Sistema"
    if e.actor_id is None:
        return None
    return nombres.get((e.actor_tipo, e.actor_id))


@router.get("/eventos")
def get_eventos(
    tipo: str | None = Query(None, max_length=60),
    desde: InstanteEntrada | None = Query(None),
    hasta: InstanteEntrada | None = Query(None),
    _actor: Actor = Depends(actor_admin),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Actividad del sistema, la más reciente primero."""
    if desde and hasta and hasta <= desde:
        raise invalido({"hasta": "Debe ser posterior a desde"})
    E = EventoDominio
    stmt = select(E).order_by(E.ocurrido_at.desc(), E.id.desc())
    if tipo:
        stmt = stmt.where(E.tipo == tipo)
    if desde:
        stmt = stmt.where(E.ocurrido_at >= desde)
    if hasta:
        stmt = stmt.where(E.ocurrido_at < hasta)
    resultado = paginar(db, stmt, pag, lambda e: e)
    eventos: list[EventoDominio] = resultado["data"]
    nombres = _nombres_actores(db, eventos)
    resultado["data"] = [
        {
            "id": str(e.id),
            "tipo": e.tipo,
            "ocurrido_at": _utc(e.ocurrido_at),
            "actor_tipo": e.actor_tipo,
            "actor_nombre": _actor_nombre(e, nombres),
            "solicitud_id": str(e.solicitud_id) if e.solicitud_id else None,
            "orden_id": str(e.orden_id) if e.orden_id else None,
            "pesaje_id": str(e.pesaje_id) if e.pesaje_id else None,
            "datos": _limpiar(e.datos or {}),
        }
        for e in eventos
    ]
    return resultado


@router.get("/eventos/tipos")
def get_tipos_evento(_actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)) -> dict[str, list[str]]:
    """Tipos de evento que existen, para el filtro del panel."""
    return {"data": list(db.execute(select(EventoDominio.tipo).distinct().order_by(EventoDominio.tipo)).scalars())}
