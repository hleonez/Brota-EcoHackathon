"""Identidad del actor.

Dos formas de autenticarse (cabecera `Authorization: Bearer <token>`):

1. **Bot de WhatsApp** — `BOT_SERVICE_TOKEN`. Si además envía `X-Canal-Celular`, actúa en nombre
   de ese contacto (ya verificado por el adaptador de WhatsApp). Sin esa cabecera actúa como
   servicio (p. ej. para reservar avisos).
2. **Cuenta operadora** (tablet de coordinación, paneles) — JWT emitido por `POST /v1/auth/sesiones`
   con usuario y PIN.

El cuerpo de una petición nunca concede rol ni identidad.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Literal

import jwt
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errores import AppError, prohibido
from app.core.tipos import ahora
from app.db import get_db
from app.models import CuentaOperadora, Participante

TipoActor = Literal["servicio_bot", "participante", "no_registrado", "operador"]


@dataclass
class Actor:
    tipo: TipoActor
    canal: str
    participante_id: uuid.UUID | None = None
    celular: str | None = None
    cuenta_id: uuid.UUID | None = None
    nombre: str | None = None
    permisos: list[tuple[str, uuid.UUID | None]] = field(default_factory=list)

    @property
    def clave(self) -> str:
        """Ámbito de idempotencia y de referencias locales."""
        if self.tipo == "operador":
            return f"op:{self.cuenta_id}"
        if self.celular:
            return f"wa:{self.celular}"
        return f"{self.tipo}"

    @property
    def es_operador(self) -> bool:
        return self.tipo == "operador"

    def tiene_rol(self, rol: str) -> bool:
        return any(r == rol for r, _ in self.permisos)

    @property
    def es_admin(self) -> bool:
        return self.tiene_rol("admin")

    @property
    def es_fundacion(self) -> bool:
        return self.tiene_rol("fundacion")

    @property
    def gremios_coordinados(self) -> set[uuid.UUID]:
        return {g for r, g in self.permisos if r == "coordinacion" and g is not None}

    def coordina(self, gremio_id: uuid.UUID) -> bool:
        return gremio_id in self.gremios_coordinados

    def exigir_coordinacion(self, gremio_id: uuid.UUID) -> None:
        if not self.coordina(gremio_id):
            raise prohibido("Solo la coordinación de este gremio puede hacer esta acción.")

    @property
    def tipo_publico(self) -> str:
        return {"servicio_bot": "servicio", "no_registrado": "no_registrado"}.get(self.tipo, self.tipo)

    @property
    def actor_id(self) -> uuid.UUID | None:
        return self.cuenta_id or self.participante_id


# --------------------------------------------------------------------------- celular

_CELULAR = re.compile(r"^[1-9]\d{7,14}$")


def normalizar_celular(valor: str) -> str:
    """E.164 con '+'. Acepta el `wa_id` de WhatsApp (573001234567) o un móvil colombiano de 10 dígitos."""
    digitos = re.sub(r"[^\d]", "", valor or "")
    if len(digitos) == 10 and digitos.startswith("3"):
        digitos = "57" + digitos
    if not _CELULAR.match(digitos):
        raise AppError(400, "BAD_REQUEST", "Celular inválido en X-Canal-Celular.", {"X-Canal-Celular": "Formato E.164"})
    return "+" + digitos


# --------------------------------------------------------------------------- PIN


def hash_pin(pin: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(pin.encode(), salt=sal, n=2**14, r=8, p=1)
    return "scrypt$" + base64.b64encode(sal).decode() + "$" + base64.b64encode(h).decode()


def verificar_pin(pin: str, guardado: str | None) -> bool:
    if not guardado or not guardado.startswith("scrypt$"):
        return False
    _, sal_b64, h_b64 = guardado.split("$")
    h = hashlib.scrypt(pin.encode(), salt=base64.b64decode(sal_b64), n=2**14, r=8, p=1)
    return hmac.compare_digest(h, base64.b64decode(h_b64))


# --------------------------------------------------------------------------- JWT


def _secreto() -> str:
    s = get_settings().jwt_secret
    if len(s) < 32:
        raise AppError(503, "AUTH_NOT_CONFIGURED", "JWT_SECRET no está configurado (mínimo 32 caracteres).")
    return s


def emitir_token(cuenta_id: uuid.UUID) -> tuple[str, int]:
    minutos = get_settings().jwt_minutos
    exp = ahora() + timedelta(minutes=minutos)
    token = jwt.encode({"sub": str(cuenta_id), "typ": "operador", "exp": exp}, _secreto(), algorithm="HS256")
    return token, minutos * 60


def _no_autenticado(msg: str = "Falta autenticación.") -> AppError:
    return AppError(401, "UNAUTHORIZED", msg)


def _bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise _no_autenticado()
    return auth[7:].strip()


def get_actor(request: Request, db: Session = Depends(get_db)) -> Actor:
    token = _bearer(request)
    s = get_settings()

    if s.bot_service_token and hmac.compare_digest(token, s.bot_service_token):
        celular_hdr = request.headers.get("x-canal-celular")
        if not celular_hdr:
            return Actor(tipo="servicio_bot", canal="whatsapp")
        celular = normalizar_celular(celular_hdr)
        p = db.execute(
            select(Participante).where(
                Participante.celular_normalizado == celular, Participante.estado != "eliminado"
            )
        ).scalar_one_or_none()
        if p is None:
            return Actor(tipo="no_registrado", canal="whatsapp", celular=celular)
        return Actor(tipo="participante", canal="whatsapp", celular=celular, participante_id=p.id, nombre=p.nombre)

    try:
        datos = jwt.decode(token, _secreto(), algorithms=["HS256"], options={"require": ["exp", "sub"]})
    except jwt.ExpiredSignatureError:
        raise _no_autenticado("La sesión expiró. Ingresa de nuevo.") from None
    except jwt.PyJWTError:
        raise _no_autenticado("Credencial inválida.") from None
    if datos.get("typ") != "operador":
        raise _no_autenticado("Credencial inválida.")
    cuenta = db.get(CuentaOperadora, uuid.UUID(datos["sub"]))
    if cuenta is None or not cuenta.activo:
        raise _no_autenticado("La cuenta no está activa.")
    return Actor(
        tipo="operador",
        canal="tablet",
        cuenta_id=cuenta.id,
        nombre=cuenta.nombre,
        permisos=[(p.rol, p.gremio_id) for p in cuenta.permisos],
    )


# --------------------------------------------------------------------------- dependencias por tipo


def actor_operador(actor: Actor = Depends(get_actor)) -> Actor:
    if not actor.es_operador:
        raise prohibido("Esta acción es solo para cuentas operadoras.")
    return actor


def actor_participante(actor: Actor = Depends(get_actor)) -> Actor:
    if actor.tipo == "no_registrado":
        raise AppError(403, "NOT_REGISTERED", "El contacto aún no está registrado.")
    if actor.tipo != "participante":
        raise prohibido("Esta acción es para residentes o negocios registrados.")
    return actor


def actor_bot(actor: Actor = Depends(get_actor)) -> Actor:
    if actor.tipo not in ("servicio_bot", "participante", "no_registrado"):
        raise prohibido("Esta acción es solo para el servicio del bot.")
    return actor


def actor_admin(actor: Actor = Depends(actor_operador)) -> Actor:
    if not actor.es_admin:
        raise prohibido("Se requiere capacidad de administración.")
    return actor
