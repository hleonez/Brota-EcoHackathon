"""Pedido guiado: Brisa enseña antes de pedir.

    ELIGE (lista o texto) → CONFIRMA (si fue texto) → CHEQUEO (preguntas de cada ficha)
    → MAS (¿algo más?) → RESUMEN (cuándo pasar) → Enviar | Corregir | Cancelar

Cada material queda listo, en revisión (lo confirma el equipo), por preparar (fuera del envío,
con el consejo) o no se recibe (con la alternativa). Nada se crea hasta «Enviar solicitud»,
y solo con una preferencia: cuando pueda, o una franja. Nunca las dos juntas.
Las fichas vienen de la API (`GET /v1/residuos`); el bot no decide qué se recibe.
El borrador vive en memoria por celular (2 h); para varias réplicas, pasarlo a Redis.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app import textos as T
from app.brota import Brota, ErrorBrota
from app.catalogo import buscar, normalizar
from app.ia import interpretar
from app.whatsapp import Boton, Entrante, Fila, WhatsApp

INCLUIDOS = ("listo", "revision")
CONFIRMAR_ENVIO = {"enviar", "enviar solicitud", "enviala", "si", "si enviala", "dale", "confirmo"}
REFERENCIAS = {"es eso", "eso", "eso mismo", "lo mismo", "eso es", "el mismo"}
PASOS_SIN_RECUERDO = {"CHEQUEO", "HORARIO", "RESUMEN"}
# Misma zona fija UTC-5 que usa liga_del_mes (America/Bogota, sin horario de verano).
ZONA = timezone(timedelta(hours=-5))
_FRANJA = re.compile(r"^(hoy|manana) (\d{1,2}) a (\d{1,2})$")


@dataclass
class Item:
    codigo: str
    fuente: str = "lista"
    estado: str = "pendiente"  # pendiente | listo | revision | preparar | no
    pregunta: int = 0
    respuestas: dict[str, str] = field(default_factory=dict)


@dataclass
class Borrador:
    paso: str = "ELIGE"  # ELIGE | CONFIRMA | CHEQUEO | MAS | RESUMEN | HORARIO
    items: list[Item] = field(default_factory=list)
    propuestos: list[str] = field(default_factory=list)
    fuente_propuesta: str = "texto"  # texto | foto | audio
    preferencia_sin_restriccion: bool = False
    preferencia_inicio: str | None = None
    preferencia_fin: str | None = None
    actualizado: float = field(default_factory=time.monotonic)

    def preferencia_lista(self) -> bool:
        """Una sola alternativa: sin restricción (sin fechas) o una ventana con fin posterior."""
        if self.preferencia_sin_restriccion:
            return self.preferencia_inicio is None and self.preferencia_fin is None
        return self.preferencia_inicio is not None and self.preferencia_fin is not None

    def item(self, codigo: str) -> Item | None:
        return next((i for i in self.items if i.codigo == codigo), None)

    def pendiente(self) -> Item | None:
        return next((i for i in self.items if i.estado == "pendiente"), None)


def frases_desconocidas(r: dict[str, Any] | None) -> list[str]:
    """Lo que la IA oyó y no está en el catálogo. Vacío si además propuso un código."""
    if not r or r.get("residuos"):
        return []
    vistos: list[str] = []
    for x in r.get("no_reconocidos") or []:
        frase = str(x).strip()
        if frase and frase not in vistos:
            vistos.append(frase)
    return vistos


def texto_con_recuerdo(texto: str | None, dicho: str | None, paso: str | None = None) -> str | None:
    """Ante «es eso», la IA recibe la frase anterior. El mensaje del vecino no se reescribe."""
    if not texto or not dicho or paso in PASOS_SIN_RECUERDO or normalizar(texto) not in REFERENCIAS:
        return texto
    return f"El vecino dijo antes: «{dicho}». Ahora escribe: «{texto}»"


def guardar_dicho(estado: Any, r: dict[str, Any] | None, texto: str | None) -> None:
    """Guarda la transcripción, o el texto si nombró algo fuera del catálogo."""
    if estado is None or not r:
        return
    transcripcion = (r.get("transcripcion") or "").strip()
    if transcripcion:
        estado.dicho = transcripcion
        return
    if frases_desconocidas(r) and (texto or "").strip() and normalizar(texto) not in REFERENCIAS:
        estado.dicho = texto.strip()


def _enumerar(nombres: list[str]) -> str:
    if len(nombres) == 1:
        return nombres[0]
    return ", ".join(nombres[:-1]) + f" y {nombres[-1]}"


def ahora_bogota() -> datetime:
    """Ahora en la zona fija UTC-5 que ya usa `liga_del_mes`."""
    return datetime.now(ZONA)


def interpretar_franja(texto: str | None) -> tuple[str, str] | None:
    """«hoy» o «mañana» y dos horas en 24 h, por ejemplo «mañana 9 a 12».

    Devuelve inicio y fin con la zona UTC-5. El fin tiene que ser posterior.
    Si el texto no calza, None: no se llama a la API.
    """
    coincidencia = _FRANJA.match(normalizar(texto))
    if coincidencia is None:
        return None
    hora_ini, hora_fin = int(coincidencia.group(2)), int(coincidencia.group(3))
    if hora_ini > 23 or hora_fin > 23 or hora_fin <= hora_ini:
        return None
    fecha = ahora_bogota().date()
    if coincidencia.group(1) == "manana":
        fecha += timedelta(days=1)
    inicio = datetime(fecha.year, fecha.month, fecha.day, hora_ini, tzinfo=ZONA)
    fin = datetime(fecha.year, fecha.month, fecha.day, hora_fin, tzinfo=ZONA)
    return inicio.isoformat(), fin.isoformat()


def _texto_franja(inicio: str, fin: str) -> str:
    ini, fin_dt = datetime.fromisoformat(inicio), datetime.fromisoformat(fin)
    hoy = ahora_bogota().date()
    if ini.date() == hoy:
        dia = "Hoy"
    elif ini.date() == hoy + timedelta(days=1):
        dia = "Mañana"
    else:
        dia = f"{ini.day}/{ini.month}"
    return f"{dia} de {ini.hour} a {fin_dt.hour}"


def _pregunta(b: Borrador) -> str:
    if not b.preferencia_lista():
        return T.P_PREGUNTA_PREFERENCIA
    if b.preferencia_sin_restriccion:
        return T.P_PREGUNTA_ENVIO
    return T.P_PREGUNTA_FRANJA.format(franja=_texto_franja(b.preferencia_inicio or "", b.preferencia_fin or ""))


def _botones_resumen(b: Borrador) -> list[Boton]:
    if not b.preferencia_lista():
        return [
            Boton("P_SIN", "Cuando pueda"),
            Boton("P_HORARIO", "Tengo un horario"),
            Boton("P_CORREGIR", "✏ Corregir"),
        ]
    return [
        Boton("P_ENVIAR", "✅ Enviar solicitud"),
        Boton("P_CORREGIR", "✏ Corregir"),
        Boton("P_CANCELAR", "❌ Cancelar"),
    ]


def _unidad_id_negocio(me: dict[str, Any]) -> str | None:
    """La única unidad, y solo si es un negocio. Un hogar o una unidad sin tipo no se manda."""
    unidades = me.get("unidades") or []
    if len(unidades) != 1 or unidades[0].get("tipo") != "negocio":
        return None
    identificador = unidades[0].get("id")
    return str(identificador) if identificador else None


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

    async def avisar_desconocido(
        self, celular: str, r: dict[str, Any] | None, encabezado: str | None = None
    ) -> bool:
        """Si no hay código y sí hay algo fuera del catálogo, lo nombra y ofrece a una persona."""
        nombres = frases_desconocidas(r)
        if not nombres:
            return False
        cuerpo = T.IA_FUERA_CATALOGO.format(lista=_enumerar(nombres))
        if encabezado:
            cuerpo = f"{encabezado}\n\n{cuerpo}"
        await self.wa.botones(
            celular, cuerpo,
            [Boton("M_PERSONA", "Hablar con alguien"), Boton("M_PEDIR", "Elegir material")],
        )
        return True

    async def atender(self, m: Entrante, me: dict[str, Any], estado: Any | None = None) -> bool:
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
            await self._agregar(cel, b, fichas, b.propuestos, b.fuente_propuesta)
        elif accion == "P_NO_TEXTO":
            b.propuestos = []
            await self._elegir(cel, b, fichas)
        elif accion == "P_V" and resto.count(":") == 2:
            await self._responder(cel, b, fichas, *resto.split(":"))
        elif accion == "P_MAS":
            await self._elegir(cel, b, fichas)
        elif accion == "P_LISTO":
            await self._resumen(cel, b, fichas, me)
        elif accion == "P_SIN":
            b.preferencia_sin_restriccion = True
            b.preferencia_inicio = b.preferencia_fin = None
            await self._resumen(cel, b, fichas, me)
        elif accion == "P_HORARIO":
            b.preferencia_sin_restriccion = False
            b.preferencia_inicio = b.preferencia_fin = None
            b.paso = "HORARIO"
            await self.wa.texto(cel, T.P_PIDE_HORARIO)
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
            await self._texto(m, b, fichas, me, estado)
        else:
            await self._seguir(cel, b, fichas, me)
        return True

    async def proponer(self, celular: str, codigos: list[str], fuente: str, encabezado: str | None = None) -> None:
        """Materiales detectados por texto, foto o audio: se confirman antes de revisarlos."""
        b = self.borradores.obtener(celular) or self.borradores.nuevo(celular)
        fichas = await self.fichas(celular)
        b.propuestos = [c for c in dict.fromkeys(codigos) if c in fichas]
        b.fuente_propuesta = fuente
        if not b.propuestos:
            await self._elegir(celular, b, fichas)
            return
        b.paso = "CONFIRMA"
        await self._confirmar_texto(celular, b, fichas, encabezado)

    async def responder_duda(
        self, celular: str, encontradas: list[dict[str, Any]], respuesta: str | None = None,
        encabezado: str | None = None,
    ) -> None:
        if respuesta:  # redactada por la IA con base en las fichas
            texto = respuesta
        elif encontradas:
            texto = "\n\n".join(_ficha(f) for f in encontradas[:3])
        else:
            texto = T.DUDA_NO_SE
        await self.wa.texto(celular, f"{encabezado}\n\n{texto}" if encabezado else texto)
        aceptadas = [f["codigo"] for f in encontradas if f["acepta"] != "no"]
        pedir = Boton(f"P_ADDS:{','.join(aceptadas)}", "♻ Pedir recolección") if aceptadas else Boton(
            "M_PEDIR", "♻ Pedir recolección"
        )
        await self.wa.botones(celular, T.DUDA_SIGUE, [pedir, Boton("M_DUDA", "❓ Otra duda"), Boton("M_MENU", "🏠 Menú")])

    # ------------------------------------------------------------------ pasos

    async def _texto(
        self, m: Entrante, b: Borrador, fichas: dict[str, dict[str, Any]], me: dict[str, Any],
        estado: Any | None = None,
    ) -> None:
        if b.paso == "HORARIO":
            await self._recibir_horario(m, b, fichas, me)
            return
        if b.paso == "RESUMEN" and normalizar(m.texto) in CONFIRMAR_ENVIO:
            await self._enviar(m, b, fichas, me)
            return
        if b.paso == "CHEQUEO":
            await self.wa.texto(m.de, T.P_TOCA_OPCION)
            await self._siguiente(m.de, b, fichas)
            return
        encontradas = buscar(m.texto, list(fichas.values()))
        if encontradas:
            await self.proponer(m.de, [f["codigo"] for f in encontradas], "texto")
            return
        # Los sinónimos no alcanzaron: que la IA lo intente (si está disponible).
        dicho = getattr(estado, "dicho", None) if estado is not None else None
        r = await interpretar(
            self.api, m.de, texto=texto_con_recuerdo(m.texto, dicho, b.paso), contexto="pedido",
        )
        guardar_dicho(estado, r, m.texto)
        if r and r["residuos"]:
            await self.proponer(m.de, [x["codigo"] for x in r["residuos"]], "texto")
        elif r and r.get("intencion") == "cancelar":
            await self.cancelar(m.de)
        elif r and await self.avisar_desconocido(m.de, r):
            return
        elif r and (r.get("respuesta") or r.get("aclaracion")):
            await self.wa.texto(m.de, r.get("respuesta") or r["aclaracion"])
            await self._elegir(m.de, b, fichas)
        else:
            await self.wa.texto(m.de, T.P_NO_ENTENDI)
            await self._elegir(m.de, b, fichas)

    async def _confirmar_texto(
        self, celular: str, b: Borrador, fichas: dict[str, dict[str, Any]], encabezado: str | None = None
    ) -> None:
        nombres = [_nombre(fichas[c]) for c in b.propuestos if c in fichas]
        lista = ", ".join(nombres[:-1]) + f" y {nombres[-1]}" if len(nombres) > 1 else nombres[0]
        cuerpo = T.P_ENTENDI.format(lista=lista)
        await self.wa.botones(
            celular, f"{encabezado}\n\n{cuerpo}" if encabezado else cuerpo,
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
        por_preparar = [_nombre(fichas[i.codigo]) for i in b.items if i.estado == "preparar" and i.codigo in fichas]
        no_va = [_nombre(fichas[i.codigo]) for i in b.items if i.estado == "no" and i.codigo in fichas]
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
                fuera=(T.P_RESUMEN_FUERA.format(lista=", ".join(por_preparar)) if por_preparar else "")
                + (T.P_RESUMEN_NO_VA.format(lista=", ".join(no_va)) if no_va else ""),
                pregunta=_pregunta(b),
            ),
            _botones_resumen(b),
        )

    async def _recibir_horario(
        self, m: Entrante, b: Borrador, fichas: dict[str, dict[str, Any]], me: dict[str, Any]
    ) -> None:
        franja = interpretar_franja(m.texto)
        if franja is None:
            await self.wa.texto(m.de, T.P_HORARIO_NO)
            return
        b.preferencia_sin_restriccion = False
        b.preferencia_inicio, b.preferencia_fin = franja
        await self._resumen(m.de, b, fichas, me)

    async def _enviar(self, m: Entrante, b: Borrador, fichas: dict[str, dict[str, Any]], me: dict[str, Any]) -> None:
        if b.paso == "HORARIO" or not b.preferencia_lista():
            if b.paso == "HORARIO":
                await self.wa.texto(m.de, T.P_PIDE_HORARIO)
            else:
                await self._resumen(m.de, b, fichas, me)
            return
        if b.paso != "RESUMEN":  # se envía solo lo que la persona vio en el resumen
            await self._resumen(m.de, b, fichas, me)
            return
        residuos = [
            {"residuo_id": fichas[i.codigo]["id"], "estado": i.estado, "respuestas": i.respuestas, "fuente": i.fuente}
            for i in b.items
            if i.estado in INCLUIDOS and i.codigo in fichas
        ]
        try:
            s = await self.api.crear_solicitud(
                m.de, m.wamid, residuos=residuos,
                preferencia_sin_restriccion=b.preferencia_sin_restriccion,
                preferencia_inicio=None if b.preferencia_sin_restriccion else b.preferencia_inicio,
                preferencia_fin=None if b.preferencia_sin_restriccion else b.preferencia_fin,
                unidad_id=_unidad_id_negocio(me),
            )
        except ErrorBrota as err:
            if err.codigo == "OPEN_REQUEST_EXISTS":
                self.borradores.borrar(m.de)
                await self.wa.texto(m.de, T.SOLICITUD_ABIERTA.format(codigo=err.datos.get("codigo_pasaporte", "")))
                return
            if err.codigo == "VALIDATION_ERROR":
                detalle = (err.datos.get("fields") or {}).get("residuos") or err.mensaje
                await self.wa.texto(m.de, T.P_INVALIDO.format(mensaje=detalle))
                return
            if err.codigo == "PILOT_NOT_ENABLED":
                # Si sube a atender, el vecino solo vería el fallo genérico.
                await self.wa.botones(m.de, T.PILOTO_NO, [Boton("M_DUDA", "📘 Ver la guía")])
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
        if b.paso == "HORARIO":
            await self.wa.texto(celular, T.P_PIDE_HORARIO)
        elif b.paso == "RESUMEN":
            await self._resumen(celular, b, fichas, me)
        elif b.paso == "CONFIRMA" and b.propuestos:
            await self._confirmar_texto(celular, b, fichas)
        elif b.items:
            await self._siguiente(celular, b, fichas)
        else:
            await self._elegir(celular, b, fichas)
