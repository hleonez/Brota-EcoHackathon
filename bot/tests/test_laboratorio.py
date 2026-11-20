"""Laboratorio (/lab): celulares simulados que nunca salen a Meta, solo accesible desde la máquina local."""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx
from fastapi.testclient import TestClient

from app.main import crear_app
from app.simular import payload
from tests.test_bot import SECRETO, APIFalsa, ajustes

LAURA = "573000000001"
REAL = "573001112233"


def _app(transporte, **extra) -> TestClient:
    s = ajustes(lab_activo=True, whatsapp_dry_run=False, whatsapp_token="t", whatsapp_phone_number_id="123", **extra)
    return TestClient(crear_app(s, httpx.AsyncClient(transport=httpx.MockTransport(transporte)), procesar_en_linea=True))


def test_apagado_por_defecto():
    with TestClient(crear_app(ajustes(), httpx.AsyncClient(), procesar_en_linea=True)) as c:
        assert c.get("/lab").status_code == 404


def test_no_responde_por_el_tunel():
    with _app(lambda r: httpx.Response(500)) as c:
        assert c.get("/lab").status_code == 200
        assert c.get("/lab", headers={"Cf-Connecting-Ip": "203.0.113.9"}).status_code == 404
        assert c.get("/lab/estado", headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 404


def test_celular_simulado_no_sale_a_meta_y_el_real_si():
    api = APIFalsa()
    a_meta: list[dict] = []

    def ruteo(req: httpx.Request) -> httpx.Response:
        if req.url.host == "graph.facebook.com":
            cuerpo = json.loads(req.content)
            a_meta.append(cuerpo)
            return httpx.Response(200, json={"messages": [{"id": f"wamid.meta.{len(a_meta)}"}]})
        return api(req)

    with _app(ruteo) as c:
        r = c.post("/lab/mensaje", json={"de": LAURA, "texto": "hola"})
        assert r.status_code == 200, r.text
        assert all(m.get("to") != LAURA for m in a_meta)  # ni la respuesta ni el «leído» van a Meta
        eventos = c.get("/lab/estado").json()["eventos"]
        assert [e["dir"] for e in eventos] == ["in", "out"]
        assert eventos[0]["texto"] == "hola" and "Soy Brisa" in eventos[1]["mensaje"]["text"]["body"]

        # Un celular real sigue yendo por Meta, y su conversación también se ve en el laboratorio.
        cuerpo = json.dumps(payload(REAL, "hola", None, None, "Jeremy")).encode()
        firma = "sha256=" + hmac.new(SECRETO.encode(), cuerpo, hashlib.sha256).hexdigest()
        c.post("/webhook", content=cuerpo, headers={"X-Hub-Signature-256": firma})
        assert any(m.get("to") == REAL for m in a_meta)
        estado = c.get("/lab/estado", params={"desde": 2}).json()
        assert {e["celular"] for e in estado["eventos"]} == {REAL}
        real = next(p for p in estado["personas"] if p["celular"] == REAL)
        assert real["simulado"] is False and "Jeremy" in real["nombre"] and REAL not in real["nombre"]

        # Desde el laboratorio no se puede escribir como un celular real.
        assert c.post("/lab/mensaje", json={"de": REAL, "texto": "hola"}).status_code == 400


def test_preparar_asigna_celulares_simulados_a_la_coordinacion():
    parches: list[tuple[str, dict, str]] = []
    cuentas = [
        {"id": "c1", "usuario": "coord-reciclaje", "celular": None, "version": 3},
        {"id": "c2", "usuario": "coord-huerta", "celular": "+573000000102", "version": 1},
    ]

    def ruteo(req: httpx.Request) -> httpx.Response:
        p = req.url.path
        if p == "/v1/auth/sesiones":
            if json.loads(req.content)["pin"] != "2468":
                return httpx.Response(401, json={"error": {"code": "INVALID_CREDENTIALS", "message": "x"}})
            return httpx.Response(201, json={"data": {"token": "jwt-admin"}})
        assert req.headers["Authorization"] == "Bearer jwt-admin"
        if p == "/v1/cuentas-operadoras":
            return httpx.Response(200, json={"data": cuentas})
        if req.method == "PATCH":
            parches.append((p, json.loads(req.content), req.headers["Idempotency-Key"]))
            return httpx.Response(200, json={"data": {}})
        return httpx.Response(404)

    with _app(ruteo) as c:
        assert c.post("/lab/preparar", json={"usuario": "admin", "pin": "0000"}).status_code == 401
        r = c.post("/lab/preparar", json={"usuario": "admin", "pin": "2468"})
        assert r.status_code == 200
        assert r.json()["data"] == [{"usuario": "coord-reciclaje", "estado": "lista"},
                                    {"usuario": "coord-huerta", "estado": "ya estaba lista"}]
        assert parches == [("/v1/cuentas-operadoras/c1", {"version_esperada": 3, "celular": "573000000101"},
                            parches[0][2])]
