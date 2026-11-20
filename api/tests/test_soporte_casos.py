"""Casos (quejas y «hablar con una persona») y cancelación de solicitudes por el vecino.

Corre después de test_recorrido_coordinacion.py: la coordinación de reciclaje ya tiene celular.
"""

from __future__ import annotations

from tests.conftest import BOT, bot, habilitar_piloto

VECINO = "573150000005"


def _avisos(client) -> list[dict]:
    return client.post("/v1/canal/avisos/reservas", json={"limite": 50}, headers=BOT).json()["data"]


def _registrar(client, catalogo) -> None:
    u = client.get("/v1/unidades", params={"torre_id": catalogo["torre:1"], "referencia": "104"},
                   headers=bot(VECINO, False)).json()["data"][0]
    r = client.post("/v1/registros", json={"nombre": "Paola", "unidad_id": u["id"],
                    "consentimiento": {"version_politica": "2026-11", "decision": "aceptado"}}, headers=bot(VECINO))
    assert r.status_code == 201, r.text
    habilitar_piloto(client, VECINO)


def test_casos_llegan_a_la_coordinacion_y_la_respuesta_al_vecino(client, catalogo, operador):
    _registrar(client, catalogo)
    s = client.post("/v1/solicitudes", json={"tipo_servicio_ids": [catalogo["tipos_servicio:RECICLABLES"]]},
                    headers=bot(VECINO)).json()["data"]
    _avisos(client)

    r = client.post("/v1/casos", json={"tipo": "queja", "texto": "Nadie ha venido por mis cajas",
                                       "codigo_pasaporte": s["codigo_pasaporte"].lower()}, headers=bot(VECINO))
    assert r.status_code == 201, r.text
    queja = r.json()["data"]
    assert queja["codigo"].startswith("CA-") and queja["estado"] == "abierto"
    assert queja["gremio_id"] == catalogo["gremios:ASORESCATAR"] and queja["codigo_pasaporte"] == s["codigo_pasaporte"]
    assert queja["contacto_nombre"] == "Paola" and queja["ubicacion"] == "Torre 1 · Apto 104"
    alerta = next(a for a in _avisos(client) if a["tipo"] == "nuevo_caso")
    assert alerta["destino"]["tipo"] == "operador"
    assert "Nadie ha venido por mis cajas" in alerta["datos"]["texto_sugerido"]

    ayuda = client.post("/v1/casos", json={"tipo": "ayuda", "texto": "Quiero hablar con alguien"},
                        headers=bot(VECINO)).json()["data"]
    assert ayuda["gremio_id"] is None  # sin solicitud: lo ven todas las coordinaciones

    huerta = {c["codigo"] for c in client.get("/v1/casos", headers=operador("coord-huerta", False)).json()["data"]}
    assert ayuda["codigo"] in huerta and queja["codigo"] not in huerta
    reciclaje = client.get("/v1/casos", params={"estado": "abierto"},
                           headers=operador("coord-reciclaje", False)).json()["data"]
    assert {queja["codigo"], ayuda["codigo"]} <= {c["codigo"] for c in reciclaje}

    r = client.post(f"/v1/casos/{queja['id']}/atencion",
                    json={"version_esperada": queja["version"], "respuesta": "Rosa pasa mañana a las 9."},
                    headers=operador("coord-reciclaje"))
    assert r.status_code == 200 and r.json()["data"]["estado"] == "atendido"
    respuesta = next(a for a in _avisos(client) if a["tipo"] == "caso_respuesta")
    assert respuesta["destino"]["celular"] == "+" + VECINO
    assert "Rosa pasa mañana a las 9." in respuesta["datos"]["texto_sugerido"]
    otra = client.post(f"/v1/casos/{queja['id']}/atencion",
                       json={"version_esperada": queja["version"] + 1, "respuesta": "x"}, headers=operador("coord-reciclaje"))
    assert otra.status_code == 409
    # La huerta no puede atender un caso de reciclaje.
    assert client.post(f"/v1/casos/{queja['id']}/atencion", json={"version_esperada": 2, "respuesta": "x"},
                       headers=operador("coord-huerta")).status_code == 404


def test_el_vecino_cancela_y_puede_volver_a_pedir(client, catalogo, operador):
    s = client.get("/v1/solicitudes", params={"abiertas": "true"}, headers=bot(VECINO, False)).json()["data"][0]
    _avisos(client)
    r = client.post(f"/v1/solicitudes/{s['id']}/cancelacion", json={"motivo": "Ya lo llevé yo"}, headers=bot(VECINO))
    assert r.status_code == 200, r.text
    assert {o["estado"] for o in r.json()["data"]["ordenes"]} == {"cancelada"}
    aviso = next(a for a in _avisos(client) if a["tipo"] == "orden_cancelada")
    assert s["codigo_pasaporte"] in aviso["datos"]["texto_sugerido"] and "Ya lo llevé yo" in aviso["datos"]["texto_sugerido"]

    assert client.post(f"/v1/solicitudes/{s['id']}/cancelacion", json={}, headers=bot(VECINO)).status_code == 409
    canceladas = client.get("/v1/ordenes", params={"estado": "cancelada"},
                            headers=operador("coord-reciclaje", False)).json()["data"]
    assert s["codigo_pasaporte"] in {o["codigo_pasaporte"] for o in canceladas}
    # Ya no está abierta: puede volver a pedir el mismo servicio.
    nueva = client.post("/v1/solicitudes", json={"tipo_servicio_ids": [catalogo["tipos_servicio:RECICLABLES"]]},
                        headers=bot(VECINO))
    assert nueva.status_code == 201
