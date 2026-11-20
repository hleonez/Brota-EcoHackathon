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
    coordinacion,
    ia,
    identidad,
    piloto,
    pesajes,
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
    ):
        app.include_router(m.router, prefix="/v1")
    app.include_router(avisos.canal, prefix="/v1")
    return app


app = crear_app()
