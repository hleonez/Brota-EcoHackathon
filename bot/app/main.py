"""Brisa: webhook de WhatsApp (Meta) conectado a la API de Brota."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app import avisos, laboratorio
from app.brota import Brota
from app.config import Settings, get_settings
from app.conversacion import Brisa
from app.whatsapp import Entrante, ErrorWhatsApp, WhatsApp, firma_valida, leer_webhook

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # el bucle de avisos consulta cada pocos segundos
log = logging.getLogger("brota.bot")

TOKEN_VENCIDO = (
    "Meta rechazó el token de WhatsApp (190): venció o se regeneró. Genera uno nuevo en "
    "developers.facebook.com → tu app → WhatsApp → Configuración de la API, ponlo en WHATSAPP_TOKEN "
    "de bot/.env y reinicia el bot."
)


class SinSondeoDelLab(logging.Filter):
    """La página del laboratorio consulta cada segundo; no llenar la consola con eso."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "/lab/" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(SinSondeoDelLab())


class Vistos:
    """Recuerda los últimos wamid para ignorar reenvíos del webhook de Meta."""

    def __init__(self, maximo: int = 5000) -> None:
        self.maximo = maximo
        self._d: OrderedDict[str, None] = OrderedDict()

    def nuevo(self, wamid: str) -> bool:
        if wamid in self._d:
            return False
        self._d[wamid] = None
        if len(self._d) > self.maximo:
            self._d.popitem(last=False)
        return True


def crear_app(settings: Settings | None = None, cliente: httpx.AsyncClient | None = None,
              procesar_en_linea: bool = False) -> FastAPI:
    """`procesar_en_linea=True` atiende el mensaje antes de responder al webhook (útil en pruebas)."""
    s = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        propio = cliente is None
        http = cliente or httpx.AsyncClient()
        app.state.wa = WhatsApp(s, http)
        app.state.lab = laboratorio.Laboratorio() if s.lab_activo else None
        app.state.wa.lab = app.state.lab
        app.state.api = Brota(s, http)
        app.state.brisa = Brisa(app.state.wa, app.state.api)
        app.state.vistos = Vistos()
        app.state.candados = {}
        app.state.tareas = set()
        tarea_avisos = None
        if s.avisos_activos:
            tarea_avisos = asyncio.create_task(avisos.bucle(app.state.wa, app.state.api, s))
        _advertencias(s)
        yield
        if tarea_avisos:
            tarea_avisos.cancel()
        if propio:
            await http.aclose()

    app = FastAPI(title="Brisa · bot de WhatsApp de Brota", lifespan=lifespan)

    async def _atender(m: Entrante) -> None:
        candado = app.state.candados.setdefault(m.de, asyncio.Lock())
        async with candado:  # mensajes del mismo vecino, en orden
            if app.state.lab is not None:
                app.state.lab.entrante(m)
            try:
                await app.state.brisa.atender(m)
            except ErrorWhatsApp as e:
                if e.codigo == 190:
                    log.error(TOKEN_VENCIDO)
                else:
                    log.exception("Error atendiendo %s", m.wamid)
            except Exception:  # noqa: BLE001
                log.exception("Error atendiendo %s", m.wamid)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/webhook")
    async def verificar(
        modo: str = Query("", alias="hub.mode"),
        token: str = Query("", alias="hub.verify_token"),
        reto: str = Query("", alias="hub.challenge"),
    ):
        if modo == "subscribe" and s.whatsapp_verify_token and token == s.whatsapp_verify_token:
            return PlainTextResponse(reto)
        return PlainTextResponse("Token de verificación inválido", status_code=403)

    @app.post("/webhook")
    async def recibir(request: Request):
        cuerpo = await request.body()
        if not firma_valida(s.whatsapp_app_secret, cuerpo, request.headers.get("x-hub-signature-256")):
            log.warning("Webhook con firma inválida; descartado.")
            return JSONResponse({"error": "firma inválida"}, status_code=401)
        try:
            payload = json.loads(cuerpo)
        except ValueError:
            return JSONResponse({"error": "JSON inválido"}, status_code=400)
        for m in leer_webhook(payload):
            if not app.state.vistos.nuevo(m.wamid):
                continue
            if procesar_en_linea:
                await _atender(m)
            else:
                t = asyncio.create_task(_atender(m))
                app.state.tareas.add(t)
                t.add_done_callback(app.state.tareas.discard)
        return {"status": "ok"}  # responder rápido: Meta reintenta si tardamos

    @app.get("/dev/mensajes")
    async def mensajes_dry_run(para: str | None = None):
        """Solo con WHATSAPP_DRY_RUN=true: lo que Brisa habría enviado."""
        if not s.whatsapp_dry_run:
            return JSONResponse({"error": "Disponible solo en modo dry-run"}, status_code=404)
        bandeja = app.state.wa.bandeja
        return {"data": [b for b in bandeja if para is None or b.get("to") == para]}

    if s.lab_activo:
        laboratorio.montar(app, _atender)

    return app


def _advertencias(s: Settings) -> None:
    if not s.bot_service_token:
        log.warning("Falta BOT_SERVICE_TOKEN: la API de Brota rechazará las llamadas.")
    if not s.whatsapp_app_secret:
        log.warning("Falta WHATSAPP_APP_SECRET: todos los webhooks se rechazarán.")
    if not s.whatsapp_dry_run and not (s.whatsapp_token and s.whatsapp_phone_number_id):
        log.warning("Faltan WHATSAPP_TOKEN / WHATSAPP_PHONE_NUMBER_ID (o activa WHATSAPP_DRY_RUN=true).")
    if s.lab_activo:
        log.info("Laboratorio activo: abre http://localhost:%s/lab (solo desde esta máquina).", s.port)
    if s.whatsapp_dry_run:
        log.info("Modo dry-run: no se envía nada a Meta; revisa GET /dev/mensajes.")


app = crear_app()
