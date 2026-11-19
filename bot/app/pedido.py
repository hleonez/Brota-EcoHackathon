"""Pedido guiado: Brisa enseña antes de pedir.

    ELIGE (lista o texto) → CONFIRMA (si fue texto) → CHEQUEO (preguntas de cada ficha)
    → MAS (¿algo más?) → RESUMEN → Enviar | Corregir | Cancelar

Cada material queda listo, en revisión (lo confirma el equipo), por preparar (fuera del envío,
con el consejo) o no se recibe (con la alternativa). Nada se crea hasta «Enviar solicitud».
Las fichas vienen de la API (`GET /v1/residuos`); el bot no decide qué se recibe.
El borrador vive en memoria por celular (2 h); para varias réplicas, pasarlo a Redis.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app import textos as T
from app.brota import Brota, ErrorBrota
from app.catalogo import buscar, normalizar
from app.whatsapp import Boton, Entrante, Fila, WhatsApp

INCLUIDOS = ("listo", "revision")
CONFIRMAR_ENVIO = {"enviar", "enviar solicitud", "enviala", "si", "si enviala", "dale", "confirmo"}


@dataclass
class Item:
    codigo: str
    fuente: str = "lista"
    estado: str = "pendiente"  # pendiente | listo | revision | preparar | no
    pregunta: int = 0
    respuestas: dict[str, str] = field(default_factory=dict)


@dataclass
class Borrador:
    paso: str = "ELIGE"  # ELIGE | CONFIRMA | CHEQUEO | MAS | RESUMEN
    items: list[Item] = field(default_factory=list)
    propuestos: list[str] = field(default_factory=list)
    actualizado: float = field(default_factory=time.monotonic)

    def item(self, codigo: str) -> Item | None:
        return next((i for i in self.items if i.codigo == codigo), None)

    def pendiente(self) -> Item | None:
        return next((i for i in self.items if i.estado == "pendiente"), None)


class Borradores:
    def __init__(self, ttl_segundos: int = 7200) -> None:
        self.ttl = ttl_segundos
        self._d: dict[str, Borrador] = {}

    def obtener(self, celular: str) -> Borrador | None:
        b = self._d.get(celular)
        if b is None or time.monotonic() - b.actualizado > self.ttl:
            self._d.pop(celular, None)
            return None
        b.actualizado = time.monotonic()
        return b

    def nuevo(self, celular: str) -> Borrador:
        self._d[celular] = Borrador()
        return self._d[celular]

    def borrar(self, celular: str) -> None:
        self._d.pop(celular, None)


def _nombre(f: dict[str, Any]) -> str:
    return f"{f['emoji']} {f['nombre']}"


def _campos(f: dict[str, Any]) -> dict[str, Any]:
    """La ficha con textos vacíos en vez de None, para formatear mensajes."""
    return {**f, **{k: f.get(k) or "" for k in ("preparacion", "evitar", "alternativa")}}


def _ficha(f: dict[str, Any]) -> str:
    """Tarjeta educativa de un material (para dudas)."""
    if f["acepta"] == "no":
        return T.FICHA_NO.format(**_campos(f)).rstrip()
    texto = (T.FICHA_SI if f["acepta"] == "si" else T.FICHA_REVISION).format(**_campos(f))
    return texto + (T.FICHA_EVITAR.format(evitar=f["evitar"]) if f.get("evitar") else "")


class Pedido:
    def __init__(self, wa: WhatsApp, api: Brota, borradores: Borradores | None = None) -> None:
        self.wa = wa
        self.api = api
        self.borradores = borradores or Borradores()

    def activo(self, celular: str) -> Borrador | None:
        return self.borradores.obtener(celular)

    async def fichas(self, celular: str) -> dict[str, dict[str, Any]]:
        return {f["codigo"]: f for f in await self.api.residuos(celular)}

    # ------------------------------------------------------------------ entradas

    async def empezar(self, celular: str) -> None:
        b = self.borradores.nuevo(celular)
        await self._elegir(celular, b, await self.fichas(celular))

    async def cancelar(self, celular: str) -> None:
        self.borradores.borrar(celular)
        await self.wa.texto(celular, T.P_CANCELADA)

    async def atender(self, m: Entrante, me: dict[str, Any]) -> bool:
        """Atiende botones P_* y el texto mientras hay un borrador. False: no era para el pedido."""
        accion, _, resto = (m.respuesta_id or "").partition(":")
        b = self.borradores.obtener(m.de)
        if not accion.startswith("P_") and (b is None or m.tipo != "text"):
            return False
        fichas = await self.fichas(m.de)
        cel = m.de

        if accion in ("P_ADD", "P_ADDS"):
            b = b or self.borradores.nuevo(cel)
            await self._agregar(cel, b, fichas, resto.split(","), "lista" if accion == "P_ADD" else "texto")
        elif accion == "P_OTRO":
            b = b or self.borradores.nuevo(cel)
            b.paso = "ELIGE"
            await self.wa.texto(cel, T.P_OTRO)
        elif b is None:  # botón de un pedido que ya venció o se envió
            await self.wa.texto(cel, T.P_SIN_BORRADOR)
            await self.empezar(cel)
        elif accion == "P_SI_TEXTO":
            await self._agregar(cel, b, fichas, b.propuestos, "texto")
        elif accion == "P_NO_TEXTO":
            b.propuestos = []
            await self._elegir(cel, b, fichas)
        elif accion == "P_V" and resto.count(":") == 2:
            await self._responder(cel, b, fichas, *resto.split(":"))
        elif accion == "P_MAS":
            await self._elegir(cel, b, fichas)
        elif accion == "P_LISTO":
            await self._resumen(cel, b, fichas, me)
        elif accion == "P_ENVIAR":
            await self._enviar(m, b, fichas, me)
        elif accion == "P_CANCELAR":
            await self.cancelar(cel)
        elif accion == "P_CORREGIR":
            await self._corregir(cel, b, fichas)
        elif accion == "P_QUITAR":
            b.items = [i for i in b.items if i.codigo != resto]
            await (self._resumen(cel, b, fichas, me) if b.items else self._elegir(cel, b, fichas))
        elif accion == "P_REVISAR" and (it := b.item(resto)):
            it.estado, it.pregunta, it.respuestas = "pendiente", 0, {}
            await self._siguiente(cel, b, fichas)
        elif accion == "P_REINICIAR":
            await self.empezar(cel)
        elif accion == "P_SEGUIR":
            await self._seguir(cel, b, fichas, me)
        elif m.tipo == "text":
            await self._texto(m, b, fichas, me)
        else:
            await self._seguir(cel, b, fichas, me)
        return True

    async def responder_duda(self, celular: str, encontradas: list[dict[str, Any]]) -> None:
        if encontradas:
            await self.wa.texto(celular, "\n\n".join(_ficha(f) for f in encontradas[:3]))
        else:
            await self.wa.texto(celular, T.DUDA_NO_SE)
        aceptadas = [f["codigo"] for f in encontradas if f["acepta"] != "no"]
        pedir = Boton(f"P_ADDS:{','.join(aceptadas)}", "♻ Pedir recolección") if aceptadas else Boton(
            "M_PEDIR", "♻ Pedir recolección"
        )
        await self.wa.botones(celular, T.DUDA_SIGUE, [pedir, Boton("M_DUDA", "❓ Otra duda"), Boton("M_MENU", "🏠 Menú")])

    # ------------------------------------------------------------------ pasos

    async def _texto(self, m: Entrante, b: Borrador, fichas: dict[str, dict[str, Any]], me: dict[str, Any]) -> None:
        if b.paso == "RESUMEN" and normalizar(m.texto) in CONFIRMAR_ENVIO:
            await self._enviar(m, b, fichas, me)
            return
        if b.paso == "CHEQUEO":
            await self.wa.texto(m.de, T.P_TOCA_OPCION)
            await self._siguiente(m.de, b, fichas)
            return
        encontradas = buscar(m.texto, list(fichas.values()))
        if not encontradas:
            await self.wa.texto(m.de, T.P_NO_ENTENDI)
            await self._elegir(m.de, b, fichas)
            return
        b.propuestos = [f["codigo"] for f in encontradas]
        b.paso = "CONFIRMA"
        await self._confirmar_texto(m.de, b, fichas)

    async def _confirmar_texto(self, celular: str, b: Borrador, fichas: dict[str, dict[str, Any]]) -> None:
        nombres = [_nombre(fichas[c]) for c in b.propuestos if c in fichas]
        lista = ", ".join(nombres[:-1]) + f" y {nombres[-1]}" if len(nombres) > 1 else nombres[0]
        await self.wa.botones(
            celular, T.P_ENTENDI.format(lista=lista),
            [Boton("P_SI_TEXTO", "Sí, correcto"), Boton("P_NO_TEXTO", "Corregir")],
        )

    async def _elegir(self, celular: str, b: Borrador, fichas: dict[str, dict[str, Any]]) -> None:
        b.paso = "ELIGE"
        menu = sorted((f for f in fichas.values() if f["en_menu"]), key=lambda f: f["orden"])[:9]
        filas = [Fila(f"P_ADD:{f['codigo']}", _nombre(f), f.get("preparacion")) for f in menu]
        filas.append(Fila("P_OTRO", "✍ Otro: lo escribo", "Cuéntame con tus palabras qué tienes"))
        await self.wa.lista(celular, T.P_QUE_TIENES, "Elegir material", "Materiales", filas)

    async def _agregar(
        self, celular: str, b: Borrador, fichas: dict[str, dict[str, Any]], codigos: list[str], fuente: str
    ) -> None:
        for c in codigos:
            if c not in fichas:
                continue
            if b.item(c):
                await self.wa.texto(celular, T.P_YA_ESTA.format(**fichas[c]))
                continue
            b.items.append(Item(codigo=c, fuente=fuente))
        b.propuestos = []
        await self._siguiente(celular, b, fichas)

    async def _siguiente(self, celular: str, b: Borrador, fichas: dict[str, dict[str, Any]]) -> None:
        """Revisa el próximo material pendiente; si no queda ninguno, pregunta si hay algo más."""
        while (it := b.pendiente()) is not None:
            f = fichas.get(it.codigo)
            if f is None or f["acepta"] == "no":
                it.estado = "no"
                if f is not None:
                    await self.wa.texto(celular, T.P_NO_SE_RECIBE.format(**_campos(f)).rstrip())
                continue
            verificaciones = f["verificaciones"]
            if it.pregunta < len(verificaciones):
                b.paso = "CHEQUEO"
                await self._preguntar(celular, f, it)
                return
            it.estado = "revision" if f["acepta"] == "revision" else "listo"
            if verificaciones:
                await self.wa.texto(celular, T.P_LISTO.format(**f))
            else:  # sin preguntas: basta con enseñar cómo prepararlo
                extra = T.P_SIN_CHEQUEO_REVISION if it.estado == "revision" else "✅ Anotado."
                await self.wa.texto(celular, f"{_nombre(f)}: {f.get('preparacion') or ''}\n{extra}")
        if not b.items:
            await self._elegir(celular, b, fichas)
            return
        b.paso = "MAS"
        await self.wa.botones(
            celular, T.P_ALGO_MAS, [Boton("P_MAS", "➕ Agregar otro"), Boton("P_LISTO", "✅ Eso es todo")]
        )

    async def _preguntar(self, celular: str, f: dict[str, Any], it: Item) -> None:
        v = f["verificaciones"][it.pregunta]
        cuerpo = v["pregunta"]
        if it.pregunta == 0 and f.get("preparacion"):
            cuerpo = f"{_nombre(f)}: {f['preparacion']}\n\n{cuerpo}"
        botones = [Boton(f"P_V:{f['codigo']}:{v['id']}:{o['id']}", o["texto"]) for o in v["opciones"]]
        await self.wa.botones(celular, cuerpo, botones)

    async def _responder(
        self, celular: str, b: Borrador, fichas: dict[str, dict[str, Any]], codigo: str, pregunta: str, opcion: str
    ) -> None:
        it, f = b.item(codigo), fichas.get(codigo)
        v = f["verificaciones"][it.pregunta] if f and it and it.pregunta < len(f["verificaciones"]) else None
        o = next((x for x in v["opciones"] if x["id"] == opcion), None) if v and v["id"] == pregunta else None
        if it is None or f is None or o is None or it.estado != "pendiente":
            await self._siguiente(celular, b, fichas)  # botón viejo: retomar donde íbamos
            return
        it.respuestas[pregunta] = opcion
        consejo = o.get("consejo") or ""
        if o["resultado"] == "listo":
            it.pregunta += 1
            if consejo:  # listo, pero con algo que separar («saca los rotos»)
                await self.wa.texto(celular, f"💡 {consejo}")
        elif o["resultado"] == "revision":
            it.estado = "revision"
            await self.wa.texto(celular, T.P_REVISION.format(consejo=consejo or T.P_SIN_CHEQUEO_REVISION))
        elif o["resultado"] == "preparar":
            it.estado = "preparar"
            await self.wa.texto(celular, T.P_PREPARAR.format(consejo=consejo))
        else:
            it.estado = "no"
            await self.wa.texto(celular, f"🚫 {consejo}")
        await self._siguiente(celular, b, fichas)

    async def _resumen(self, celular: str, b: Borrador, fichas: dict[str, dict[str, Any]], me: dict[str, Any]) -> None:
        if b.pendiente():
            await self._siguiente(celular, b, fichas)
            return
        incluidos = [i for i in b.items if i.estado in INCLUIDOS and i.codigo in fichas]
        fuera = [_nombre(fichas[i.codigo]) for i in b.items if i.estado in ("preparar", "no") and i.codigo in fichas]
        if not incluidos:
            b.paso = "MAS"
            texto = T.P_NADA_LISTO.format(fuera=f"\nQueda por fuera: {', '.join(fuera)}." if fuera else "")
            await self.wa.botones(celular, texto, [Boton("P_MAS", "➕ Agregar otro"), Boton("P_CANCELAR", "❌ Cancelar")])
            return
        lineas = [
            _nombre(fichas[i.codigo]) + (" ✅" if i.estado == "listo" else " 🔎 lo revisa el equipo") for i in incluidos
        ]
        unidad = (me.get("unidades") or [{}])[0]
        b.paso = "RESUMEN"
        await self.wa.botones(
            celular,
            T.P_RESUMEN.format(
                incluidos="\n".join(lineas),
                ubicacion=unidad.get("etiqueta") or "tu apartamento",
                fuera=T.P_RESUMEN_FUERA.format(lista=", ".join(fuera)) if fuera else "",
            ),
            [Boton("P_ENVIAR", "✅ Enviar solicitud"), Boton("P_CORREGIR", "✏ Corregir"), Boton("P_CANCELAR", "❌ Cancelar")],
        )

    async def _enviar(self, m: Entrante, b: Borrador, fichas: dict[str, dict[str, Any]], me: dict[str, Any]) -> None:
        if b.paso != "RESUMEN":  # se envía solo lo que la persona vio en el resumen
            await self._resumen(m.de, b, fichas, me)
            return
        residuos = [
            {"residuo_id": fichas[i.codigo]["id"], "estado": i.estado, "respuestas": i.respuestas, "fuente": i.fuente}
            for i in b.items
            if i.estado in INCLUIDOS and i.codigo in fichas
        ]
        try:
            s = await self.api.crear_solicitud(m.de, m.wamid, residuos=residuos)
        except ErrorBrota as err:
            if err.codigo == "OPEN_REQUEST_EXISTS":
                self.borradores.borrar(m.de)
                await self.wa.texto(m.de, T.SOLICITUD_ABIERTA.format(codigo=err.datos.get("codigo_pasaporte", "")))
                return
            if err.codigo == "VALIDATION_ERROR":
                detalle = (err.datos.get("fields") or {}).get("residuos") or err.mensaje
                await self.wa.texto(m.de, T.P_INVALIDO.format(mensaje=detalle))
                return
            raise
        self.borradores.borrar(m.de)
        await self.wa.texto(m.de, T.P_ENVIADA.format(nombre=me.get("nombre") or "vecino", codigo=s["codigo_pasaporte"]))

    async def _corregir(self, celular: str, b: Borrador, fichas: dict[str, dict[str, Any]]) -> None:
        filas: list[Fila] = []
        for i in b.items[:8]:
            f = fichas.get(i.codigo)
            if f is None:
                continue
            if i.estado == "preparar":
                filas.append(Fila(f"P_REVISAR:{i.codigo}", f"🔁 Ya preparé {f['nombre']}"[:24], "Volver a revisarlo"))
            elif i.estado in INCLUIDOS:
                filas.append(Fila(f"P_QUITAR:{i.codigo}", f"➖ Quitar {f['nombre']}"[:24], "Sacarlo del pedido"))
        filas.append(Fila("P_MAS", "➕ Agregar material"))
        filas.append(Fila("P_REINICIAR", "🔁 Empezar de nuevo"))
        await self.wa.lista(celular, T.P_CORREGIR, "Ver opciones", "Tu pedido", filas)

    async def _seguir(self, celular: str, b: Borrador, fichas: dict[str, dict[str, Any]], me: dict[str, Any]) -> None:
        if b.paso == "RESUMEN":
            await self._resumen(celular, b, fichas, me)
        elif b.paso == "CONFIRMA" and b.propuestos:
            await self._confirmar_texto(celular, b, fichas)
        elif b.items:
            await self._siguiente(celular, b, fichas)
        else:
            await self._elegir(celular, b, fichas)
