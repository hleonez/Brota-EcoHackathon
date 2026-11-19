"""Máquina de estados de Brisa.

    SIN_REGISTRO → PIDE_NOMBRE → PIDE_TORRE → PIDE_APTO → CONSENTIMIENTO → MENÚ

El estado de registro se guarda en memoria por celular (se pierde al reiniciar; en ese caso el
vecino simplemente empieza de nuevo). Si un vecino ya está registrado, la API lo dice en
`GET /v1/me` y se va directo al menú: la fuente de verdad es la API, no el bot.
Para varias réplicas del bot, cambiar `Memoria` por Redis.
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app import textos as T
from app.brota import Brota, ErrorBrota
from app.catalogo import buscar
from app.coordinacion import Coordinacion
from app.ia import interpretar
from app.pedido import Pedido
from app.soporte import Soporte
from app.whatsapp import Boton, Entrante, ErrorWhatsApp, Fila, WhatsApp

log = logging.getLogger("brota.bot.conversacion")

FILAS_MENU = [
    Fila("M_PEDIR", "♻ Pedir recolección", "Te ayudo a preparar tu material"),
    Fila("M_DUDA", "❓ Tengo una duda", "¿Esto se recicla? ¿Cómo lo preparo?"),
    Fila("M_ESTADO", "📦 Mis solicitudes", "Cómo va lo que pediste"),
    Fila("M_PUNTOS", "⭐ Mis puntos"),
    Fila("M_LIGA", "🏆 Liga de torres"),
    Fila("M_QUEJA", "⚠ Reportar un problema", "Algo salió mal con una recolección"),
    Fila("M_PERSONA", "🙋 Hablar con alguien", "Te responde una persona del equipo"),
]
PALABRAS_MENU = {"menu", "inicio", "volver", "opciones"}
MAX_MEDIA = 10 * 1024 * 1024


def _fichas_de(r: dict[str, Any] | None, fichas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fichas del catálogo para los residuos que propuso la IA (en su orden)."""
    por_codigo = {f["codigo"]: f for f in fichas}
    return [por_codigo[x["codigo"]] for x in (r or {}).get("residuos", []) if x["codigo"] in por_codigo]
BOTONES_CONSENTIMIENTO = [Boton("ACEPTO", "Sí, acepto"), Boton("VER_MAS", "Ver más"), Boton("NO_ACEPTO", "No")]
BOTONES_BORRAR = [Boton("BORRAR_SI", "Sí, borrar"), Boton("BORRAR_NO", "No")]
SALUDOS = {"hola", "buenas", "buenos dias", "buenas tardes", "buenas noches", "hi", "hello", "ola", "holi"}


@dataclass
class Estado:
    paso: str = "INICIO"
    nombre: str | None = None
    conjunto_id: str | None = None
    torres: dict[str, dict[str, Any]] = field(default_factory=dict)
    torre_id: str | None = None
    unidad: dict[str, Any] | None = None
    actualizado: float = field(default_factory=time.monotonic)


class Memoria:
    """Estado de conversación por celular, con vencimiento por inactividad."""

    def __init__(self, ttl_segundos: int = 1800) -> None:
        self.ttl = ttl_segundos
        self._datos: dict[str, Estado] = {}

    def obtener(self, celular: str) -> Estado:
        e = self._datos.get(celular)
        if e is None or time.monotonic() - e.actualizado > self.ttl:
            e = Estado()
            self._datos[celular] = e
        e.actualizado = time.monotonic()
        return e

    def borrar(self, celular: str) -> None:
        self._datos.pop(celular, None)


def normalizar(texto: str | None) -> str:
    t = unicodedata.normalize("NFKD", (texto or "").strip().lower())
    return "".join(c for c in t if not unicodedata.combining(c))


_PALABRAS_APTO = re.compile(r"\b(?:apartamento|apto|apt|ap|numero|no|n|casa)\b\.?|#")


def referencia_apto(texto: str | None) -> str:
    """'Apto 402' / 'apartamento #402' / '4-02' → '402'."""
    t = _PALABRAS_APTO.sub(" ", normalizar(texto))
    return "".join(ch for ch in t if ch.isalnum()).upper()


