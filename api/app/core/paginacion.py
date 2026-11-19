from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select
from sqlalchemy.orm import Session

T = TypeVar("T")


class Paginacion(BaseModel):
    limit: int
    offset: int


def paginacion(
    limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)
) -> Paginacion:
    return Paginacion(limit=limit, offset=offset)


def paginar(
    db: Session, stmt: Select[Any], pag: Paginacion, convertir: Callable[[Any], Any], escalar: bool = True
) -> dict[str, Any]:
    """Ejecuta `stmt` con limit+1 y arma la respuesta de lista del contrato."""
    res = db.execute(stmt.limit(pag.limit + 1).offset(pag.offset))
    filas: Sequence[Any] = res.scalars().all() if escalar else res.all()
    has_more = len(filas) > pag.limit
    filas = filas[: pag.limit]
    return {
        "data": [convertir(f) for f in filas],
        "pagination": {"limit": pag.limit, "offset": pag.offset, "has_more": has_more},
    }
