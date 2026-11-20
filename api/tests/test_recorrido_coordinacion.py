"""Coordinación por WhatsApp: la coordinadora recibe la nueva orden y la gestiona con Brisa.

Usa la misma base de la sesión; el nombre hace que corra después de test_recorrido.py.
"""

from __future__ import annotations

from tests.conftest import BOT, bot, habilitar_piloto

COORD = "573110000001"  # celular de prueba de la coordinación de Asorescatar
VECINA = "573120000002"


def _vaciar_avisos(client) -> None:
    while client.post("/v1/canal/avisos/reservas", json={"limite": 50}, headers=BOT).json()["data"]:
        pass


def test_coordinacion_por_whatsapp(client, operador, catalogo):
    _vaciar_avisos(client)
    # 1. Administración asigna el celular de WhatsApp a la cuenta de coordinación.
    cuentas = client.get("/v1/cuentas-operadoras", headers=operador("admin", False)).json()["data"]
    coord = next(c for c in cuentas if c["usuario"] == "coord-reciclaje")
    r = client.patch(
        f"/v1/cuentas-operadoras/{coord['id']}",
        json={"version_esperada": coord["version"], "celular": COORD},
        headers=operador("admin"),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["celular"] == "+" + COORD

    # 2. Por WhatsApp, ese número es la coordinación (no un vecino sin registro).
    me = client.get("/v1/me", headers=bot(COORD, False)).json()["data"]
    assert me["tipo_actor"] == "operador" and me["permisos"][0]["rol"] == "coordinacion"

    # 3. Una vecina pide reciclables y orgánicos → solo Asorescatar tiene celular → 1 aviso.
    u = client.get(
        "/v1/unidades", params={"torre_id": catalogo["torre:5"], "referencia": "201"}, headers=bot(VECINA, False)
    ).json()["data"][0]
    client.post(
        "/v1/registros",
        json={"nombre": "Marta", "unidad_id": u["id"],
              "consentimiento": {"version_politica": "2026-11", "decision": "aceptado"}},
        headers=bot(VECINA),
    )
    habilitar_piloto(client, VECINA)
    s = client.post(
        "/v1/solicitudes",
        json={"tipo_servicio_ids": [catalogo["tipos_servicio:RECICLABLES"], catalogo["tipos_servicio:ORGANICOS"]],
              "observacion": "Cajas en la portería"},
        headers=bot(VECINA),
    ).json()["data"]
    avisos = client.post("/v1/canal/avisos/reservas", json={"limite": 50}, headers=BOT).json()["data"]
    nuevas = [a for a in avisos if a["tipo"] == "nueva_orden"]
    assert len(nuevas) == 1
    aviso = nuevas[0]
    assert aviso["destino"]["tipo"] == "operador" and aviso["destino"]["celular"] == "+" + COORD
    assert aviso["datos"]["codigo_pasaporte"] == s["codigo_pasaporte"]
    assert "Torre 5 · Apto 201" in aviso["datos"]["texto_sugerido"]
    assert "Cajas en la portería" in aviso["datos"]["texto_sugerido"]
    orden_id = aviso["datos"]["orden_id"]

    # 4. La coordinadora asigna y cierra desde WhatsApp (mismos endpoints y permisos que la tablet).
    rec = client.get("/v1/recolectores", headers=bot(COORD, False)).json()["data"][0]
    r = client.post(
        f"/v1/ordenes/{orden_id}/asignacion",
        json={"version_esperada": 1, "recolector_id": rec["id"], "forma_aviso": "llamada"},
        headers=bot(COORD),
    )
    assert r.status_code == 200, r.text
    r = client.post(
        f"/v1/ordenes/{orden_id}/resultado",
        json={"version_esperada": 2, "resultado": "recogida", "ocurrido_at": "2026-11-17T10:00:00-05:00"},
        headers=bot(COORD),
    )
    assert r.json()["data"]["evaluacion_puntos"] == "acreditada"
    tipos = {a["tipo"] for a in client.post("/v1/canal/avisos/reservas", json={"limite": 50}, headers=BOT).json()["data"]}
    assert tipos == {"asignacion", "recoleccion_confirmada"}

    # 5. La coordinación de Asorescatar no puede tocar la orden de la huerta.
    huerta = next(o for o in s["ordenes"] if o["gremio_id"] == catalogo["gremios:ECORAZON"])
    assert client.get(f"/v1/ordenes/{huerta['id']}", headers=bot(COORD, False)).status_code == 404

    # 6. El celular no puede repetirse entre cuentas.
    otra = next(c for c in cuentas if c["usuario"] == "coord-huerta")
    r = client.patch(f"/v1/cuentas-operadoras/{otra['id']}", json={"version_esperada": otra["version"], "celular": COORD},
                     headers=operador("admin"))
    assert r.status_code == 409
