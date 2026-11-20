"""Modo coordinación: la coordinadora asigna y cierra solicitudes desde WhatsApp."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app import avisos
from app.brota import Brota
from app.coordinacion import BOGOTA, franjas
from app.main import crear_app
from app.whatsapp import WhatsApp
from tests.test_bot import _texto, ajustes, enviar

COORD = "573110000001"
ORDEN = "0b6f0000-0000-4000-8000-000000000001"
REC = "0b6f0000-0000-4000-8000-0000000000aa"
MOTIVO = "0b6f0000-0000-4000-8000-0000000000bb"
GREMIO = "g-asorescatar"


class APICoordinacion:
    def __init__(self) -> None:
        self.orden = {
            "id": ORDEN, "version": 1, "estado": "nueva", "gremio_id": GREMIO, "codigo_pasaporte": "BR-00002",
            "ubicacion_operativa": "Torre 2 · Apto 403", "contacto_nombre": "Jeremy", "observacion": None,
            "asignacion": None,
        }
        self.escrituras: list[tuple[str, dict, str]] = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        p, m = req.url.path, req.method
        assert req.headers["X-Canal-Celular"] == COORD
        if p == "/v1/me":
            return _ok({"tipo_actor": "operador", "registrado": True, "nombre": "Coordinación Asorescatar",
                        "permisos": [{"rol": "coordinacion", "gremio_id": GREMIO}]})
        if p == "/v1/ordenes":
            estado = req.url.params["estado"]
            return _ok([self.orden] if self.orden["estado"] == estado else [])
        if p == f"/v1/ordenes/{ORDEN}":
            return _ok(self.orden)
        if p == "/v1/recolectores":
            return _ok([{"id": REC, "nombre": "Rosa (demo)", "telefono_contacto": "3001234567", "gremio_id": GREMIO}])
        if p == "/v1/catalogos":
            return _ok({"tipos_servicio": [], "motivos_rechazo": [
                {"id": MOTIVO, "codigo": "MOJADO", "nombre": "Material mojado", "gremio_id": None},
                {"id": "otro", "codigo": "X", "nombre": "De la huerta", "gremio_id": "g-huerta"},
            ]})
        cuerpo = json.loads(req.content) if req.content else {}
        if p == f"/v1/ordenes/{ORDEN}/asignacion" and m == "POST":
            assert cuerpo["version_esperada"] == self.orden["version"]
            self.escrituras.append(("asignacion", cuerpo, req.headers["Idempotency-Key"]))
            self.orden |= {"estado": "asignada", "version": self.orden["version"] + 1,
                           "asignacion": {"recolector_id": REC, "recolector_nombre": "Rosa (demo)"}}
            return _ok(self.orden)
        if p == f"/v1/ordenes/{ORDEN}/resultado" and m == "POST":
            if self.orden["estado"] != "asignada":
                return httpx.Response(409, json={"error": {"code": "INVALID_TRANSITION", "message": "x"}})
            self.escrituras.append(("resultado", cuerpo, req.headers["Idempotency-Key"]))
            self.orden |= {"estado": cuerpo["resultado"], "version": self.orden["version"] + 1}
            extra = {"puntos_otorgados": "10.00"} if cuerpo["resultado"] == "recogida" else {}
            return _ok(self.orden | extra)
        return httpx.Response(404, json={"error": {"code": "NOT_FOUND", "message": p}})


def _ok(data) -> httpx.Response:
    return httpx.Response(200, json={"data": data})


@pytest.fixture
def coord():
    api = APICoordinacion()
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(api))
    with TestClient(crear_app(ajustes(coordinacion_por_whatsapp=True), cliente, procesar_en_linea=True)) as c:
        yield c, api


def _filas(msj: dict) -> list[dict]:
    return msj["interactive"]["action"]["sections"][0]["rows"]


def _botones(msj: dict) -> list[str]:
    return [b["reply"]["id"] for b in msj["interactive"]["action"]["buttons"]]


def test_menu_de_coordinacion(coord):
    c, _ = coord
    r = enviar(c, "hola", de=COORD)
    assert "Tienes 1 solicitud nueva" in _texto(r[0])
    assert _botones(r[0]) == ["C_BANDEJA", "C_ASIGNADAS"]
    lista = enviar(c, boton="C_BANDEJA", de=COORD)[0]
    assert _filas(lista)[0] == {"id": f"C_ASG:{ORDEN}", "title": "BR-00002 T2 · 403", "description": "Jeremy"}


def test_asignar_y_cerrar_como_recogida(coord):
    c, api = coord
    rec = _filas(enviar(c, boton=f"C_ASG:{ORDEN}", de=COORD)[0])
    assert rec[0]["id"] == f"C_REC:{ORDEN}:{REC}" and rec[0]["description"] == "3001234567"
    fr = _filas(enviar(c, lista=rec[0]["id"], de=COORD)[0])
    assert fr[-1]["id"] == f"C_FRA:{ORDEN}:{REC}:SIN" and fr[-1]["title"] == "Sin hora fija"

    r = enviar(c, lista=fr[0]["id"], de=COORD, wamid="wamid.asignar")
    tipo, cuerpo, clave = api.escrituras[0]
    assert tipo == "asignacion" and clave == "wamid.asignar" and cuerpo["forma_aviso"] == "llamada"
    assert cuerpo["inicio"] < cuerpo["fin"]
    assert "asignada a Rosa (demo)" in _texto(r[0]) and "3001234567" in _texto(r[0])
    assert _botones(r[1]) == [f"C_OK:{ORDEN}", f"C_NO:{ORDEN}"]

    r = enviar(c, boton=f"C_OK:{ORDEN}", de=COORD)
    assert api.escrituras[1][1]["resultado"] == "recogida"
    assert "recogida" in _texto(r[0]) and "+10 puntos" in _texto(r[0])

    # Tocar otra vez un botón viejo no rompe nada.
    r = enviar(c, boton=f"C_OK:{ORDEN}", de=COORD)
    assert "ya cambió" in _texto(r[0])


def test_rechazo_con_motivo_del_gremio(coord):
    c, api = coord
    enviar(c, lista=f"C_FRA:{ORDEN}:{REC}:SIN", de=COORD)
    assert "inicio" not in api.escrituras[0][1]
    motivos = _filas(enviar(c, boton=f"C_NO:{ORDEN}", de=COORD)[0])
    assert [f["title"] for f in motivos] == ["Material mojado"]  # el de la huerta no aparece
    r = enviar(c, lista=motivos[0]["id"], de=COORD)
    assert api.escrituras[1][1] == {**api.escrituras[1][1], "resultado": "rechazada", "motivo_rechazo_id": MOTIVO}
    assert "no se pudo recoger" in _texto(r[0])


def test_franjas_futuras():
    assert [f for f, _ in franjas(datetime(2026, 11, 19, 15, 0, tzinfo=BOGOTA))][0] == "2026111914"  # queda 1 h
    tarde = datetime(2026, 11, 19, 15, 45, tzinfo=BOGOTA)
    ids = [f for f, _ in franjas(tarde)]
    assert ids[0] == "2026111916" and "2026111914" not in ids  # a 2–4 pm le quedan 15 min
    assert ids[-1] == "SIN" and len(ids) <= 10
    assert dict(franjas(tarde))["2026112008"] == "Mañana 8am–10am"


def _aviso_nueva_orden(**extra) -> dict:
    enviados: list[dict] = []

    def ruteo(req: httpx.Request) -> httpx.Response:
        if req.url.host == "graph.facebook.com":
            enviados.append(json.loads(req.content))
            return httpx.Response(200, json={"messages": [{"id": "wamid.x"}]})
        if req.url.path.endswith("/reservas"):
            return _ok([{"id": "a1", "tipo": "nueva_orden",
                         "destino": {"tipo": "operador", "celular": "+" + COORD, "nombre": "Coordinación"},
                         "datos": {"orden_id": ORDEN, "texto_sugerido": "🆕 Nueva solicitud BR-00002"}}])
        return _ok({})

    s = ajustes(whatsapp_dry_run=False, whatsapp_token="t", whatsapp_phone_number_id="123", **extra)

    async def correr():
        async with httpx.AsyncClient(transport=httpx.MockTransport(ruteo)) as cli:
            return await avisos.procesar_lote(WhatsApp(s, cli), Brota(s, cli), s)

    assert asyncio.run(correr()) == 1
    assert enviados[0]["to"] == COORD
    return enviados[0]


def test_aviso_nueva_orden_es_alerta_hacia_el_panel():
    msj = _aviso_nueva_orden(panel_coordinacion_url="https://panel.brota.test")
    assert msj["type"] == "text"
    assert "BR-00002" in msj["text"]["body"] and "panel de coordinación: https://panel.brota.test" in msj["text"]["body"]


def test_aviso_nueva_orden_con_boton_asignar_en_modo_respaldo():
    msj = _aviso_nueva_orden(coordinacion_por_whatsapp=True)
    assert _botones(msj) == [f"C_ASG:{ORDEN}", "C_BANDEJA"]


def test_coordinadora_por_whatsapp_recibe_el_enlace_al_panel():
    api = APICoordinacion()
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(api))
    s = ajustes(panel_coordinacion_url="https://panel.brota.test")
    with TestClient(crear_app(s, cliente, procesar_en_linea=True)) as c:
        r = enviar(c, boton=f"C_ASG:{ORDEN}", de=COORD)  # un botón viejo tampoco asigna
    assert "Tienes 1 solicitud nueva" in _texto(r[0]) and "https://panel.brota.test" in _texto(r[0])
    assert api.escrituras == []
