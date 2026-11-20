"""IA de la API (Gemini) vista desde el bot: si no está disponible, devuelve None y Brisa sigue
con listas y sinónimos del catálogo. Nunca bloquea la conversación."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.brota import Brota, ErrorBrota

log = logging.getLogger("brota.bot.ia")


async def interpretar(api: Brota, celular: str, **kw: Any) -> dict[str, Any] | None:
    try:
        return await api.interpretar(celular, **kw)
    except ErrorBrota as e:
        log.info("IA no disponible (%s %s): sigo sin IA", e.status, e.codigo)
    except httpx.HTTPError as e:
        log.info("IA sin respuesta (%s): sigo sin IA", type(e).__name__)
    return None
