"""Modo coordinación de Brisa: la coordinadora gestiona su bandeja desde WhatsApp.

Se activa cuando `GET /v1/me` dice `tipo_actor = operador` (cuenta de coordinación con celular).
Cada botón o fila lleva en su `id` la orden y lo elegido, así el flujo no depende de memoria:

    C_BANDEJA / C_ASIGNADAS / C_PROGRAMADAS → listas de órdenes por estado
    C_ASG:<orden>                        → elegir recolector
    C_REC:<orden>:<recolector>           → elegir franja
    C_FRA:<orden>:<recolector>:<franja>  → asignar sin hora o elegir canal del acuerdo
    C_CER:<orden>                        → ¿cómo le fue?
    C_OK:<orden>                         → solicitar códigos de materiales para cerrar
    C_NO:<orden> → C_MOT:<orden>:<motivo>:<versión> → rechazada con motivo

El recolector no usa el sistema: Brisa le muestra a la coordinadora su teléfono para llamarlo.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from app import textos as T
from app.brota import Brota, ErrorBrota
from app.whatsapp import Boton, Entrante, Fila, WhatsApp

BOGOTA = timezone(timedelta(hours=-5))
FRANJAS_HORAS = [(8, 10), (10, 12), (14, 16), (16, 18)]
CANALES = {"whatsapp": "WhatsApp", "llamada": "Llamada", "presencial": "Presencial"}


def _h(hora: int) -> str:
    return f"{hora % 12 or 12}{'am' if hora < 12 else 'pm'}"


def franjas(ahora: datetime | None = None) -> list[tuple[str, str]]:
    """(id, título) de las próximas franjas de recolección en hora de Bogotá."""
    ahora = (ahora or datetime.now(BOGOTA)).astimezone(BOGOTA)
    salida: list[tuple[str, str]] = []
    for dias, etiqueta in ((0, "Hoy"), (1, "Mañana")):
        dia = (ahora + timedelta(days=dias)).date()
        for ini, fin in FRANJAS_HORAS:
            fin_dt = datetime(dia.year, dia.month, dia.day, fin, tzinfo=BOGOTA)
            if fin_dt - timedelta(minutes=30) <= ahora:
                continue
            salida.append((f"{dia:%Y%m%d}{ini:02d}", f"{etiqueta} {_h(ini)}–{_h(fin)}"))
    salida.append(("SIN", "Sin hora fija"))
    return salida[:10]


def _rango(franja: str) -> tuple[str | None, str | None]:
    if franja == "SIN":
        return None, None
    inicio = datetime.strptime(franja, "%Y%m%d%H").replace(tzinfo=BOGOTA)
    fin_h = dict(FRANJAS_HORAS).get(inicio.hour, inicio.hour + 2)
    return inicio.isoformat(), inicio.replace(hour=fin_h).isoformat()


def _fila_orden(o: dict[str, Any], prefijo: str) -> Fila:
    # «Torre 2 · Apto 403» → «T2 · 403» para caber en 24 caracteres.
    ubic = o.get("ubicacion_operativa", "").replace("Torre ", "T").replace("Apto ", "")
    return Fila(f"{prefijo}:{o['id']}", f"{o['codigo_pasaporte']} {ubic}"[:24],
                f"{o.get('contacto_nombre') or ''} · {o.get('observacion') or ''}".strip(" ·")[:72] or None)


def _cuantas(n: int) -> str:
    if n == 0:
        return "No tienes solicitudes nuevas."
    return f"Tienes {n}{'+' if n >= 10 else ''} solicitud{'es' if n != 1 else ''} nueva{'s' if n != 1 else ''}."


class Coordinacion:
    def __init__(self, wa: WhatsApp, api: Brota) -> None:
        self.wa = wa
        self.api = api

    async def atender(self, m: Entrante, me: dict[str, Any]) -> None:
        if not self.wa.settings.coordinacion_por_whatsapp:
            await self._solo_panel(m.de, me)
            return
        opcion = m.respuesta_id or ""
        texto = (m.texto or "").strip()
        comando = texto.lower()
        accion, _, resto = opcion.partition(":")
        partes = resto.split(":") if resto else []
        try:
            if accion == "C_BANDEJA" or comando in ("bandeja", "nuevas"):
                await self._lista(m.de, "nueva", "C_ASG", T.C_SIN_NUEVAS, T.C_LISTA_NUEVAS)
            elif accion == "C_ASIGNADAS" or comando == "asignadas":
                await self._lista(m.de, "asignada", "C_HOR", T.C_SIN_ASIGNADAS, T.C_LISTA_ASIGNADAS)
            elif accion == "C_PROGRAMADAS" or comando == "programadas":
                await self._lista(m.de, "programada", "C_CER", T.C_SIN_PROGRAMADAS, T.C_LISTA_PROGRAMADAS)
            elif accion == "C_ASG" and len(partes) == 1:
                await self._elegir_recolector(m.de, partes[0])
            elif accion == "C_REC" and len(partes) == 2:
                await self._elegir_franja(m.de, *partes)
            elif accion == "C_HOR" and len(partes) == 1:
                await self._horario_asignada(m.de, partes[0])
            elif accion == "C_FRA" and len(partes) == 3:
                await self._elegir_canal(m, *partes)
            elif (accion == "C_CAN" and len(partes) == 5 and partes[3] in CANALES
                  and partes[4].isascii() and partes[4].isdigit()):
                orden, recolector, franja, canal, version = partes
                await self._asignar(m, orden, recolector, franja, canal, int(version))
            elif accion == "C_CER" and len(partes) == 1:
                await self._preguntar_resultado(m.de, partes[0])
            elif accion == "C_OK" and len(partes) == 1:
                await self._pedir_materiales(m.de, partes[0])
            elif comando.startswith("recogida "):
                await self._recogida(m, texto)
            elif accion == "C_NO" and len(partes) == 1:
                await self._elegir_motivo(m.de, partes[0])
            elif accion == "C_MOT" and len(partes) == 3:
                o = await self.api.orden(m.de, partes[0])
                if str(o["version"]) == partes[2]:
                    await self._resultado(m, o, "rechazada", [], partes[1])
                else:
                    await self.wa.texto(m.de, T.C_ORDEN_CAMBIO)
            elif accion == "C_MOT":
                await self.wa.texto(m.de, T.C_ORDEN_CAMBIO)
            else:
                await self._menu(m.de, me)
        except ErrorBrota as e:
            if e.codigo in ("VERSION_CONFLICT", "INVALID_TRANSITION"):
                await self.wa.texto(m.de, T.C_ORDEN_CAMBIO)
            elif e.codigo == "NOT_FOUND":
                await self.wa.texto(m.de, T.C_ORDEN_NO_ENCONTRADA)
            else:
                raise

    async def _solo_panel(self, celular: str, me: dict[str, Any]) -> None:
        nuevas = await self.api.ordenes(celular, "nueva")
        url = self.wa.settings.panel_coordinacion_url
        await self.wa.texto(celular, T.C_SOLO_PANEL.format(
            nombre=me.get("nombre") or "coordinación", cuantas=_cuantas(len(nuevas)), enlace=f": {url}" if url else "",
        ))

    async def _menu(self, celular: str, me: dict[str, Any]) -> None:
        nuevas = await self.api.ordenes(celular, "nueva")
        await self.wa.botones(
            celular,
            T.C_MENU.format(nombre=me.get("nombre") or "coordinación", cuantas=_cuantas(len(nuevas))),
            [Boton("C_BANDEJA", "📋 Nuevas"), Boton("C_ASIGNADAS", "🚲 Asignadas"),
             Boton("C_PROGRAMADAS", "🗓 Programadas")],
            T.C_MENU_PIE,
        )

    async def _lista(self, celular: str, estado: str, prefijo: str, vacia: str, titulo: str) -> None:
        ordenes = await self.api.ordenes(celular, estado)
        if not ordenes:
            await self.wa.texto(celular, vacia)
            return
        await self.wa.lista(celular, titulo, "Ver solicitudes", "Solicitudes",
                            [_fila_orden(o, prefijo) for o in ordenes])

    async def _elegir_recolector(self, celular: str, orden_id: str) -> None:
        o = await self.api.orden(celular, orden_id)
        if o["estado"] not in ("nueva", "asignada"):
            await self.wa.texto(celular, T.C_ORDEN_CAMBIO)
            return
        recolectores = await self.api.recolectores(celular, o["gremio_id"])
        if not recolectores:
            await self.wa.texto(celular, T.C_SIN_RECOLECTORES)
            return
        filas = [Fila(f"C_REC:{orden_id}:{r['id']}", r["nombre"], r.get("telefono_contacto") or "sin teléfono")
                 for r in recolectores]
        await self.wa.lista(celular, T.C_ELIGE_RECOLECTOR.format(codigo=o["codigo_pasaporte"],
                            ubicacion=o["ubicacion_operativa"]), "Elegir recolector", "Recolectores", filas)

    async def _horario_asignada(self, celular: str, orden_id: str) -> None:
        o = await self.api.orden(celular, orden_id)
        if o["estado"] != "asignada" or not o.get("asignacion"):
            await self.wa.texto(celular, T.C_ORDEN_CAMBIO)
            return
        await self._elegir_franja(celular, orden_id, o["asignacion"]["recolector_id"], permitir_sin_hora=False)

    async def _elegir_franja(
        self, celular: str, orden_id: str, recolector_id: str, permitir_sin_hora: bool = True,
    ) -> None:
        filas = [Fila(f"C_FRA:{orden_id}:{recolector_id}:{fid}", titulo) for fid, titulo in franjas()
                 if permitir_sin_hora or fid != "SIN"]
        await self.wa.lista(celular, T.C_ELIGE_FRANJA, "Elegir horario", "Horario", filas)

    async def _elegir_canal(self, m: Entrante, orden_id: str, recolector_id: str, franja: str) -> None:
        if franja == "SIN":
            await self._asignar(m, orden_id, recolector_id, franja)
            return
        o = await self.api.orden(m.de, orden_id)
        if not self._puede_asignar(o, recolector_id, franja) or franja not in dict(franjas()):
            await self.wa.texto(m.de, T.C_ORDEN_CAMBIO)
            return
        await self.wa.botones(m.de, T.C_ELIGE_CANAL, [
            Boton(f"C_CAN:{orden_id}:{recolector_id}:{franja}:{canal}:{o['version']}", titulo)
            for canal, titulo in CANALES.items()
        ])

    async def _asignar(
        self, m: Entrante, orden_id: str, recolector_id: str, franja: str,
        canal: str | None = None, version: int | None = None,
    ) -> None:
        o = await self.api.orden(m.de, orden_id)
        opciones = dict(franjas())
        if (not self._puede_asignar(o, recolector_id, franja) or franja not in opciones
                or (version is not None and o["version"] != version)):
            await self.wa.texto(m.de, T.C_ORDEN_CAMBIO)
            return
        inicio, fin = _rango(franja)
        asignada = await self.api.asignar(m.de, m.wamid, orden_id, o["version"], recolector_id, inicio, fin, canal)
        rec = next((r for r in await self.api.recolectores(m.de, o["gremio_id"]) if r["id"] == recolector_id), {})
        tel = rec.get("telefono_contacto")
        llamar = T.C_LLAMAR.format(nombre=rec.get("nombre", "al recolector"), telefono=tel) if tel else T.C_RECADO
        horario = opciones[franja].lower()
        await self.wa.texto(m.de, T.C_ASIGNADA.format(
            codigo=asignada["codigo_pasaporte"], recolector=asignada["asignacion"]["recolector_nombre"],
            horario=horario, llamar=llamar))
        if asignada["estado"] == "programada":
            await self._preguntar_resultado(m.de, orden_id, asignada)
        else:
            await self.wa.texto(m.de, T.C_FALTA_HORARIO)

    @staticmethod
    def _puede_asignar(o: dict[str, Any], recolector_id: str, franja: str) -> bool:
        asignacion = o.get("asignacion") or {}
        return o["estado"] == "nueva" or (
            o["estado"] == "asignada" and franja != "SIN" and asignacion.get("recolector_id") == recolector_id
        )

    async def _preguntar_resultado(self, celular: str, orden_id: str, o: dict[str, Any] | None = None) -> None:
        o = o or await self.api.orden(celular, orden_id)
        if o["estado"] != "programada":
            await self.wa.texto(celular, T.C_ORDEN_CAMBIO)
            return
        nombre = (o.get("asignacion") or {}).get("recolector_nombre", "el recolector")
        await self.wa.botones(
            celular, T.C_COMO_LE_FUE.format(codigo=o["codigo_pasaporte"], ubicacion=o["ubicacion_operativa"],
                                            recolector=nombre),
            [Boton(f"C_OK:{orden_id}", "✅ Recogida"), Boton(f"C_NO:{orden_id}", "❌ Rechazada")],
        )

    async def _elegir_motivo(self, celular: str, orden_id: str) -> None:
        o = await self.api.orden(celular, orden_id)
        if o["estado"] != "programada":
            await self.wa.texto(celular, T.C_ORDEN_CAMBIO)
            return
        cat = await self.api.catalogo(celular)
        motivos = [x for x in cat["motivos_rechazo"] if x.get("gremio_id") in (None, o["gremio_id"])]
        if not motivos:
            await self.wa.texto(celular, T.C_SIN_MOTIVOS)
            return
        filas = [Fila(f"C_MOT:{orden_id}:{x['id']}:{o['version']}", x["nombre"]) for x in motivos]
        await self.wa.lista(celular, T.C_ELIGE_MOTIVO, "Elegir motivo", "Motivos", filas)

    async def _materiales(self, celular: str, gremio_id: str) -> dict[str, dict[str, Any]]:
        cat = await self.api.catalogo(celular)
        return {m["codigo"]: m for m in cat["materiales"] if m["gremio_id"] == gremio_id}

    async def _pedir_materiales(self, celular: str, orden_id: str) -> None:
        o = await self.api.orden(celular, orden_id)
        if o["estado"] != "programada":
            await self.wa.texto(celular, T.C_ORDEN_CAMBIO)
            return
        materiales = await self._materiales(celular, o["gremio_id"])
        if not materiales:
            await self.wa.texto(celular, T.C_SIN_MATERIALES)
            return
        await self.wa.texto(celular, T.C_CONFIRMA_MATERIALES.format(orden=orden_id, version=o["version"]))
        lineas = [f"{codigo} · {m['nombre']}" for codigo, m in materiales.items()]
        for inicio in range(0, len(lineas), 20):
            await self.wa.texto(celular, "\n".join(lineas[inicio:inicio + 20]))

    async def _recogida(self, m: Entrante, texto: str) -> None:
        try:
            _, identificador, version, lista = texto.split(maxsplit=3)
            orden_id = str(UUID(identificador))
            version_esperada = int(version)
        except ValueError:
            await self.wa.texto(m.de, T.C_MATERIALES_INVALIDOS)
            return
        o = await self.api.orden(m.de, orden_id)
        if o["estado"] != "programada" or o["version"] != version_esperada:
            await self.wa.texto(m.de, T.C_ORDEN_CAMBIO)
            return
        materiales = await self._materiales(m.de, o["gremio_id"])
        codigos = list(dict.fromkeys(c.strip() for c in lista.split(",")))
        if len(codigos) > 50 or any(c not in materiales for c in codigos):
            await self.wa.texto(m.de, T.C_MATERIALES_INVALIDOS)
            return
        await self._resultado(m, o, "recogida", [materiales[c]["id"] for c in codigos])

    async def _resultado(
        self, m: Entrante, o: dict[str, Any], resultado: str, materiales: list[str], motivo_id: str | None = None,
    ) -> None:
        if o["estado"] != "programada":
            await self.wa.texto(m.de, T.C_ORDEN_CAMBIO)
            return
        r = await self.api.registrar_resultado(m.de, m.wamid, o["id"], o["version"], resultado, materiales, motivo_id)
        if resultado == "recogida":
            pts = str(r.get("puntos_otorgados") or "").removesuffix(".00")
            extra = f" {r.get('contacto_nombre') or 'El vecino'} ganó +{pts} puntos." if pts else ""
            await self.wa.texto(m.de, T.C_RECOGIDA.format(codigo=r["codigo_pasaporte"]) + extra)
        else:
            await self.wa.texto(m.de, T.C_RECHAZADA.format(codigo=r["codigo_pasaporte"]))
