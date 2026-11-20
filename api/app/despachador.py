"""Despachador de avisos en modo webhook y limpieza periódica.

Corre en un hilo del proceso de la API (suficiente para el piloto). Con varias réplicas
es seguro: la reserva usa FOR UPDATE SKIP LOCKED.

Petición al bot:
    POST BOT_WEBHOOK_URL
    X-Brota-Evento-Id: <id del aviso>
    X-Brota-Firma: sha256=<HMAC-SHA256(BOT_WEBHOOK_SECRET, cuerpo)>
    {"id", "tipo", "intentos", "destino": {...}, "datos": {...}, ...}

Respuesta 2xx = enviado (opcionalmente {"id_externo": "wamid..."}). Otro código = reintento.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time

import httpx
from sqlalchemy import delete

from app.config import get_settings
from app.core.tipos import ahora
from app.db import get_sessionmaker
from app.models import OperacionIdempotente
from app.modulos.avisos import registrar_resultado_envio, reservar

log = logging.getLogger("brota.despachador")


def firmar(secreto: str, cuerpo: bytes) -> str:
    return "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()


def despachar_lote(cliente: httpx.Client, limite: int = 10) -> int:
    s = get_settings()
    with get_sessionmaker()() as db:
        avisos = reservar(db, limite)
        for a in avisos:
            cuerpo = json.dumps(a.model_dump(mode="json"), ensure_ascii=False).encode()
            try:
                r = cliente.post(
                    s.bot_webhook_url,
                    content=cuerpo,
                    headers={
                        "Content-Type": "application/json",
                        "X-Brota-Evento-Id": str(a.id),
                        "X-Brota-Firma": firmar(s.bot_webhook_secret, cuerpo),
                    },
                )
                if 200 <= r.status_code < 300:
                    id_externo = None
                    try:
                        id_externo = (r.json() or {}).get("id_externo")
                    except ValueError:
                        pass
                    registrar_resultado_envio(db, a.id, "enviado", id_externo, None, True)
                else:
                    registrar_resultado_envio(db, a.id, "fallido", None, f"HTTP {r.status_code}", r.status_code != 410)
            except httpx.HTTPError as e:
                registrar_resultado_envio(db, a.id, "fallido", None, f"{type(e).__name__}: {e}"[:500], True)
        return len(avisos)


def limpiar_idempotencia() -> None:
    with get_sessionmaker()() as db:
        db.execute(delete(OperacionIdempotente).where(OperacionIdempotente.expira_at < ahora()))
        db.commit()


class Despachador:
    def __init__(self) -> None:
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None

    def iniciar(self) -> None:
        self._hilo = threading.Thread(target=self._bucle, name="brota-despachador", daemon=True)
        self._hilo.start()

    def detener(self) -> None:
        self._parar.set()
        if self._hilo:
            self._hilo.join(timeout=5)

    def _bucle(self) -> None:
        s = get_settings()
        webhook = s.avisos_modo == "webhook" and bool(s.bot_webhook_url)
        if s.avisos_modo == "webhook" and not webhook:
            log.warning("AVISOS_MODO=webhook sin BOT_WEBHOOK_URL: los avisos quedan pendientes (modo pull).")
        ultima_limpieza = 0.0
        with httpx.Client(timeout=10) as cliente:
            while not self._parar.is_set():
                enviados = 0
                try:
                    if webhook:
                        enviados = despachar_lote(cliente)
                    if time.monotonic() - ultima_limpieza > 600:
                        limpiar_idempotencia()
                        ultima_limpieza = time.monotonic()
                except Exception:  # pragma: no cover - el bucle no debe morir
                    log.exception("Fallo en el despachador de avisos")
                self._parar.wait(0.2 if enviados else 2.0)
