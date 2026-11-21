"""Fichas de residuos: Brisa enseña antes de pedir y la solicitud guarda lo que el vecino declaró."""

from __future__ import annotations

from tests.conftest import BOT, bot, habilitar_piloto

VECINO = "573130000003"


def _fichas(client) -> dict[str, dict]:
    r = client.get("/v1/residuos", headers=bot(VECINO, False))
    assert r.status_code == 200, r.text
    return {x["codigo"]: x for x in r.json()["data"]}


def test_catalogo_de_fichas(client, catalogo):
    f = _fichas(client)
    carton = f["CARTON"]
    assert carton["acepta"] == "si" and carton["gremio_id"] == catalogo["gremios:ASORESCATAR"]
    assert carton["tipo_servicio_id"] == catalogo["tipos_servicio:RECICLABLES"]
    assert carton["verificaciones"][0]["opciones"][1] == {
        "id": "mojado", "texto": "Está mojado", "resultado": "preparar",
        "consejo": "Déjalo secar bajo techo y lo pides cuando esté seco. Si tiene grasa o comida, no lo reciben.",
    }
    assert f["FRUVER"]["tipo_servicio_id"] == catalogo["tipos_servicio:ORGANICOS"]
    pilas = f["PILAS"]
    assert pilas["acepta"] == "no" and pilas["gremio_id"] is None and pilas["alternativa"]
    menu = [x for x in f.values() if x["en_menu"]]
    assert 1 <= len(menu) <= 9  # caben en una lista de WhatsApp con la fila «Otro»
    assert all(len(f"{x['emoji']} {x['nombre']}") <= 24 for x in menu)  # título de fila
    for x in f.values():  # los textos de las opciones son botones de WhatsApp
        assert all(len(o["texto"]) <= 20 for v in x["verificaciones"] for o in v["opciones"])


def test_solicitud_con_residuos_declarados(client, catalogo, operador):
    f = _fichas(client)
    u = client.get(
        "/v1/unidades", params={"torre_id": catalogo["torre:4"], "referencia": "304"}, headers=bot(VECINO, False)
    ).json()["data"][0]
    r = client.post(
        "/v1/registros",
        json={"nombre": "Andrés", "unidad_id": u["id"],
              "consentimiento": {"version_politica": "2026-11", "decision": "aceptado"}},
        headers=bot(VECINO),
    )
    assert r.status_code == 201, r.text

    habilitar_piloto(client, VECINO)

    # Lo que no se recibe nunca entra a la ruta, ni una respuesta que la ficha no tiene.
    pilas = client.post("/v1/solicitudes", json={"preferencia_sin_restriccion": True, "residuos": [{"residuo_id": f["PILAS"]["id"]}]}, headers=bot(VECINO))
    assert pilas.status_code == 422 and "no se recibe" in pilas.json()["error"]["fields"]["residuos"]
    rara = client.post(
        "/v1/solicitudes",
        json={"preferencia_sin_restriccion": True, "residuos": [{"residuo_id": f["CARTON"]["id"], "respuestas": {"seco": "quizas"}}]},
        headers=bot(VECINO),
    )
    assert rara.status_code == 422
    assert client.post("/v1/solicitudes", json={}, headers=bot(VECINO)).status_code == 422

    # Sin tipo_servicio_ids: los servicios salen de los gremios de los residuos (una orden por gremio).
    r = client.post(
        "/v1/solicitudes",
        json={"preferencia_sin_restriccion": True, "residuos": [
            {"residuo_id": f["CARTON"]["id"], "respuestas": {"seco": "si"}, "fuente": "lista"},
            {"residuo_id": f["PET"]["id"], "respuestas": {"vacias": "si", "quimicos": "no"}, "fuente": "texto"},
            {"residuo_id": f["FRUVER"]["id"], "estado": "revision", "respuestas": {"separados": "duda"}},
        ]},
        headers=bot(VECINO),
    )
    assert r.status_code == 201, r.text
    s = r.json()["data"]
    assert set(s["tipo_servicio_ids"]) == {catalogo["tipos_servicio:RECICLABLES"], catalogo["tipos_servicio:ORGANICOS"]}
    por_gremio = {o["gremio_id"]: o for o in s["ordenes"]}
    reciclaje = por_gremio[catalogo["gremios:ASORESCATAR"]]
    assert [x["codigo"] for x in reciclaje["residuos"]] == ["CARTON", "PET"]
    assert [x["codigo"] for x in por_gremio[catalogo["gremios:ECORAZON"]]["residuos"]] == ["FRUVER"]

    # La coordinación ve qué materiales trae y qué respondió el vecino.
    o = client.get(f"/v1/ordenes/{reciclaje['id']}", headers=operador("coord-reciclaje", False)).json()["data"]
    carton = next(x for x in o["residuos"] if x["codigo"] == "CARTON")
    assert carton["chequeos"] == ["¿Tu cartón está limpio y seco? Sí, está listo"] and carton["estado"] == "listo"
    huerta = client.get(
        f"/v1/ordenes/{por_gremio[catalogo['gremios:ECORAZON']]['id']}", headers=operador("coord-huerta", False)
    ).json()["data"]
    assert huerta["residuos"][0]["estado"] == "revision"

    # El aviso a la coordinación nombra los materiales.
    avisos = client.post("/v1/canal/avisos/reservas", json={"limite": 50}, headers=BOT).json()["data"]
    textos = [a["datos"]["texto_sugerido"] for a in avisos if a["tipo"] == "nueva_orden"]
    assert any("📦 Cartón · 🧴 Botellas plásticas" in t for t in textos)
