"""Soporte al vecino: reportar un problema, hablar con una persona y cancelar una solicitud enviada.

- Reporte o ayuda: Brisa pide el detalle en un mensaje (texto o nota de voz) y crea un caso en la API.
  La coordinación lo ve en el panel (Reportes) y su respuesta le llega al vecino por aquí.
- Cancelar: Brisa muestra las solicitudes abiertas, pide confirmación y la API avisa a la coordinación.
"""

from __future__ import annotations

import re
import time
from typing import Any

from app import textos as T
from app.brota import Brota, ErrorBrota
from app.whatsapp import Boton, Entrante, Fila, WhatsApp

ESPERA = 1800  # segundos que Brisa espera el detalle de un reporte
_BR = re.compile(r"\bBR[-\s]?(\d{1,5})\b", re.IGNORECASE)


def codigo_mencionado(texto: str | None) -> str | None:
    """«me cancelaron la br 18» → BR-00018."""
    m = _BR.search(texto or "")
    return f"BR-{int(m.group(1)):05d}" if m else None


def _detalle(s: dict[str, Any]) -> str:
    partes = []
    for o in s.get("ordenes", []):
        gremio = (o.get("gremio_nombre") or "").split(" ·")[0]
        partes.append(f"{gremio}: {T.ESTADO_ORDEN.get(o['estado'], o['estado'])}")
    return "; ".join(partes)


class Soporte:
    def __init__(self, wa: WhatsApp, api: Brota) -> None:
        self.wa = wa
        self.api = api
        self._pendientes: dict[str, tuple[str, float]] = {}  # celular → (tipo de caso, desde)

    def esperando(self, celular: str) -> str | None:
        tipo, desde = self._pendientes.get(celular, ("", 0.0))
        return tipo if tipo and time.monotonic() - desde < ESPERA else None

    async def pedir_detalle(self, celular: str, tipo: str, encabezado: str | None = None) -> None:
        self._pendientes[celular] = (tipo, time.monotonic())
        texto = T.CASO_QUEJA_PIDE if tipo == "queja" else T.CASO_AYUDA_PIDE
        await self.wa.texto(celular, f"{encabezado}\n\n{texto}" if encabezado else texto)

    async def registrar(self, celular: str, clave: str, tipo: str, texto: str) -> None:
        self._pendientes.pop(celular, None)
        caso = await self.api.crear_caso(celular, clave, tipo, texto.strip(), codigo_mencionado(texto))
        await self.wa.texto(celular, T.CASO_REGISTRADO.format(codigo=caso["codigo"]))

    async def ofrecer_cancelar(self, celular: str) -> None:
        abiertas = await self.api.solicitudes_abiertas(celular)
        if not abiertas:
            await self.wa.texto(celular, T.CANCELAR_NADA)
        elif len(abiertas) == 1:
            await self._confirmar(celular, abiertas[0])
        else:
            filas = [Fila(f"S_CANCELAR:{s['id']}", f"❌ {s['codigo_pasaporte']}", _detalle(s)) for s in abiertas[:10]]
            await self.wa.lista(celular, T.CANCELAR_CUAL, "Ver solicitudes", "Tus solicitudes", filas)

    async def atender_boton(self, m: Entrante) -> bool:
        accion, _, resto = (m.respuesta_id or "").partition(":")
        if accion == "S_CANCELAR":
            s = next((x for x in await self.api.solicitudes_abiertas(m.de) if x["id"] == resto), None)
            if s is None:
                await self.wa.texto(m.de, T.CANCELAR_NO_SE_PUEDE)
            else:
                await self._confirmar(m.de, s)
        elif accion == "S_CANCELAR_SI":
            try:
                s = await self.api.cancelar_solicitud(m.de, m.wamid, resto)
            except ErrorBrota as e:
                if e.codigo not in ("INVALID_TRANSITION", "NOT_FOUND"):
                    raise
                await self.wa.texto(m.de, T.CANCELAR_NO_SE_PUEDE)
                return True
            await self.wa.texto(m.de, T.CANCELADA.format(codigo=s["codigo_pasaporte"]))
        else:
            return False
        return True

    async def _confirmar(self, celular: str, s: dict[str, Any]) -> None:
        await self.wa.botones(
            celular, T.CANCELAR_CONFIRMA.format(codigo=s["codigo_pasaporte"], detalle=_detalle(s)),
            [Boton(f"S_CANCELAR_SI:{s['id']}", "❌ Sí, cancelar"), Boton("M_MENU", "No, dejarla")],
        )
