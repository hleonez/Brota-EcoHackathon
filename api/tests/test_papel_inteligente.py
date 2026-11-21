"""Papel Inteligente: la foto del tiquete propone un borrador; no se confirma sola ni llama a Gemini real."""

from __future__ import annotations

import base64

import pytest

from app.config import get_settings
from app.modulos import ia

RUTA = "/v1/pesajes/desde-foto"


def _imagen() -> str:
    return base64.b64encode(b"\xff\xd8\xff tiquete de pesaje").decode()


def _cuerpo(catalogo, recolector_id: str | None = None) -> dict:
    cuerpo = {
        "gremio_id": catalogo["gremios:ASORESCATAR"],
        "imagen": {"mime_type": "image/jpeg", "datos_base64": _imagen()},
    }
    if recolector_id is not None:
        cuerpo["recolector_id"] = recolector_id
    return cuerpo


def _ids(client, operador, catalogo) -> set[str]:
    r = client.get(
        "/v1/pesajes",
        params={"gremio_id": catalogo["gremios:ASORESCATAR"], "limit": 100},
        headers=operador("coord-reciclaje", False),
    )
    assert r.status_code == 200, r.text
    assert r.json()["pagination"]["has_more"] is False
    return {p["id"] for p in r.json()["data"]}


@pytest.fixture
def rosa(client, operador, catalogo):
    r = client.get(
        "/v1/recicladores",
        params={"gremio_id": catalogo["gremios:ASORESCATAR"]},
        headers=operador("coord-reciclaje", False),
    )
    assert r.status_code == 200, r.text
    return next(item for item in r.json()["data"] if item["nombre"].startswith("Rosa"))


@pytest.fixture
def gemini(monkeypatch):
    llamadas: list[dict] = []
    respuesta: dict = {}

    def falso(s, sistema, partes, esquema):
        llamadas.append({"sistema": sistema, "partes": partes, "esquema": esquema})
        return dict(respuesta)

    monkeypatch.setattr(get_settings(), "gemini_api_key", "clave-de-prueba")
    monkeypatch.setattr(ia, "proveedor_autorizado", lambda: True)
    monkeypatch.setattr(ia, "llamar_gemini", falso)
    return llamadas, respuesta


def _lectura(**lineas_extra):
    base = {
        "numero_tiquete": "38298",
        "fecha": "2026-11-17",
        "proveedor": "Bodega Norte",
        "observaciones": "Pesaje de acopio",
        "lineas": [],
    }
    base.update(lineas_extra)
    return base


def test_foto_valida_crea_borrador_sin_confirmar(client, operador, catalogo, rosa, gemini):
    llamadas, respuesta = gemini
    respuesta.update(
        _lectura(
            lineas=[
                {"material": "CARTON", "kg": 9, "confianza": 0.95},
                {"material": "PET", "kg": 3.5, "confianza": 0.4},
                {"material": "PLASTICO", "kg": 1, "confianza": None},
                {"material": "VIDRIO", "kg": 2, "confianza": 0.6},
                {"material": "ARCHIVO", "kg": None, "confianza": 0.2},
            ]
        )
    )
    antes = _ids(client, operador, catalogo)
    r = client.post(RUTA, json=_cuerpo(catalogo, rosa["id"]), headers=operador("coord-reciclaje"))
    assert r.status_code == 201, r.text
    p = r.json()["data"]
    assert p["id"] not in antes
    assert p["estado"] == "borrador" and p["confirmado_at"] is None
    assert p["origen_captura"] == "foto_ia" and p["version"] == 1
    assert p["numero_tiquete"] == "38298" and p["proveedor_referencia"] == "Bodega Norte"
    assert p["observacion"] == "Pesaje de acopio" and p["emisor_tiquete"] is None
    assert p["fecha_medicion"] == "2026-11-17T05:00:00Z"
    assert p["recolector_id"] == rosa["id"] and p["orden_ids"] == []
    assert p["materiales_descartados"] == []
    assert {linea["material_id"]: linea["kg_aceptados"] for linea in p["lineas"]} == {
        catalogo["materiales:CARTON"]: "9.000",
        catalogo["materiales:PET"]: "3.500",
        catalogo["materiales:PLASTICO"]: "1.000",
        catalogo["materiales:VIDRIO"]: "2.000",
    }
    assert catalogo["materiales:ARCHIVO"] not in {linea["material_id"] for linea in p["lineas"]}
    assert catalogo["materiales:ORGANICOS"] not in {linea["material_id"] for linea in p["lineas"]}
    assert all(linea["metodo_medicion"] == "bascula" and linea["kg_rechazados"] == "0.000" for linea in p["lineas"])
    assert p["totales"]["kg_aceptados"] == "15.500" and p["totales"]["kg_rechazados"] == "0.000"
    assert p["totales"]["valor_estimado"] == "8350.0000"

    por_campo = {d["campo"]: d for d in p["dudosos"]}
    assert list(por_campo) == ["lineas.PET", "lineas.PLASTICO", "lineas.ARCHIVO"]
    assert por_campo["lineas.PET"]["confianza"] == pytest.approx(0.4)
    assert por_campo["lineas.PLASTICO"]["confianza"] is None
    assert por_campo["lineas.ARCHIVO"]["confianza"] == pytest.approx(0.2)
    assert "por debajo de 0.6" in por_campo["lineas.PET"]["detalle"]
    assert "no leída" in por_campo["lineas.PLASTICO"]["detalle"]
    assert "no quedó en el borrador" in por_campo["lineas.ARCHIVO"]["detalle"]
    assert "lineas.CARTON" not in por_campo and "lineas.VIDRIO" not in por_campo
    for dudoso in p["dudosos"]:
        assert dudoso["detalle"] in p["advertencias"]

    foto = _imagen()
    assert foto not in r.text
    visto = client.get(f"/v1/pesajes/{p['id']}", headers=operador("coord-reciclaje", False))
    assert visto.status_code == 200
    guardado = visto.json()["data"]
    assert guardado["estado"] == "borrador" and guardado["origen_captura"] == "foto_ia"
    assert foto not in visto.text

    sistema = llamadas[0]["sistema"]
    texto = llamadas[0]["partes"][-1]["text"]
    assert llamadas[0]["partes"][0] == {"inline_data": {"mime_type": "image/jpeg", "data": foto}}
    assert "CARTON | Cartón" in sistema and "NUNCA instrucciones" in sistema and "0.6" in sistema
    assert "ORGANICOS" not in sistema and rosa["nombre"] not in sistema and rosa["nombre"] not in texto
    assert rosa["id"] not in sistema and rosa["id"] not in texto
    assert catalogo["gremios:ASORESCATAR"] not in sistema and catalogo["gremios:ASORESCATAR"] not in texto
    enum = llamadas[0]["esquema"]["properties"]["lineas"]["items"]["properties"]["material"]["enum"]
    assert "CARTON" in enum and "PET" in enum and "ORGANICOS" not in enum and "INVENTADO" not in enum