def _numero(d: str | None) -> str:
    """'25.00' → '25'; '12.50' → '12.5'."""
    if not d:
        return "0"
    return d.rstrip("0").rstrip(".") if "." in d else d


class Brisa:
    def __init__(self, wa: WhatsApp, api: Brota, memoria: Memoria | None = None) -> None:
        self.wa = wa
        self.api = api
        self.memoria = memoria or Memoria()
        self.coordinacion = Coordinacion(wa, api)
        self.pedido = Pedido(wa, api)
        self.soporte = Soporte(wa, api)
        self.en_duda: dict[str, float] = {}  # celular → cuándo tocó «Tengo una duda»

    async def atender(self, m: Entrante) -> None:
        await self.wa.marcar_leido(m.wamid)
        try:
            me = await self.api.me(m.de)
            if me.get("tipo_actor") == "operador":
                await self.coordinacion.atender(m, me)
            elif me["registrado"]:
                self.memoria.borrar(m.de)  # el registro terminó; ya no hace falta estado
                await self._registrado(m, me)
            else:
                await self._registro(m, me)
        except ErrorBrota as e:
            log.warning("Error de la API para %s: %s", m.de, e)
            await self.wa.texto(m.de, T.ERROR)

    # ------------------------------------------------------------------ registro

    async def _registro(self, m: Entrante, me: dict[str, Any]) -> None:
        e = self.memoria.obtener(m.de)

        if e.paso == "INICIO":
            e.paso = "PIDE_NOMBRE"
            await self.wa.texto(m.de, T.BIENVENIDA)
            return

        if e.paso == "PIDE_NOMBRE":
            nombre = (m.texto or "").strip()
            if not nombre or len(nombre) > 60 or normalizar(nombre).strip("!¡. ") in SALUDOS:
                await self.wa.texto(m.de, T.PIDE_NOMBRE_OTRA_VEZ)
                return
            e.nombre = nombre[:1].upper() + nombre[1:]
            await self._preguntar_torre(m.de, e)
            return

        if e.paso == "PIDE_TORRE":
            torre = self._elegir_torre(e, m)
            if torre is None:
                await self.wa.texto(m.de, T.TORRE_NO_VALIDA)
                return
            e.torre_id = torre["id"]
            e.paso = "PIDE_APTO"
            await self.wa.texto(m.de, T.PIDE_APTO.format(torre=torre["nombre"] or f"Torre {torre['codigo']}"))
            return

        if e.paso == "PIDE_APTO":
            apto = referencia_apto(m.texto)
            torre = e.torres.get(e.torre_id or "", {})
            nombre_torre = torre.get("nombre") or f"Torre {torre.get('codigo', '')}"
            unidad = await self.api.buscar_unidad(m.de, e.torre_id, apto) if apto and e.torre_id else None
            if unidad is None:
                await self.wa.texto(m.de, T.APTO_NO_ENCONTRADO.format(apto=apto or "ese", torre=nombre_torre))
                return
            e.unidad = unidad
            e.paso = "CONSENTIMIENTO"
            await self._pedir_consentimiento(m.de, e)
            return

        if e.paso == "CONSENTIMIENTO":
            if m.respuesta_id == "VER_MAS":
                await self.wa.texto(m.de, T.POLITICA.format(version=me["politica_datos_version"]))
                await self._pedir_consentimiento(m.de, e)
                return
            if m.respuesta_id == "NO_ACEPTO":
                self.memoria.borrar(m.de)
                await self.wa.texto(m.de, T.SIN_CONSENTIMIENTO)
                return
            if m.respuesta_id != "ACEPTO" or not e.unidad or not e.nombre:
                await self._pedir_consentimiento(m.de, e)
                return
            try:
                await self.api.registrar(m.de, m.wamid, e.nombre, e.unidad["id"], me["politica_datos_version"])
            except ErrorBrota as err:
                if err.codigo != "CONTACT_ALREADY_REGISTERED":
                    raise
                await self.wa.texto(m.de, T.YA_REGISTRADO)
            nombre = e.nombre
            self.memoria.borrar(m.de)
            await self.wa.texto(m.de, T.REGISTRADO.format(nombre=nombre))
            await self._menu(m.de, nombre)
            return

        # Paso desconocido: reiniciar.
        self.memoria.borrar(m.de)
        await self._registro(m, me)

    async def _preguntar_torre(self, celular: str, e: Estado) -> None:
        conjuntos = await self.api.conjuntos(celular)
        if not conjuntos:
            await self.wa.texto(celular, T.ERROR)
            return
        e.conjunto_id = conjuntos[0]["id"]  # piloto: un solo conjunto (Brisas de San Pablo)
        torres = await self.api.torres(celular, e.conjunto_id)
        e.torres = {t["id"]: t for t in torres}
        e.paso = "PIDE_TORRE"
        if len(torres) <= 10:
            filas = [Fila(t["id"], t["nombre"] or f"Torre {t['codigo']}") for t in torres]
            await self.wa.lista(celular, T.ELIGE_TORRE.format(nombre=e.nombre), "Elegir torre",
                                conjuntos[0]["nombre"], filas)
        else:
            await self.wa.texto(celular, T.ELIGE_TORRE_TEXTO.format(nombre=e.nombre))

    def _elegir_torre(self, e: Estado, m: Entrante) -> dict[str, Any] | None:
        if m.respuesta_id and m.respuesta_id in e.torres:
            return e.torres[m.respuesta_id]
        escrito = normalizar(m.texto).replace("torre", "").strip()
        for t in e.torres.values():
            if escrito and escrito == normalizar(t["codigo"]):
                return t
        return None

    async def _pedir_consentimiento(self, celular: str, e: Estado) -> None:
        unidad = (e.unidad or {}).get("etiqueta", "")
        await self.wa.botones(celular, T.CONSENTIMIENTO.format(nombre=e.nombre, unidad=unidad), BOTONES_CONSENTIMIENTO)

    # ------------------------------------------------------------------ vecino registrado

    async def _registrado(self, m: Entrante, me: dict[str, Any]) -> None:
        nombre = me.get("nombre") or "vecino"
        opcion = m.respuesta_id or ""
        comando = normalizar(m.texto).strip("!¡.¿? ")
        duda = time.monotonic() - self.en_duda.pop(m.de, 0) < 1800
        caso = self.soporte.esperando(m.de)  # tipo de reporte que espera su detalle

        if opcion == "M_MENU" or comando in PALABRAS_MENU or comando in SALUDOS:
            await self._menu(m.de, nombre)  # el borrador se conserva: el menú ofrece seguirlo
        elif opcion in ("M_PEDIR", "RECICLABLES", "ORGANICOS", "LOS_DOS"):  # los tres últimos: menú anterior
            await self.pedido.empezar(m.de)
        elif opcion == "M_DUDA":
            self.en_duda[m.de] = time.monotonic()
            await self.wa.texto(m.de, T.DUDA_PREGUNTA)
        elif opcion == "M_ESTADO" or comando in ("estado", "mis solicitudes"):
            await self._estado(m.de)
        elif opcion == "M_PUNTOS" or comando in ("puntos", "mis puntos"):
            p = await self.api.puntos(m.de)
            await self.wa.texto(m.de, T.PUNTOS.format(saldo=_numero(p["saldo"])))
        elif opcion == "M_LIGA" or comando == "liga":
            await self._liga(m.de, me)
        elif opcion == "M_QUEJA":
            await self.soporte.pedir_detalle(m.de, "queja")
        elif opcion == "M_PERSONA":
            await self.soporte.pedir_detalle(m.de, "ayuda")
        elif opcion.startswith("S_") and await self.soporte.atender_boton(m):
            pass
        elif comando == "cancelar":
            if self.pedido.activo(m.de):
                await self.pedido.cancelar(m.de)
            else:
                await self.soporte.ofrecer_cancelar(m.de)
        elif caso and m.tipo == "text" and m.texto:
            await self.soporte.registrar(m.de, m.wamid, caso, m.texto)
        elif opcion == "BORRAR_SI":
            await self.api.pedir_eliminacion(m.de, m.wamid)
            await self.wa.texto(m.de, T.BORRAR_OK)
        elif opcion == "BORRAR_NO":
            await self.wa.texto(m.de, T.BORRAR_CANCELADO)
        elif comando in ("borrar mis datos", "borrar datos"):
            await self.wa.botones(m.de, T.BORRAR_CONFIRMA, BOTONES_BORRAR)
        elif duda and m.tipo == "text":
            await self._duda(m)
        elif m.tipo in ("audio", "image"):
            await self._media(m, me, nombre)
        elif await self.pedido.atender(m, me):
            pass
        elif m.tipo == "text" and m.texto:
            await self._texto_libre(m, me, nombre)
        else:
            if m.tipo in ("audio", "image", "video", "document"):
                await self.wa.texto(m.de, T.SOLO_BOTONES)
            await self._menu(m.de, nombre)

    # ------------------------------------------------------------------ IA: dudas, texto libre, audios y fotos

    async def _duda(self, m: Entrante) -> None:
        fichas = await self.api.residuos(m.de)
        r = await interpretar(self.api, m.de, texto=m.texto)
        encontradas = _fichas_de(r, fichas) if r else buscar(m.texto, fichas)
        await self.pedido.responder_duda(m.de, encontradas, respuesta=(r or {}).get("respuesta"))

    async def _texto_libre(self, m: Entrante, me: dict[str, Any], nombre: str) -> None:
        r = await interpretar(self.api, m.de, texto=m.texto)
        if r is None:  # sin IA: si menciona materiales, primero se le enseña; si no, el menú
            encontradas = buscar(m.texto, await self.api.residuos(m.de))
            if encontradas:
                await self.pedido.responder_duda(m.de, encontradas)
            else:
                await self._menu(m.de, nombre)
            return
        await self._rutear(m, me, nombre, r, "texto")

    async def _media(self, m: Entrante, me: dict[str, Any], nombre: str) -> None:
        es_audio = m.tipo == "audio"
        datos, mime = m.media_datos, m.media_mime
        if datos is None:
            try:
                datos, mime = await self.wa.descargar_media(m.media_id or "")
            except (ErrorWhatsApp, httpx.HTTPError) as e:
                log.warning("No se pudo descargar la media de %s: %s", m.wamid, e)
                await self.wa.texto(m.de, T.IA_DESCARGA)
                return
        if len(datos) > MAX_MEDIA:
            await self.wa.texto(m.de, T.IA_PESADO)
            return
        en_pedido = self.pedido.activo(m.de) is not None
        r = await interpretar(
            self.api, m.de, texto=m.texto, media=(datos, mime or ("audio/ogg" if es_audio else "image/jpeg")),
            contexto="pedido" if en_pedido else "general",
        )
        if r is None:
            await self.wa.texto(m.de, T.IA_MEDIA_SIN_IA)
            return
        caso = self.soporte.esperando(m.de)
        if caso and es_audio and r.get("transcripcion"):  # el detalle de un reporte, dictado
            await self.soporte.registrar(m.de, m.wamid, caso, r["transcripcion"])
            return
        lineas = []
        if es_audio and r.get("transcripcion"):
            lineas.append(T.IA_TE_ESCUCHE.format(texto=r["transcripcion"]))
        if not es_audio and r.get("observado"):
            lineas.append(T.IA_VI.format(texto=r["observado"]))
        lineas += [T.IA_PELIGRO.format(texto=p) for p in r.get("peligros") or []]
        encabezado = "\n".join(lineas) or None
        fuente = "audio" if es_audio else "foto"
        if r["residuos"] and (en_pedido or r["intencion"] in ("pedir", "otro", "saludo")):
            await self.pedido.proponer(m.de, [x["codigo"] for x in r["residuos"]], fuente, encabezado)
        elif not r["residuos"] and r["intencion"] in ("pedir", "otro"):
            no_entendi = r.get("aclaracion") or (T.IA_NO_ENTENDI_AUDIO if es_audio else T.IA_NO_ENTENDI_FOTO)
            await self.wa.texto(m.de, f"{encabezado}\n\n{no_entendi}" if encabezado else no_entendi)
        else:
            await self._rutear(m, me, nombre, r, fuente, encabezado)

    async def _rutear(
        self, m: Entrante, me: dict[str, Any], nombre: str, r: dict[str, Any], fuente: str,
        encabezado: str | None = None,
    ) -> None:
        """Lleva la intención que entendió la IA a la acción que corresponde. La IA no crea nada."""
        codigos = [x["codigo"] for x in r["residuos"]]
        intencion = r["intencion"]
        if intencion == "pedir":
            if codigos:
                await self.pedido.proponer(m.de, codigos, fuente, encabezado)
            else:
                await self._decir(m.de, encabezado)
                await self.pedido.empezar(m.de)
            return
        if intencion in ("duda", "otro") and (codigos or r.get("respuesta")):
            encontradas = _fichas_de(r, await self.api.residuos(m.de))
            await self.pedido.responder_duda(m.de, encontradas, r.get("respuesta"), encabezado)
            return
        await self._decir(m.de, encabezado)
        if intencion == "estado":
            await self._estado(m.de)
        elif intencion == "puntos":
            p = await self.api.puntos(m.de)
            await self.wa.texto(m.de, T.PUNTOS.format(saldo=_numero(p["saldo"])))
        elif intencion == "liga":
            await self._liga(m.de, me)
        elif intencion == "cancelar":
            if self.pedido.activo(m.de):
                await self.pedido.cancelar(m.de)
            else:
                await self.soporte.ofrecer_cancelar(m.de)
        elif intencion == "queja":
            relato = m.texto or r.get("transcripcion") or ""
            if len(relato.split()) >= 4:  # ya contó qué pasó: se registra de una vez
                await self.soporte.registrar(m.de, m.wamid, "queja", relato)
            else:
                await self.soporte.pedir_detalle(m.de, "queja")
        elif intencion == "persona":
            await self.soporte.pedir_detalle(m.de, "ayuda")
        elif r.get("aclaracion") and intencion != "saludo":
            await self.wa.texto(m.de, r["aclaracion"])
        else:
            await self._menu(m.de, nombre)

    async def _decir(self, celular: str, texto: str | None) -> None:
        if texto:
            await self.wa.texto(celular, texto)

    async def _menu(self, celular: str, nombre: str) -> None:
        filas = list(FILAS_MENU)
        b = self.pedido.activo(celular)
        if b and b.items:
            n = len(b.items)
            filas.insert(0, Fila("P_SEGUIR", "📝 Seguir mi pedido", f"{n} material{'es' if n != 1 else ''} sin enviar"))
        await self.wa.lista(celular, T.MENU_LISTA.format(nombre=nombre), "Ver opciones", "Brisa", filas)

    async def _estado(self, celular: str) -> None:
        abiertas = await self.api.solicitudes_abiertas(celular)
        if not abiertas:
            await self.wa.texto(celular, T.SIN_SOLICITUDES)
            return
        lineas = []
        for s in abiertas:
            for o in s["ordenes"]:
                estado = T.ESTADO_ORDEN.get(o["estado"], o["estado"])
                if o.get("asignacion"):
                    a = o["asignacion"]
                    estado += f" a {a['recolector_nombre']}"
                    if a.get("inicio"):
                        estado += f" ({_hora_local(a['inicio'])})"
                lineas.append(f"• {s['codigo_pasaporte']} · {o['gremio_nombre']}: {estado}")
        await self.wa.texto(celular, "📋 Tus recolecciones:\n" + "\n".join(lineas) + T.ESTADO_PIE)

    async def _liga(self, celular: str, me: dict[str, Any]) -> None:
        unidades = me.get("unidades") or []
        if not unidades or not unidades[0].get("conjunto_id"):
            await self.wa.texto(celular, T.LIGA_NO_DISPONIBLE)
            return
        try:
            liga = await self.api.liga_del_mes(celular, unidades[0]["conjunto_id"])
        except ErrorBrota as err:
            if err.codigo == "LIGA_NOT_CONFIGURED":
                await self.wa.texto(celular, T.LIGA_NO_DISPONIBLE)
                return
            raise
        mia = next((t for t in liga["torres"] if t["torre_id"] == unidades[0]["torre_id"]), None)
        if mia is None:
            await self.wa.texto(celular, T.LIGA_NO_DISPONIBLE)
            return
        await self.wa.texto(
            celular,
            T.LIGA_POSICION.format(
                torre=mia["torre_nombre"], posicion=mia["posicion"],
                porcentaje=_numero(mia["porcentaje_participacion"]).replace(".", ","),
            ),
        )


def _hora_local(iso: str) -> str:
    d = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=-5)))
    h = d.hour % 12 or 12
    return f"{h}:{d.minute:02d} {'a. m.' if d.hour < 12 else 'p. m.'}"
