"""Inicio de sesión del panel: freno a la fuerza bruta, mensajes genéricos, token y cabeceras."""

from __future__ import annotations

import jwt
import pytest

from app.config import get_settings
from app.core import limite_acceso


@pytest.fixture(autouse=True)
def _limpio():
    limite_acceso.reiniciar()
    yield
    limite_acceso.reiniciar()


def _entrar(client, usuario: str, pin: str):
    return client.post("/v1/auth/sesiones", json={"usuario": usuario, "pin": pin})


def test_usuario_inexistente_y_pin_errado_responden_igual(client):
    a = _entrar(client, "no-existe-nadie", "1111")
    b = _entrar(client, "coord-huerta", "1111")
    assert a.status_code == b.status_code == 401
    assert a.json()["error"]["message"] == b.json()["error"]["message"] == "Usuario o contraseña incorrectos."


def test_bloquea_tras_cinco_fallos_y_avisa_cuanto_esperar(client):
    for _ in range(get_settings().login_max_fallos):
        assert _entrar(client, "coord-huerta", "0000").status_code == 401
    r = _entrar(client, "coord-huerta", "2468")  # ni con el PIN correcto mientras dure el bloqueo
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
    assert int(r.headers["Retry-After"]) > 0
    # el bloqueo es del usuario atacado, no de los demás
    assert _entrar(client, "coord-reciclaje", "2468").status_code == 201


def test_un_ingreso_correcto_limpia_los_fallos(client):
    for _ in range(get_settings().login_max_fallos - 1):
        _entrar(client, "coord-huerta", "0000")
    assert _entrar(client, "coord-huerta", "2468").status_code == 201
    assert _entrar(client, "coord-huerta", "0000").status_code == 401  # vuelve a contar desde cero


def test_usuario_con_mayusculas_y_espacios(client):
    assert _entrar(client, "  Coord-Huerta ", "2468").status_code == 201


def test_token_trae_emisor_emision_e_identificador(client):
    token = _entrar(client, "coord-huerta", "2468").json()["data"]["token"]
    datos = jwt.decode(token, options={"verify_signature": False})
    assert datos["iss"] == "brota-api" and datos["typ"] == "operador"
    assert {"iat", "exp", "jti", "sub"} <= datos.keys()


def test_token_sin_emisor_se_rechaza(client):
    sub = jwt.decode(_entrar(client, "coord-huerta", "2468").json()["data"]["token"], options={"verify_signature": False})["sub"]
    viejo = jwt.encode({"sub": sub, "typ": "operador", "exp": 4102444800}, get_settings().jwt_secret, algorithm="HS256")
    r = client.get("/v1/cuentas-operadoras", headers={"Authorization": f"Bearer {viejo}"})
    assert r.status_code == 401


def test_cabeceras_de_seguridad(client):
    r = _entrar(client, "coord-huerta", "2468")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Cache-Control"] == "no-store"
