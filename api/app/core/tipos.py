"""Tipos comunes: decimales como strings con punto, fechas con zona y modelos base."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    PlainSerializer,
)

_DECIMAL = re.compile(r"^\d{1,9}(\.\d{1,4})?$")

KG_Q = Decimal("0.001")
PUNTOS_Q = Decimal("0.01")
PRECIO_Q = Decimal("0.0001")


def _a_decimal(v: Any) -> Decimal:
    if not isinstance(v, str):
        raise ValueError('Envía un string decimal con punto, por ejemplo "9.000"')
    if not _DECIMAL.match(v):
        raise ValueError('Formato decimal inválido: usa dígitos y punto, por ejemplo "12.5"')
    return Decimal(v)


DecimalEntrada = Annotated[Decimal, BeforeValidator(_a_decimal)]


def _a_kg(v: Any) -> Decimal:
    d = _a_decimal(v)
    if d.as_tuple().exponent < -3:  # type: ignore[operator]
        raise ValueError("Máximo 3 decimales para kilos o cantidades")
    return d


KgEntrada = Annotated[Decimal, BeforeValidator(_a_kg)]


def _fmt(q: Decimal):
    def f(d: Decimal | None) -> str | None:
        return None if d is None else str(Decimal(d).quantize(q, rounding=ROUND_HALF_UP))

    return f


KgSalida = Annotated[Decimal, PlainSerializer(_fmt(KG_Q), return_type=str)]
PuntosSalida = Annotated[Decimal, PlainSerializer(_fmt(PUNTOS_Q), return_type=str)]
PrecioSalida = Annotated[Decimal, PlainSerializer(_fmt(PRECIO_Q), return_type=str)]


def _utc(d: datetime | None) -> str | None:
    if d is None:
        return None
    return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


Instante = Annotated[datetime, PlainSerializer(_utc, return_type=str)]
InstanteEntrada = AwareDatetime


class Entrada(BaseModel):
    """Cuerpos de escritura: los campos desconocidos se rechazan."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Salida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def zona(nombre: str) -> ZoneInfo:
    return ZoneInfo(nombre)


def redondear_kg(d: Decimal) -> Decimal:
    return d.quantize(KG_Q, rounding=ROUND_HALF_UP)
