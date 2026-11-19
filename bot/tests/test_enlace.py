"""Autoconexión: la URL del túnel se registra sola como webhook en Meta."""

from __future__ import annotations

import asyncio
from urllib.parse import parse_qs

import httpx
import pytest

from app import enlace
from tests.test_bot import ajustes

PUBLICA = "https://tres-palabras-raras.trycloudflare.com"


class MetaFalsa:
    def __init__(self, callback_actual: str | None) -> None:
        self.callback_actual = callback_actual
        self.registros: list[dict[str, list[str]]] = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        u = req.url
        if u.host == "tunel":
            return httpx.Response(200, json={"hostname": PUBLICA.removeprefix("https://")})
        if u.host.endswith("trycloudflare.com"):
            return httpx.Response(200, json={"status": "ok"})
        assert u.path.endswith("/977/subscriptions")
        assert u.params.get("access_token") == "977|secreto" or b"access_token=977%7Csecreto" in req.content
        if req.method == "GET":
            return httpx.Response(200, json={"data": [{
                "object": "whatsapp_business_account", "callback_url": self.callback_actual, "active": True,
                "fields": [{"name": "messages"}, {"name": "account_alerts"}],
            }]})
        self.registros.append(parse_qs(req.content.decode()))
        return httpx.Response(200, json={"success": True})


def _correr(meta: MetaFalsa) -> dict:
    s = ajustes(whatsapp_app_id="977", whatsapp_app_secret="secreto", whatsapp_verify_token="verificar",
                tunel_metricas_url="http://tunel:2000")
    estado: dict = {"url": None}

    async def una_vuelta():
        async with httpx.AsyncClient(transport=httpx.MockTransport(meta)) as cli:
            tarea = asyncio.create_task(enlace.bucle(cli, s, estado))
            for _ in range(50):
                await asyncio.sleep(0.01)
                if estado["url"]:
                    break
            tarea.cancel()

    asyncio.run(una_vuelta())
    return estado


def test_registra_la_url_nueva_del_tunel_y_conserva_los_campos():
    meta = MetaFalsa(callback_actual="https://vieja.trycloudflare.com/webhook")
    assert _correr(meta)["url"] == PUBLICA
    (registro,) = meta.registros
    assert registro["callback_url"] == [f"{PUBLICA}/webhook"]
    assert registro["verify_token"] == ["verificar"]
    assert registro["fields"] == ["account_alerts,messages"]
    assert registro["object"] == ["whatsapp_business_account"]


def test_si_ya_estaba_registrada_no_la_toca():
    meta = MetaFalsa(callback_actual=f"{PUBLICA}/webhook")
    assert _correr(meta)["url"] == PUBLICA and meta.registros == []


def test_sin_app_secret_no_intenta_registrar():
    s = ajustes(whatsapp_app_secret="", whatsapp_app_id="977")

    async def correr():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))) as cli:
            await enlace.registrar_webhook(cli, s, f"{PUBLICA}/webhook")

    with pytest.raises(enlace.ErrorEnlace, match="WHATSAPP_APP_SECRET"):
        asyncio.run(correr())
