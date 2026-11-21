"""Registro de la conversación en la API (`POST /v1/canal/mensajes`) para que Administración la vea.

Nunca bloquea ni rompe la conversación: cada registro corre en una tarea en segundo plano y
cualquier error (API caída, 4xx, red) solo queda en el log. Si la API no responde, Brisa sigue igual.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

from app.whatsapp import Entrante

log = logging.getLogger("brota.bot.registro")

MAX_TEXTO = 4000

_MEDIA = {"video": "🎬 Video", "document": "📄 Documento", "sticker": "Sticker"}


def describir_entrante(m: Entrante) -> tuple[str, str]:
    """(tipo, texto) de un mensaje del vecino, como lo verá Administración."""
    if m.tipo == "text":
        return "texto", m.texto or ""
    if m.tipo == "audio":
        return "audio", "🎤 Nota de voz"
    if m.tipo == "image":
        return "imagen", "📷 Foto" + (f": {m.texto}" if m.texto else "")
    if m.tipo in ("interactive", "button"):
        return "interactivo", m.respuesta_titulo or m.respuesta_id or ""
    if m.tipo in _MEDIA:
        return "sistema", _MEDIA[m.tipo] + (f": {m.texto}" if m.texto else "")
    return "sistema", f"Mensaje de tipo {m.tipo or 'desconocido'}"


def describir_saliente(cuerpo: dict[str, Any]) -> tuple[str, str] | None:
    """(tipo, texto) de lo que Brisa envió; None si no es un mensaje (p. ej. marcar como leído)."""
    tipo = cuerpo.get("type")
    if tipo == "text":
        return "texto", cuerpo.get("text", {}).get("body", "")
    if tipo == "interactive":
        i = cuerpo.get("interactive", {})
        texto = i.get("body", {}).get("text", "")
        accion = i.get("action", {})
        if i.get("type") == "button":
            titulos = [b.get("reply", {}).get("title", "") for b in accion.get("buttons", [])]
        else:
            titulos = [f.get("title", "") for s in accion.get("sections", []) for f in s.get("rows", [])]
        if titulos:
            texto = f"{texto} · {' | '.join(titulos)}"
        return "interactivo", texto
    if tipo == "template":
        t = cuerpo.get("template", {})
        parametros = [p.get("text", "") for c in t.get("components", []) for p in c.get("parameters", [])]
        texto = f"Plantilla {t.get('name', '')}"
        if parametros:
            texto += ": " + " | ".join(parametros)
        return "plantilla", texto
    return None


class Registro:
    """Lanza los registros en segundo plano y guarda las tareas para poder esperarlas al apagar."""

    def __init__(self, api: Any) -> None:
        self.api = api
        self.tareas: set[asyncio.Task[None]] = set()

    def entrante(self, m: Entrante) -> None:
        try:
            tipo, texto = describir_entrante(m)
            self._lanzar(self._enviar(m.de, "entrante", tipo, texto, m.wamid or None))
        except Exception:  # noqa: BLE001 - registrar nunca debe romper la conversación
            log.exception("No se pudo preparar el registro de un mensaje entrante")

    def saliente(self, cuerpo: dict[str, Any], wamid: str | None) -> None:
        try:
            a = cuerpo.get("to")
            descrito = describir_saliente(cuerpo)
            if not a or descrito is None:
                return
            tipo, texto = descrito
            self._lanzar(self._enviar(a, "saliente", tipo, texto, wamid or None))
        except Exception:  # noqa: BLE001
            log.exception("No se pudo preparar el registro de un mensaje saliente")

    def _lanzar(self, coro: Coroutine[Any, Any, None]) -> None:
        try:
            t = asyncio.get_running_loop().create_task(coro)
        except RuntimeError:  # sin bucle de eventos (no debería pasar dentro del bot)
            coro.close()
            return
        self.tareas.add(t)
        t.add_done_callback(self.tareas.discard)

    async def _enviar(self, celular: str, direccion: str, tipo: str, texto: str, wamid: str | None) -> None:
        try:
            await self.api.registrar_mensaje(celular, direccion, tipo, texto[:MAX_TEXTO], wamid)
        except Exception as e:  # noqa: BLE001
            log.warning("No se pudo registrar un mensaje %s en la API: %s", direccion, type(e).__name__)

    async def esperar(self, segundos: float = 3.0) -> None:
        """Al apagar: da un momento a los registros pendientes para terminar."""
        if self.tareas:
            await asyncio.wait(set(self.tareas), timeout=segundos)