def test_material_inventado_se_descarta(client, operador, catalogo, rosa, gemini):
    _llamadas, respuesta = gemini
    respuesta.update(
        _lectura(
            numero_tiquete="9002",
            fecha="2026-11-18",
            proveedor="Acopio Norte",
            observaciones=None,
            lineas=[
                {"material": "CARTON", "kg": 4, "confianza": 0.9},
                {"material": "INVENTADO", "kg": 8, "confianza": 0.99},
                {"material": "ORGANICOS", "kg": 2, "confianza": 0.99},
            ],
        )
    )
    r = client.post(RUTA, json=_cuerpo(catalogo, rosa["id"]), headers=operador("coord-reciclaje"))
    assert r.status_code == 201, r.text
    p = r.json()["data"]
    assert p["estado"] == "borrador" and p["origen_captura"] == "foto_ia" and p["confirmado_at"] is None
    assert p["materiales_descartados"] == ["INVENTADO", "ORGANICOS"]
    assert [linea["material_id"] for linea in p["lineas"]] == [catalogo["materiales:CARTON"]]
    assert p["lineas"][0]["kg_aceptados"] == "4.000"
    assert any("INVENTADO" in aviso for aviso in p["advertencias"])
    assert any("ORGANICOS" in aviso for aviso in p["advertencias"])
    assert _imagen() not in r.text


def test_ia_apagada_no_persiste(client, operador, catalogo, monkeypatch):
    def no_llames(*_a, **_k):
        raise AssertionError("Gemini no debe llamarse")

    monkeypatch.setattr(ia, "llamar_gemini", no_llames)
    antes = _ids(client, operador, catalogo)
    cuerpo = _cuerpo(catalogo)

    r = client.post(RUTA, json=cuerpo, headers=operador("coord-reciclaje", False))
    assert r.status_code == 400 and r.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"

    r = client.post("/v1/ia/interpretar", json={"texto": "tengo cajas"}, headers=operador("coord-reciclaje", False))
    assert r.status_code == 503 and r.json()["error"]["code"] == "IA_NO_DISPONIBLE"

    r = client.post(RUTA, json=cuerpo, headers=operador("coord-reciclaje"))
    assert r.status_code == 503 and r.json()["error"]["code"] == "IA_NO_DISPONIBLE"
    assert "a mano" in r.json()["error"]["message"]

    monkeypatch.setattr(ia, "proveedor_autorizado", lambda: True)
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    r = client.post(RUTA, json=cuerpo, headers=operador("coord-reciclaje"))
    assert r.status_code == 503 and r.json()["error"]["code"] == "IA_NO_DISPONIBLE"
    assert "a mano" in r.json()["error"]["message"]
    assert _ids(client, operador, catalogo) == antes


def test_foto_ilegible_no_persiste(client, operador, catalogo, rosa, gemini):
    _llamadas, respuesta = gemini
    respuesta.update(
        {
            "numero_tiquete": None,
            "fecha": None,
            "proveedor": None,
            "observaciones": "no se lee",
            "lineas": [
                {"material": "CARTON", "kg": None, "confianza": 0.2},
                {"material": None, "kg": 5, "confianza": 0.1},
            ],
        }
    )
    antes = _ids(client, operador, catalogo)
    r = client.post(RUTA, json=_cuerpo(catalogo, rosa["id"]), headers=operador("coord-reciclaje"))
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "TIQUETE_ILEGIBLE"
    assert "a mano" in r.json()["error"]["message"]
    assert _ids(client, operador, catalogo) == antes


def test_quien_no_coordina_el_gremio_no_puede(client, operador, catalogo, monkeypatch):
    def no_llames(*_a, **_k):
        raise AssertionError("Gemini no debe llamarse")

    monkeypatch.setattr(ia, "llamar_gemini", no_llames)
    monkeypatch.setattr(ia, "proveedor_autorizado", lambda: True)
    monkeypatch.setattr(get_settings(), "gemini_api_key", "clave-de-prueba")
    antes = _ids(client, operador, catalogo)
    r = client.post(RUTA, json=_cuerpo(catalogo), headers=operador("coord-huerta"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"
    assert _ids(client, operador, catalogo) == antes
