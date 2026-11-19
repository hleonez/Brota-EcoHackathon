"""Cliente de la WhatsApp Cloud API (Meta): firma, lectura del webhook y envío de mensajes."""

from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import Settings

log = logging.getLogger("brota.bot.whatsapp")


# --------------------------------------------------------------------------- firma


def firma_valida(app_secret: str, cuerpo: bytes, cabecera: str | None) -> bool:
    """Valida `X-Hub-Signature-256: sha256=<hmac>` con el App Secret de la app de Meta."""
    if not app_secret or not cabecera or not cabecera.startswith("sha256="):
        return False
    esperado = "sha256=" + hmac.new(app_secret.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, cabecera)


# --------------------------------------------------------------------------- mensajes entrantes


@dataclass
class Entrante:
    """Mensaje de un vecino, normalizado desde el webhook de Meta."""

    wamid: str
    de: str  # wa_id, p. ej. 573001112233
    tipo: str  # text | interactive | audio | image | ...
    texto: str | None = None
    respuesta_id: str | None = None  # id del botón o fila de lista elegida
    respuesta_titulo: str | None = None
    nombre_perfil: str | None = None
    media_id: str | None = None


def leer_webhook(payload: dict[str, Any]) -> list[Entrante]:
    """Extrae los mensajes del webhook. Ignora estados (entregado, leído) y otros campos."""
    salida: list[Entrante] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            valor = change.get("value", {})
            nombres = {c.get("wa_id"): c.get("profile", {}).get("name") for c in valor.get("contacts", [])}
            for m in valor.get("messages", []):
                e = Entrante(wamid=m["id"], de=m["from"], tipo=m.get("type", ""), nombre_perfil=nombres.get(m["from"]))
                if e.tipo == "text":
                    e.texto = m.get("text", {}).get("body", "")
                elif e.tipo == "interactive":
                    i = m.get("interactive", {})
                    r = i.get("button_reply") or i.get("list_reply") or {}
                    e.respuesta_id, e.respuesta_titulo = r.get("id"), r.get("title")
                elif e.tipo == "button":  # respuesta rápida de una plantilla
                    e.respuesta_id = m.get("button", {}).get("payload")
                    e.respuesta_titulo = m.get("button", {}).get("text")
                elif e.tipo in ("audio", "image", "video", "document", "sticker"):
                    e.media_id = m.get(e.tipo, {}).get("id")
                salida.append(e)
    return salida


# --------------------------------------------------------------------------- envío


class ErrorWhatsApp(Exception):
    def __init__(self, codigo: int | None, mensaje: str) -> None:
        super().__init__(f"{codigo}: {mensaje}")
        self.codigo = codigo
        self.mensaje = mensaje

    @property
    def fuera_de_ventana(self) -> bool:
        """131047: han pasado más de 24 h desde el último mensaje del vecino."""
        return self.codigo == 131047


@dataclass
class Boton:
    id: str
    titulo: str  # máximo 20 caracteres


@dataclass
class Fila:
    id: str
    titulo: str  # máximo 24 caracteres
    descripcion: str | None = None


@dataclass
class WhatsApp:
    """Envía mensajes. En `dry_run` no llama a Meta y guarda lo enviado en `bandeja`."""

    settings: Settings
    cliente: httpx.AsyncClient
    bandeja: list[dict[str, Any]] = field(default_factory=list)
    # Laboratorio (solo desarrollo): registra las conversaciones y se queda con los mensajes
    # a celulares simulados, que nunca salen a Meta. Ver app/laboratorio.py.
    lab: Any = None

    @property
    def dry_run(self) -> bool:
        return self.settings.whatsapp_dry_run

    async def _post(self, cuerpo: dict[str, Any]) -> str:
        a = cuerpo.get("to")
        if self.lab is not None and a and self.lab.simulado(a):
            return self.lab.saliente(cuerpo)
        wamid = await self._enviar(cuerpo)
        if self.lab is not None and a:
            self.lab.saliente(cuerpo, wamid)
        return wamid

    async def _enviar(self, cuerpo: dict[str, Any]) -> str:
        if self.dry_run:
            wamid = f"wamid.dryrun.{len(self.bandeja) + 1}"
            self.bandeja.append({"id": wamid, **cuerpo})
            del self.bandeja[:-200]
            log.info("[dry-run] → %s: %s", cuerpo.get("to"), _resumen(cuerpo))
            return wamid
        s = self.settings
        r = await self.cliente.post(
            f"{s.graph_base()}/{s.whatsapp_phone_number_id}/messages",
            json={"messaging_product": "whatsapp", **cuerpo},
            headers={"Authorization": f"Bearer {s.whatsapp_token}"},
            timeout=15,
        )
        datos = r.json() if r.content else {}
        if r.status_code >= 400:
            err = datos.get("error", {})
            raise ErrorWhatsApp(err.get("code"), err.get("message", f"HTTP {r.status_code}"))
        mensajes = datos.get("messages") or [{}]
        return mensajes[0].get("id", "")

    async def texto(self, a: str, cuerpo: str, vista_previa: bool = False) -> str:
        return await self._post(
            {"to": a, "type": "text", "text": {"body": cuerpo[:4096], "preview_url": vista_previa}}
        )

    async def botones(self, a: str, cuerpo: str, botones: list[Boton], pie: str | None = None) -> str:
        interactive: dict[str, Any] = {
            "type": "button",
            "body": {"text": cuerpo[:1024]},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b.id, "title": b.titulo[:20]}} for b in botones[:3]
                ]
            },
        }
        if pie:
            interactive["footer"] = {"text": pie[:60]}
        return await self._post({"to": a, "type": "interactive", "interactive": interactive})

    async def lista(self, a: str, cuerpo: str, boton: str, titulo_seccion: str, filas: list[Fila]) -> str:
        rows = []
        for f in filas[:10]:
            row = {"id": f.id, "title": f.titulo[:24]}
            if f.descripcion:
                row["description"] = f.descripcion[:72]
            rows.append(row)
        return await self._post(
            {
                "to": a,
                "type": "interactive",
                "interactive": {
                    "type": "list",
                    "body": {"text": cuerpo[:1024]},
                    "action": {"button": boton[:20], "sections": [{"title": titulo_seccion[:24], "rows": rows}]},
                },
            }
        )

    async def plantilla(self, a: str, nombre: str, parametros: list[str], idioma: str) -> str:
        componentes = []
        if parametros:
            componentes = [{"type": "body", "parameters": [{"type": "text", "text": p} for p in parametros]}]
        return await self._post(
            {
                "to": a,
                "type": "template",
                "template": {"name": nombre, "language": {"code": idioma}, "components": componentes},
            }
        )

    async def marcar_leido(self, wamid: str) -> None:
        if self.dry_run or wamid.startswith("wamid.lab."):
            return
        try:
            await self._post({"status": "read", "message_id": wamid})
        except Exception:  # noqa: BLE001 - las palomitas azules no son críticas
            log.debug("No se pudo marcar como leído %s", wamid)


def _resumen(cuerpo: dict[str, Any]) -> str:
    if cuerpo.get("type") == "text":
        return cuerpo["text"]["body"][:120]
    if cuerpo.get("type") == "interactive":
        i = cuerpo["interactive"]
        return f"[{i['type']}] {i['body']['text'][:100]}"
    if cuerpo.get("type") == "template":
        return f"[plantilla] {cuerpo['template']['name']}"
    return str(cuerpo)[:120]
