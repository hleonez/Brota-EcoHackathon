"""Trazabilidad (Administración): tablero Kanban de órdenes y la historia de cada una."""

from __future__ import annotations

from tests.conftest import BOT, bot, habilitar_piloto

VECINO = "573177700001"


def _solicitud(client, catalogo) -> dict:
    u = client.get(
        "/v1/unidades", params={"torre_id": catalogo["torre:3"], "referencia": "203"}, headers=bot(VECINO, False)
    ).json()["data"][0]
    r = client.post(
        "/v1/registros",
        json={"nombre": "Lucía Traza", "unidad_id": u["id"],
              "consentimiento": {"version_politica": "2026-11", "decision": "aceptado"}},
        headers=bot(VECINO),
    )
    assert r.status_code in (200, 201), r.text
    habilitar_piloto(client, VECINO)
    r = client.post(
        "/v1/solicitudes",
        json={"preferencia_sin_restriccion": True, "tipo_servicio_ids": [catalogo["tipos_servicio:RECICLABLES"]],
              "observacion": "Llamar al 3001234567 antes de subir"},
        headers=bot(VECINO),
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]


def test_tablero_e_historia_de_una_orden(client, operador, catalogo):
    s = _solicitud(client, catalogo)
    orden = s["ordenes"][0]
    admin = operador("admin", False)

    r = client.get("/v1/trazabilidad", params={"q": s["codigo_pasaporte"]}, headers=admin)
    assert r.status_code == 200, r.text
    cuerpo = r.json()["data"]
    assert cuerpo["resumen"]["por_estado"]["nueva"] == 1 and cuerpo["resumen"]["total"] == 1
    t = cuerpo["tarjetas"][0]
    assert t["orden_id"] == orden["id"] and t["estado"] == "nueva"
    assert t["contacto_nombre"] == "Lucía Traza" and t["gremio_nombre"]
    assert t["que"] and t["recolector_nombre"] is None
    assert "3001234567" not in r.text and VECINO not in r.text

    # La coordinación asigna con horario y cierra: el tablero y la historia lo reflejan.
    rec = client.get("/v1/recolectores", params={"gremio_id": orden["gremio_id"]},
                     headers=operador("coord-reciclaje", False)).json()["data"][0]
    r = client.post(
        f"/v1/ordenes/{orden['id']}/asignacion",
        json={"recolector_id": rec["id"], "forma_aviso": "llamada", "version_esperada": 1, "acuerdo_canal": "llamada",
              "inicio": "2026-11-20T14:00:00-05:00", "fin": "2026-11-20T16:00:00-05:00"},
        headers=operador("coord-reciclaje"),
    )
    assert r.status_code == 200, r.text
    t = client.get("/v1/trazabilidad", params={"q": s["codigo_pasaporte"]}, headers=admin).json()["data"]["tarjetas"][0]
    assert t["estado"] == "programada" and t["recolector_nombre"] == rec["nombre"] and t["inicio"]

    r = client.post(
        f"/v1/ordenes/{orden['id']}/resultado",
        json={"resultado": "recogida", "version_esperada": 2, "ocurrido_at": "2026-11-20T15:00:00-05:00",
              "materiales_confirmados": [catalogo["materiales:CARTON"]]},
        headers=operador("coord-reciclaje"),
    )
    assert r.status_code == 200, r.text

    h = client.get(f"/v1/trazabilidad/{orden['id']}", headers=admin)
    assert h.status_code == 200, h.text
    d = h.json()["data"]
    assert d["estado"] == "recogida" and d["cerrada_at"]
    eventos = [x["tipo"] for x in d["linea"] if x["clase"] == "evento"]
    assert eventos[:2] == ["solicitud_creada", "orden_creada"]
    assert {"orden_asignada", "orden_programada", "orden_recogida"} <= set(eventos)
    asignada = next(x for x in d["linea"] if x["tipo"] == "orden_asignada")
    assert asignada["datos"]["recolector_nombre"] == rec["nombre"] and asignada["actor_nombre"]
    avisos = {(x["tipo"], x["destino"]) for x in d["linea"] if x["clase"] == "aviso"}
    assert {("nueva_orden", "coordinacion"), ("asignacion", "vecino"), ("recoleccion_confirmada", "vecino")} <= avisos \
        or {("asignacion", "vecino"), ("recoleccion_confirmada", "vecino")} <= avisos
    assert [x["ocurrido_at"] for x in d["linea"]] == sorted(x["ocurrido_at"] for x in d["linea"])
    assert float(d["puntos_otorgados"]) >= 0
    assert "3001234567" not in h.text and VECINO not in h.text


def test_filtros_y_validacion(client, operador, catalogo):
    admin = operador("admin", False)
    r = client.get("/v1/trazabilidad", params={"gremio_id": catalogo["gremios:ECORAZON"]}, headers=admin)
    assert r.status_code == 200
    assert all(t["gremio_id"] == catalogo["gremios:ECORAZON"] for t in r.json()["data"]["tarjetas"])
    r = client.get("/v1/trazabilidad", params={"desde": "2026-11-20T00:00:00-05:00", "hasta": "2026-11-19T00:00:00-05:00"},
                   headers=admin)
    assert r.status_code == 422
    r = client.get("/v1/trazabilidad", params={"desde": "2020-01-01T00:00:00-05:00", "hasta": "2020-02-01T00:00:00-05:00"},
                   headers=admin)
    assert r.status_code == 200 and r.json()["data"]["tarjetas"] == [] and r.json()["data"]["resumen"]["ventana_dias_cerradas"] is None
    assert client.get("/v1/trazabilidad/00000000-0000-0000-0000-000000000000", headers=admin).status_code == 404


def test_coordinacion_ve_solo_su_gremio(client, operador, catalogo):
    reciclaje = catalogo["gremios:ASORESCATAR"]
    r = client.get("/v1/trazabilidad", headers=operador("coord-reciclaje", False))
    assert r.status_code == 200, r.text
    tarjetas = r.json()["data"]["tarjetas"]
    assert tarjetas and all(t["gremio_id"] == reciclaje for t in tarjetas)
    h = client.get(f"/v1/trazabilidad/{tarjetas[0]['orden_id']}", headers=operador("coord-reciclaje", False))
    assert h.status_code == 200
    assert all(o["orden_id"] is None for o in h.json()["data"]["otras_ordenes"])
    # La huerta no ve la orden del reciclaje ni puede pedir otro gremio.
    assert client.get(f"/v1/trazabilidad/{tarjetas[0]['orden_id']}", headers=operador("coord-huerta", False)).status_code == 404
    r = client.get("/v1/trazabilidad", params={"gremio_id": reciclaje}, headers=operador("coord-huerta", False))
    assert r.status_code == 403


def test_sin_permiso(client, operador):
    for usuario in ("fundacion", "reciclador-demo"):
        assert client.get("/v1/trazabilidad", headers=operador(usuario, False)).status_code == 403
    assert client.get("/v1/trazabilidad", headers=BOT).status_code in (401, 403)
    assert client.get("/v1/trazabilidad").status_code == 401
