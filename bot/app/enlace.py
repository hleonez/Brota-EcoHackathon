"""Autoconexión: el túnel publica al bot y el bot registra solo su webhook en Meta.

Con `TUNEL_METRICAS_URL` (p. ej. http://tunel:2000), un bucle en segundo plano:
1. Lee la URL pública del túnel rápido de Cloudflare (`/quicktunnel` de sus métricas).
2. Espera a que esa URL responda (`/health` a través del túnel).
3. La registra como webhook de la app en Meta (`POST /{app-id}/subscriptions` con el token de app
   `app_id|app_secret`). Meta la verifica en ese momento contra `GET /webhook`.
4. Cada minuto revisa si el túnel cambió de URL (se reinició) y la vuelve a registrar.

Así `docker compose up` deja a Brisa recibiendo WhatsApp sin pegar URLs a mano. Los campos ya
suscritos en Meta se conservan; solo se asegura `messages`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import Settings

log = logging.getLogger("brota.bot.enlace")

OBJETO = "whatsapp_business_account"
TUNEL_RAPIDO = ".trycloudflare.com"


class ErrorEnlace(Exception):
    pass


class WebhookFijo(ErrorEnlace):
    """Meta ya apunta a una URL fija (producción) y el túnel local no la reemplaza."""

    def __init__(self, url: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.url = url


async def url_del_tunel(cliente: httpx.AsyncClient, metricas: str) -> str | None:
    r = await cliente.get(f"{metricas.rstrip('/')}/quicktunnel", timeout=5)
    host = (r.json() if r.status_code == 200 else {}).get("hostname")
    return f"https://{host}" if host else None


async def responde(cliente: httpx.AsyncClient, url: str, intentos: int = 12, espera: float = 5) -> bool:
    """El DNS de un túnel nuevo tarda unos segundos en propagarse."""
    for _ in range(intentos):
        try:
            if (await cliente.get(f"{url}/health", timeout=10)).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        await asyncio.sleep(espera)
    return False


async def _app_id(cliente: httpx.AsyncClient, s: Settings) -> str:
    if s.whatsapp_app_id:
        return s.whatsapp_app_id
    r = await cliente.get(
        f"{s.graph_base()}/debug_token",
        params={"input_token": s.whatsapp_token, "access_token": s.whatsapp_token}, timeout=15,
    )
    app_id = (r.json().get("data") or {}).get("app_id") if r.status_code == 200 else None
    if not app_id:
        raise ErrorEnlace("No pude saber el App ID: define WHATSAPP_APP_ID en bot/.env")
    return str(app_id)


async def registrar_webhook(cliente: httpx.AsyncClient, s: Settings, callback: str) -> bool:
    """Deja `callback` como webhook de la app. False si ya estaba registrado y activo."""
    if not (s.whatsapp_app_secret and s.whatsapp_verify_token):
        raise ErrorEnlace("Faltan WHATSAPP_APP_SECRET o WHATSAPP_VERIFY_TOKEN en bot/.env")
    app_id = await _app_id(cliente, s)
    token_app = {"access_token": f"{app_id}|{s.whatsapp_app_secret}"}
    url = f"{s.graph_base()}/{app_id}/subscriptions"
    r = await cliente.get(url, params=token_app, timeout=15)
    actual: dict[str, Any] = next((x for x in r.json().get("data", []) if x.get("object") == OBJETO), {}) if r.status_code == 200 else {}
    campos = {f.get("name") for f in actual.get("fields", []) if f.get("name")} | {"messages"}
    if actual.get("callback_url") == callback and actual.get("active"):
        return False
    anterior = actual.get("callback_url") or ""
    if anterior and TUNEL_RAPIDO in callback and TUNEL_RAPIDO not in anterior and not s.enlace_reemplazar_fijo:
        raise WebhookFijo(
            anterior,
            f"Meta envía los mensajes a {anterior} (URL fija, p. ej. producción): el túnel local no la "
            "reemplaza. Brisa local sigue sin WhatsApp real (usa /lab o el simulador). Para quitársela a "
            "producción a propósito: ENLACE_REEMPLAZAR_FIJO=true en bot/.env."
        )
    r = await cliente.post(
        url,
        data={
            "object": OBJETO, "callback_url": callback, "verify_token": s.whatsapp_verify_token,
            "fields": ",".join(sorted(campos)), **token_app,
        },
        timeout=30,
    )
    if r.status_code != 200 or not r.json().get("success"):
        mensaje = r.json().get("error", {}).get("message", r.text[:200]) if r.content else f"HTTP {r.status_code}"
        raise ErrorEnlace(f"Meta no aceptó el webhook: {mensaje}")
    return True


async def bucle(cliente: httpx.AsyncClient, s: Settings, estado: dict[str, Any]) -> None:
    """Mantiene el webhook de Meta apuntando a la URL vigente del túnel. `estado['url']` la expone."""
    registrada: str | None = None
    while True:
        try:
            publica = await url_del_tunel(cliente, s.tunel_metricas_url)
            if publica and publica != registrada:
                if not await responde(cliente, publica):
                    log.warning("El túnel %s todavía no responde; reintento en breve.", publica)
                else:
                    callback = f"{publica}/webhook"
                    cambio = await registrar_webhook(cliente, s, callback)
                    registrada = estado["url"] = publica
                    log.info("🌐 Brisa conectada en %s · webhook de Meta %s.", callback,
                             "actualizado" if cambio else "ya estaba al día")
        except asyncio.CancelledError:
            raise
        except WebhookFijo as e:
            if estado.get("webhook_fijo") != e.url:  # se avisa una vez, no cada 10 s
                log.warning("%s", e)
            estado["webhook_fijo"] = e.url
            await asyncio.sleep(300)
            continue
        except ErrorEnlace as e:
            log.error("%s", e)
        except Exception as e:  # noqa: BLE001 - el bucle no debe morir
            log.warning("Autoconexión: %s: %s", type(e).__name__, e)
        await asyncio.sleep(60 if registrada else 10)
