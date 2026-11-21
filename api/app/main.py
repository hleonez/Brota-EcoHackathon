"""API central de Brota."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.errores import registrar_manejadores
from app.despachador import Despachador
from app.modulos import (
    avisos,
    casos,
    configuracion,
    conversaciones,
    coordinacion,
    eventos,
    ia,
    identidad,
    piloto,
    pesajes,
    programa,
    puntos,
    reportes,
    residuos,
    sincronizacion,
    sistema,
    solicitudes,
    territorio,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

DESCRIPCION = """
API compartida por el bot de WhatsApp (Brisa), la tablet de coordinación y los paneles.

**Autenticación** (`Authorization: Bearer <token>`):
- Bot: `BOT_SERVICE_TOKEN` + cabecera `X-Canal-Celular` con el número verificado del residente.
- Operadores: token de `POST /v1/auth/sesiones` (usuario + PIN).

**Escrituras**: `POST`/`PATCH` de dominio exigen `Idempotency-Key`. Decimales como strings (`"9.000"`).
"""


def crear_app(iniciar_despachador: bool = True) -> FastAPI:
    s = get_settings()
    despachador = Despachador()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if iniciar_despachador:
            despachador.iniciar()
        yield
        if iniciar_despachador:
            despachador.detener()

    app = FastAPI(
        title="Brota API",
        version=sistema.CONTRATO_VERSION,
        description=DESCRIPCION,
        root_path=s.root_path,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        expose_headers=["X-Request-ID", "Idempotent-Replayed"],
    )

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        rid = request.headers.get("x-request-id") or f"req-{uuid.uuid4().hex[:12]}"
        request.state.request_id = rid[:64]
        resp = await call_next(request)
        resp.headers["X-Request-ID"] = request.state.request_id
        # Cabeceras de seguridad: nada de adivinar tipos, ni incrustar la API en marcos, ni filtrar
        # la URL de origen; las respuestas de /v1 traen datos personales y no se guardan en caché.
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        if "/v1/" in request.url.path:
            resp.headers.setdefault("Cache-Control", "no-store")
        if request.headers.get("x-forwarded-proto", request.url.scheme) == "https":
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return resp

    registrar_manejadores(app)
    app.include_router(sistema.salud)
    for m in (
        sistema,
        identidad,
        piloto,
        territorio,
        residuos,
        solicitudes,
        coordinacion,
        pesajes,
        puntos,
        avisos,
        reportes,
        configuracion,
        sincronizacion,
        ia,
        casos,
        conversaciones,
        eventos,
        programa,
    ):
        app.include_router(m.router, prefix="/v1")
    app.include_router(avisos.canal, prefix="/v1")
    app.include_router(conversaciones.canal, prefix="/v1")
    return app


app = crear_app()
