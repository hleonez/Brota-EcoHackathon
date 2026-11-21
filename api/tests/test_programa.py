"""Configuración del programa: GET público y PATCH de Administración."""

from __future__ import annotations

from tests.conftest import BOT, clave

CLAVES = {"nombre_programa", "horario_atencion", "dias_recoleccion", "telefono_contacto", "correo_contacto",
          "mensaje_bienvenida"}


def _reiniciar(client, operador):
    r = client.patch("/v1/programa", json={c: None for c in CLAVES}, headers=operador("admin"))
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_get_publico_con_valores_por_defecto(client, operador):
    reiniciado = _reiniciar(client, operador)
    r = client.get("/v1/programa")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data == reiniciado
    assert set(data) == CLAVES
    assert data["nombre_programa"] == "EcoConecta Villas de San Pablo"
    assert data["horario_atencion"] == "Lunes a sábado, 8:00 a. m. a 5:00 p. m."
    assert data["dias_recoleccion"] == "Según la ruta de cada colectivo"
    assert data["telefono_contacto"] == data["correo_contacto"] == data["mensaje_bienvenida"] == ""
    assert client.get("/v1/programa", headers=BOT).status_code == 200


def test_patch_parcial_devuelve_todo(client, operador):
    _reiniciar(client, operador)
    r = client.patch("/v1/programa", json={"mensaje_bienvenida": "¡Hola! Soy Brisa 🌱", "correo_contacto": "eco@brota.co"},
                     headers=operador("admin"))
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert set(data) == CLAVES
    assert data["mensaje_bienvenida"] == "¡Hola! Soy Brisa 🌱" and data["correo_contacto"] == "eco@brota.co"
    assert data["nombre_programa"] == "EcoConecta Villas de San Pablo"

    r = client.patch("/v1/programa", json={"correo_contacto": "otro@brota.co"}, headers=operador("admin"))
    assert r.json()["data"]["correo_contacto"] == "otro@brota.co"
    assert r.json()["data"]["mensaje_bienvenida"] == "¡Hola! Soy Brisa 🌱"
    assert client.get("/v1/programa").json()["data"] == r.json()["data"]
    _reiniciar(client, operador)


def test_patch_idempotente(client, operador):
    h = {**operador("admin", False), **clave()}
    a = client.patch("/v1/programa", json={"dias_recoleccion": "Martes y jueves"}, headers=h)
    b = client.patch("/v1/programa", json={"dias_recoleccion": "Martes y jueves"}, headers=h)
    assert a.status_code == b.status_code == 200 and b.headers.get("Idempotent-Replayed") == "true"
    sin_clave = client.patch("/v1/programa", json={"dias_recoleccion": "x"}, headers=operador("admin", False))
    assert sin_clave.status_code == 400
    _reiniciar(client, operador)


def test_validaciones(client, operador):
    h = operador
    assert client.patch("/v1/programa", json={"clave_rara": "x"}, headers=h("admin")).status_code == 422
    assert client.patch("/v1/programa", json={"horario_atencion": "x" * 501}, headers=h("admin")).status_code == 422
    assert client.patch("/v1/programa", json={"correo_contacto": "no-es-correo"}, headers=h("admin")).status_code == 422
    assert client.patch("/v1/programa", json={"nombre_programa": ""}, headers=h("admin")).status_code == 422
    assert client.patch("/v1/programa", json={"horario_atencion": "x" * 500}, headers=h("admin")).status_code == 200
    _reiniciar(client, operador)


def test_solo_administracion_edita(client, operador):
    for usuario in ("coord-reciclaje", "fundacion"):
        assert client.patch("/v1/programa", json={"horario_atencion": "x"}, headers=operador(usuario)).status_code == 403
    assert client.patch("/v1/programa", json={"horario_atencion": "x"}, headers={**BOT, **clave()}).status_code == 403
    assert client.patch("/v1/programa", json={"horario_atencion": "x"}, headers=clave()).status_code == 401
