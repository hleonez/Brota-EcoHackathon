"""Bucle de avisos: reserva en la API de Brota → envía por WhatsApp → confirma el resultado.

Si Meta responde 131047 (pasaron más de 24 h desde el último mensaje del vecino) y
`WHATSAPP_USAR_PLANTILLAS=true`, se reintenta con la plantilla aprobada del tipo de aviso.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app import textos as T
from app.brota import Brota, ErrorBrota
from app.config import Settings
from app.whatsapp import Boton, ErrorWhatsApp, WhatsApp

log = logging.getLogger("brota.bot.avisos")

# tipo de aviso → (plantilla en WhatsApp Manager, variables en orden desde `datos`)
PLANTILLAS: dict[str, tuple[str, list[str]]] = {
    "asignacion": ("brota_asignacion", ["recolector_nombre", "franja_texto", "codigo_pasaporte"]),
    "recoleccion_confirmada": ("brota_recoleccion_v2", ["codigo_pasaporte", "puntos_otorgados", "saldo"]),
    "entrega_directa_confirmada": ("brota_recoleccion_v2", ["codigo_pasaporte", "puntos_otorgados", "saldo"]),
    "rechazo_educativo": ("brota_rechazo_v2", ["codigo_pasaporte", "motivo"]),
    "nueva_orden": ("brota_nueva_orden_v2", ["codigo_pasaporte", "ubicacion", "servicios"]),
}


def _texto(aviso: dict[str, Any]) -> tuple[str, bool]:
    datos = aviso["datos"]
    texto = datos.get("texto_sugerido") or "Tienes una novedad en Brota 💚"
    con_enlace = False
    contenido = datos.get("contenido")
    if aviso["tipo"] == "rechazo_educativo" and contenido:
        texto += f"\n\n📘 {contenido['titulo']}"
        if contenido.get("texto"):
            texto += f"\n{contenido['texto']}"
        if contenido.get("recurso"):
            texto += f"\n▶ {contenido['recurso']}"
            con_enlace = True
    return texto, con_enlace


def _parametros(datos: dict[str, Any], campos: list[str]) -> list[str]:
    valores = []
    for c in campos:
        v = datos.get(c)
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v)
        if isinstance(v, str) and c in ("puntos_otorgados", "saldo") and "." in v:
            v = v.rstrip("0").rstrip(".")
        if v in (None, "") and c == "franja_texto":
            v = "pronto"  # «Rosa pasará por tu recolección pronto»
        valores.append(str(v) if v not in (None, "") else "-")  # Meta rechaza parámetros vacíos
    return valores


async def enviar(wa: WhatsApp, settings: Settings, aviso: dict[str, Any]) -> str:
    a = aviso["destino"]["celular"].lstrip("+")
    texto, enlace = _texto(aviso)
    try:
        if aviso["tipo"] == "nueva_orden":  # a la coordinación
            if settings.coordinacion_por_whatsapp:  # respaldo: asignar desde el mismo chat
                orden_id = aviso["datos"]["orden_id"]
                return await wa.botones(
                    a, texto, [Boton(f"C_ASG:{orden_id}", "🚲 Asignar"), Boton("C_BANDEJA", "📋 Ver bandeja")]
                )
            url = settings.panel_coordinacion_url
            texto += "\n\n" + T.C_ALERTA_PANEL.format(enlace=f": {url}" if url else "")
            return await wa.texto(a, texto, vista_previa=bool(url))
        return await wa.texto(a, texto, vista_previa=enlace)
    except ErrorWhatsApp as e:
        if e.fuera_de_ventana and settings.whatsapp_usar_plantillas and aviso["tipo"] in PLANTILLAS:
            nombre, campos = PLANTILLAS[aviso["tipo"]]
            return await wa.plantilla(a, nombre, _parametros(aviso["datos"], campos), settings.plantillas_idioma)
        raise


async def procesar_lote(wa: WhatsApp, api: Brota, settings: Settings) -> int:
    avisos = await api.reservar_avisos(settings.avisos_lote)
    for aviso in avisos:
        try:
            wamid = await enviar(wa, settings, aviso)
            await api.confirmar_aviso(aviso["id"], True, id_externo=wamid)
        except ErrorWhatsApp as e:
            if e.codigo == 190:
                log.error("Aviso %s no enviado: el token de WhatsApp venció (190). Renuévalo en bot/.env.", aviso["id"])
            else:
                log.warning("Aviso %s no enviado: %s", aviso["id"], e)
            # Fuera de ventana sin plantilla: reintentar no sirve.
            await api.confirmar_aviso(aviso["id"], False, error=str(e), reintentar=not e.fuera_de_ventana)
        except httpx.HTTPError as e:
            await api.confirmar_aviso(aviso["id"], False, error=f"{type(e).__name__}: {e}", reintentar=True)
    return len(avisos)


async def bucle(wa: WhatsApp, api: Brota, settings: Settings) -> None:
    caido = False
    while True:
        n = 0
        try:
            n = await procesar_lote(wa, api, settings)
            if caido:
                log.info("La API de Brota volvió a responder.")
            caido = False
        except (httpx.HTTPError, ErrorBrota) as e:
            if not caido:
                log.warning("No se pudo consultar avisos en la API de Brota: %s", e)
            caido = True
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - el bucle no debe morir
            log.exception("Fallo inesperado en el bucle de avisos")
        await asyncio.sleep(0.2 if n else settings.avisos_intervalo_segundos)
