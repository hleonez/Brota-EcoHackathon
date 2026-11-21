"""Cliente de la API de Brota (ver docs/integracion-bot.md).

Cada llamada en nombre de un vecino lleva `X-Canal-Celular`; las escrituras usan el `wamid`
del mensaje como `Idempotency-Key`, así un reintento de Meta o un doble toque no duplica nada.
"""

from __future__ import annotations

import base64
import time
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
    _residuos: tuple[float, list[dict[str, Any]]] | None = field(default=None, repr=False)

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
        timeout: float = 15,
    ) -> Any:
        r = await self.cliente.request(
            metodo, self._url(ruta), headers=self._cabeceras(celular, clave), json=json, params=params, timeout=timeout
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

    async def movimientos_puntos(self, celular: str) -> list[dict[str, Any]]:
        return (await self._pedir("GET", "/v1/me/movimientos-puntos", celular))["data"]

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

    async def residuos(self, celular: str) -> list[dict[str, Any]]:
        """Fichas de residuos (catálogo de la API), en caché 5 minutos."""
        ahora = time.monotonic()
        if self._residuos is None or ahora - self._residuos[0] > 300:
            self._residuos = (ahora, (await self._pedir("GET", "/v1/residuos", celular))["data"])
        return self._residuos[1]

    async def interpretar(
        self, celular: str, texto: str | None = None, media: tuple[bytes, str] | None = None,
        contexto: str = "general",
    ) -> dict[str, Any]:
        """IA de la API (Gemini): intención, residuos del catálogo, transcripción u observación de la foto."""
        cuerpo: dict[str, Any] = {"contexto": contexto}
        if texto:
            cuerpo["texto"] = texto[:2000]
        if media:
            cuerpo["media"] = {"mime_type": media[1], "datos_base64": base64.b64encode(media[0]).decode()}
        return (await self._pedir("POST", "/v1/ia/interpretar", celular, json=cuerpo, timeout=60))["data"]

    async def crear_solicitud(
        self, celular: str, clave: str, tipo_servicio_ids: list[str] | None = None,
        residuos: list[dict[str, Any]] | None = None, *,
        preferencia_sin_restriccion: bool = False,
        preferencia_inicio: str | None = None,
        preferencia_fin: str | None = None,
        unidad_id: str | None = None,
    ) -> dict[str, Any]:
        """Una sola alternativa de horario: la bandera, o inicio y fin. Nunca las dos."""
        cuerpo: dict[str, Any] = {}
        if tipo_servicio_ids:
            cuerpo["tipo_servicio_ids"] = tipo_servicio_ids
        if residuos:
            cuerpo["residuos"] = residuos
        if preferencia_sin_restriccion:
            cuerpo["preferencia_sin_restriccion"] = True
        elif preferencia_inicio and preferencia_fin:
            cuerpo["preferencia_inicio"] = preferencia_inicio
            cuerpo["preferencia_fin"] = preferencia_fin
        if unidad_id:
            cuerpo["unidad_id"] = unidad_id
        return (await self._pedir("POST", "/v1/solicitudes", celular, clave=clave, json=cuerpo))["data"]

    async def crear_caso(
        self, celular: str, clave: str, tipo: str, texto: str, codigo_pasaporte: str | None = None
    ) -> dict[str, Any]:
        """Queja (tipo «queja») o pedido de hablar con una persona («ayuda»); lo atiende la coordinación."""
        cuerpo: dict[str, Any] = {"tipo": tipo, "texto": texto[:1000]}
        if codigo_pasaporte:
            cuerpo["codigo_pasaporte"] = codigo_pasaporte
        return (await self._pedir("POST", "/v1/casos", celular, clave=clave, json=cuerpo))["data"]

    async def cancelar_solicitud(self, celular: str, clave: str, solicitud_id: str) -> dict[str, Any]:
        return (await self._pedir("POST", f"/v1/solicitudes/{solicitud_id}/cancelacion", celular, clave=clave,
                                  json={}))["data"]

    async def pedir_eliminacion(self, celular: str, clave: str) -> dict[str, Any]:
        return (await self._pedir("POST", "/v1/me/solicitudes-eliminacion", celular, clave=clave, json={}))["data"]

    # ------------------------------------------------------------------ coordinación (cuenta operadora)

    async def ordenes(self, celular: str, estado: str | None, limite: int = 10) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limite}
        if estado:
            params["estado"] = estado
        return (await self._pedir("GET", "/v1/ordenes", celular, params=params))["data"]

    async def orden(self, celular: str, orden_id: str) -> dict[str, Any]:
        return (await self._pedir("GET", f"/v1/ordenes/{orden_id}", celular))["data"]

    async def recolectores(self, celular: str, gremio_id: str) -> list[dict[str, Any]]:
        params = {"gremio_id": gremio_id, "activo": "true", "limit": 10}
        return (await self._pedir("GET", "/v1/recolectores", celular, params=params))["data"]

    async def asignar(
        self, celular: str, clave: str, orden_id: str, version: int, recolector_id: str,
        inicio: str | None, fin: str | None, acuerdo_canal: str | None,
    ) -> dict[str, Any]:
        cuerpo: dict[str, Any] = {"version_esperada": version, "recolector_id": recolector_id, "forma_aviso": "llamada"}
        if inicio and fin:
            cuerpo |= {"inicio": inicio, "fin": fin, "acuerdo_canal": acuerdo_canal}
        return (await self._pedir("POST", f"/v1/ordenes/{orden_id}/asignacion", celular, clave=clave, json=cuerpo))[
            "data"
        ]

    async def registrar_resultado(
        self, celular: str, clave: str, orden_id: str, version: int, resultado: str,
        materiales_confirmados: list[str], motivo_id: str | None = None,
    ) -> dict[str, Any]:
        cuerpo: dict[str, Any] = {
            "version_esperada": version,
            "resultado": resultado,
            "materiales_confirmados": materiales_confirmados,
            "ocurrido_at": datetime.now(timezone.utc).isoformat(),
        }
        if motivo_id:
            cuerpo["motivo_rechazo_id"] = motivo_id
        return (await self._pedir("POST", f"/v1/ordenes/{orden_id}/resultado", celular, clave=clave, json=cuerpo))[
            "data"
        ]

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
