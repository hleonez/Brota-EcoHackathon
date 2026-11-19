"""Cliente de la API de Brota (ver docs/integracion-bot.md).

Cada llamada en nombre de un vecino lleva `X-Canal-Celular`; las escrituras usan el `wamid`
del mensaje como `Idempotency-Key`, así un reintento de Meta o un doble toque no duplica nada.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import Settings


class ErrorBrota(Exception):
    def __init__(self, status: int, codigo: str, mensaje: str, datos: dict[str, Any] | None = None) -> None:
        super().__init__(f"{status} {codigo}: {mensaje}")
        self.status = status
        self.codigo = codigo
        self.mensaje = mensaje
        self.datos = datos or {}


@dataclass
class Brota:
    settings: Settings
    cliente: httpx.AsyncClient
    _catalogo: dict[str, Any] | None = field(default=None, repr=False)

    def _url(self, ruta: str) -> str:
        return f"{self.settings.brota_api_url.rstrip('/')}{ruta}"

    def _cabeceras(self, celular: str | None, clave: str | None) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self.settings.bot_service_token}"}
        if celular:
            h["X-Canal-Celular"] = celular
        if clave:
            h["Idempotency-Key"] = clave[:128]
        return h

    async def _pedir(
        self,
        metodo: str,
        ruta: str,
        celular: str | None = None,
        *,
        clave: str | None = None,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        r = await self.cliente.request(
            metodo, self._url(ruta), headers=self._cabeceras(celular, clave), json=json, params=params, timeout=15
        )
        cuerpo = r.json() if r.content else {}
        if r.status_code >= 400:
            err = cuerpo.get("error", {}) if isinstance(cuerpo, dict) else {}
            raise ErrorBrota(r.status_code, err.get("code", "HTTP_ERROR"), err.get("message", r.text[:200]), err)
        return cuerpo

    # ------------------------------------------------------------------ consultas

    async def me(self, celular: str) -> dict[str, Any]:
        return (await self._pedir("GET", "/v1/me", celular))["data"]

    async def conjuntos(self, celular: str) -> list[dict[str, Any]]:
        return (await self._pedir("GET", "/v1/conjuntos", celular))["data"]

    async def torres(self, celular: str, conjunto_id: str) -> list[dict[str, Any]]:
        return (await self._pedir("GET", f"/v1/conjuntos/{conjunto_id}/torres", celular, params={"limit": 100}))["data"]

    async def buscar_unidad(self, celular: str, torre_id: str, referencia: str) -> dict[str, Any] | None:
        datos = (
            await self._pedir("GET", "/v1/unidades", celular, params={"torre_id": torre_id, "referencia": referencia})
        )["data"]
        return datos[0] if datos else None

    async def catalogo(self, celular: str) -> dict[str, Any]:
        if self._catalogo is None:
            self._catalogo = (await self._pedir("GET", "/v1/catalogos", celular))["data"]
        return self._catalogo

    async def servicios_por_codigo(self, celular: str) -> dict[str, str]:
        cat = await self.catalogo(celular)
        return {t["codigo"]: t["id"] for t in cat["tipos_servicio"]}

    async def puntos(self, celular: str) -> dict[str, Any]:
        return (await self._pedir("GET", "/v1/me/puntos", celular))["data"]

    async def solicitudes_abiertas(self, celular: str) -> list[dict[str, Any]]:
        return (await self._pedir("GET", "/v1/solicitudes", celular, params={"abiertas": "true", "limit": 5}))["data"]

    async def liga_del_mes(self, celular: str, conjunto_id: str) -> dict[str, Any]:
        bogota = timezone(timedelta(hours=-5))
        ahora = datetime.now(bogota)
        desde = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        hasta = (desde + timedelta(days=32)).replace(day=1)
        params = {"conjunto_id": conjunto_id, "desde": desde.isoformat(), "hasta": hasta.isoformat()}
        return (await self._pedir("GET", "/v1/liga", celular, params=params))["data"]

    # ------------------------------------------------------------------ escrituras

    async def registrar(self, celular: str, clave: str, nombre: str, unidad_id: str, politica: str) -> dict[str, Any]:
        cuerpo = {"nombre": nombre, "unidad_id": unidad_id,
                  "consentimiento": {"version_politica": politica, "decision": "aceptado"}}
        return (await self._pedir("POST", "/v1/registros", celular, clave=clave, json=cuerpo))["data"]

    async def crear_solicitud(self, celular: str, clave: str, tipo_servicio_ids: list[str]) -> dict[str, Any]:
        cuerpo = {"tipo_servicio_ids": tipo_servicio_ids}
        return (await self._pedir("POST", "/v1/solicitudes", celular, clave=clave, json=cuerpo))["data"]

    async def pedir_eliminacion(self, celular: str, clave: str) -> dict[str, Any]:
        return (await self._pedir("POST", "/v1/me/solicitudes-eliminacion", celular, clave=clave, json={}))["data"]

    # ------------------------------------------------------------------ avisos (como servicio)

    async def reservar_avisos(self, limite: int) -> list[dict[str, Any]]:
        return (await self._pedir("POST", "/v1/canal/avisos/reservas", json={"limite": limite}))["data"]

    async def confirmar_aviso(
        self, aviso_id: str, enviado: bool, id_externo: str | None = None, error: str | None = None,
        reintentar: bool = True,
    ) -> None:
        cuerpo: dict[str, Any] = {"estado": "enviado" if enviado else "fallido", "reintentar": reintentar}
        if id_externo:
            cuerpo["id_externo"] = id_externo
        if error:
            cuerpo["error"] = error[:500]
        await self._pedir("POST", f"/v1/canal/avisos/{aviso_id}/resultado", json=cuerpo)


def clave_nueva() -> str:
    return str(uuid.uuid4())
