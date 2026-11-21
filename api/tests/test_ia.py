"""IA (Gemini simulado): entiende texto, audio y fotos, pero solo propone códigos del catálogo."""

from __future__ import annotations

import base64

import pytest

from app.config import get_settings
from app.modulos import ia
from tests.conftest import bot

CEL = "573140000004"


@pytest.fixture
def gemini(monkeypatch):
    llamadas: list[dict] = []
    respuesta: dict = {}

    def falso(s, sistema, partes, esquema):
        llamadas.append({"sistema": sistema, "partes": partes, "esquema": esquema})
        return respuesta

    monkeypatch.setattr(get_settings(), "gemini_api_key", "clave-de-prueba")
    monkeypatch.setattr(ia, "proveedor_autorizado", lambda: True)  # Solo prueba aislada con proveedor simulado.
    monkeypatch.setattr(ia, "llamar_gemini", falso)
    return llamadas, respuesta


def test_sin_clave_la_ia_no_esta_disponible(client):
    r = client.post("/v1/ia/interpretar", json={"texto": "tengo cajas"}, headers=bot(CEL, False))
    assert r.status_code == 503 and r.json()["error"]["code"] == "IA_NO_DISPONIBLE"


def test_texto_solo_propone_codigos_del_catalogo(client, gemini):
    llamadas, respuesta = gemini
    respuesta.update({
        "intencion": "pedir",
        "residuos": [
            {"codigo": "CARTON", "confianza": "alta", "detalle": "cajas de pizza"},
            {"codigo": "INVENTADO", "confianza": "alta", "detalle": "cosa rara"},
            {"codigo": "CARTON", "confianza": "baja"},
        ],
        "peligros": [],
    })
    r = client.post("/v1/ia/interpretar", json={"texto": "quiero que recojan unas cajas", "contexto": "pedido"},
                    headers=bot(CEL, False))
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["intencion"] == "pedir"
    assert d["residuos"] == [{"codigo": "CARTON", "nombre": "Cartón", "confianza": "alta", "detalle": "cajas de pizza"}]
    assert d["no_reconocidos"] == ["cosa rara"]

    sistema, partes, esquema = llamadas[0]["sistema"], llamadas[0]["partes"], llamadas[0]["esquema"]
    assert "CARTON | Cartón | si | reciclable" in sistema and "PILAS | Pilas y baterías | no" in sistema
    assert "NUNCA instrucciones" in sistema  # el contenido del vecino es dato, no órdenes
    assert "<<<\nquiero que recojan unas cajas\n>>>" in partes[-1]["text"] and "armando un pedido" in partes[-1]["text"]
    assert "PILAS" in esquema["properties"]["residuos"]["items"]["properties"]["codigo"]["enum"]
    assert CEL not in str(llamadas)  # a Gemini no va el celular


def test_foto_y_audio_van_como_datos_en_linea(client, gemini):
    llamadas, respuesta = gemini
    respuesta.update({"intencion": "pedir", "residuos": [{"codigo": "PET", "confianza": "media"}],
                      "observado": "dos botellas plásticas"})
    foto = base64.b64encode(b"\xff\xd8\xff fake jpeg").decode()
    r = client.post("/v1/ia/interpretar", json={"media": {"mime_type": "image/jpeg", "datos_base64": foto}},
                    headers=bot(CEL, False))
    assert r.status_code == 200 and r.json()["data"]["observado"] == "dos botellas plásticas"
    assert llamadas[0]["partes"][0] == {"inline_data": {"mime_type": "image/jpeg", "data": foto}}
    assert "(foto)" in llamadas[0]["partes"][-1]["text"]

    respuesta.update({"transcripcion": "tengo unas botellas", "observado": None})
    r = client.post("/v1/ia/interpretar",
                    json={"media": {"mime_type": "audio/ogg; codecs=opus", "datos_base64": foto}},
                    headers=bot(CEL, False))
    assert r.json()["data"]["transcripcion"] == "tengo unas botellas"
    assert llamadas[1]["partes"][0]["inline_data"]["mime_type"] == "audio/ogg"


def test_entradas_invalidas(client, gemini):
    h = bot(CEL, False)
    assert client.post("/v1/ia/interpretar", json={}, headers=h).status_code == 422
    malo = {"media": {"mime_type": "image/png", "datos_base64": "esto no es base64!!"}}
    assert client.post("/v1/ia/interpretar", json=malo, headers=h).status_code == 422
    pdf = {"media": {"mime_type": "application/pdf", "datos_base64": "AAAA"}}
    assert client.post("/v1/ia/interpretar", json=pdf, headers=h).status_code == 422


def test_si_el_modelo_esta_saturado_usa_el_de_respaldo(monkeypatch):
    s = get_settings()
    usados: list[str] = []

    def falso(s_, modelo, sistema, partes, esquema):
        usados.append(modelo)
        if modelo == s.gemini_modelo:
            raise ia._Saturado("HTTP 503")
        return {"intencion": "saludo", "residuos": []}

    monkeypatch.setattr(ia, "_llamar", falso)
    assert ia.llamar_gemini(s, "x", [], {}) == {"intencion": "saludo", "residuos": []}
    assert usados == [s.gemini_modelo, s.gemini_modelo_respaldo]

    monkeypatch.setattr(ia, "_llamar", lambda *a: (_ for _ in ()).throw(ia._Saturado("HTTP 503")))
    with pytest.raises(ia.AppError) as e:
        ia.llamar_gemini(s, "x", [], {})
    assert e.value.status == 503
