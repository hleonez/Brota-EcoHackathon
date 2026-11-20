"""Recorrido completo del piloto: registro por WhatsApp → solicitud mixta → coordinación →
avisos al bot → pesaje de lote → entrega directa con baldes → puntos → Liga → reportes → sync.

Las pruebas comparten estado y se ejecutan en orden.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import pytest

from tests.conftest import BOT, bot, habilitar_piloto

CARMEN = "573001112233"  # wa_id tal como lo envía WhatsApp
VECINO = "3005556677"  # móvil colombiano sin indicativo
E: dict = {}


def _err(r):
    return r.json()["error"]["code"]


def test_salud(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}
    caps = client.get("/v1/capacidades").json()["data"]
    assert caps["modulos"]["solicitudes"] and not caps["modulos"]["canjes"]


def test_sin_autenticacion(client):
    r = client.get("/v1/me")
    assert r.status_code == 401 and _err(r) == "UNAUTHORIZED"
    r = client.get("/v1/me", headers={"Authorization": "Bearer otro"})
    assert r.status_code == 401


def test_registro_por_whatsapp(client, catalogo):
    me = client.get("/v1/me", headers=bot(CARMEN, False)).json()["data"]
    assert me["registrado"] is False and me["tipo_actor"] == "no_registrado"

    # El canal no puede listar el directorio: solo coincidencia exacta torre + apartamento.
    r = client.get("/v1/unidades", headers=bot(CARMEN, False))
    assert r.status_code == 400
    r = client.get(
        "/v1/unidades", params={"torre_id": catalogo["torre:3"], "referencia": "402"}, headers=bot(CARMEN, False)
    )
    unidades = r.json()["data"]
    assert len(unidades) == 1 and unidades[0]["etiqueta"] == "Torre 3 · Apto 402"
    E["unidad_402"] = unidades[0]["id"]

    cuerpo = {
        "nombre": "Carmen",
        "unidad_id": E["unidad_402"],
        "consentimiento": {"version_politica": me["politica_datos_version"], "decision": "aceptado"},
    }
    r = client.post("/v1/registros", json=cuerpo, headers=bot(CARMEN))
    assert r.status_code == 201, r.text
    assert r.json()["data"]["estado_registro"] == "completo"
    habilitar_piloto(client, CARMEN)

    r = client.post("/v1/registros", json=cuerpo, headers=bot(CARMEN))
    assert r.status_code == 409 and _err(r) == "CONTACT_ALREADY_REGISTERED"

    me = client.get("/v1/me", headers=bot(CARMEN, False)).json()["data"]
    assert me["registrado"] and me["nombre"] == "Carmen"
    assert me["unidades"][0]["id"] == E["unidad_402"]
    assert me["consentimiento_vigente"]["decision"] == "aceptado"


def test_registro_sin_consentimiento_rechazado(client, catalogo):
    u = client.get(
        "/v1/unidades", params={"torre_id": catalogo["torre:1"], "referencia": "101"}, headers=bot(VECINO, False)
    ).json()["data"][0]
    r = client.post(
        "/v1/registros",
        json={"nombre": "Vecino", "unidad_id": u["id"], "consentimiento": {"version_politica": "2026-11", "decision": "retirado"}},
        headers=bot(VECINO),
    )
    assert r.status_code == 422 and _err(r) == "CONSENT_REQUIRED"


def test_solicitud_mixta_e_idempotencia(client, catalogo):
    cuerpo = {
        "tipo_servicio_ids": [catalogo["tipos_servicio:RECICLABLES"], catalogo["tipos_servicio:ORGANICOS"]],
        "observacion": "Cartón y restos de cocina",
    }
    # Sin Idempotency-Key → 400
    r = client.post("/v1/solicitudes", json=cuerpo, headers=bot(CARMEN, False))
    assert r.status_code == 400 and _err(r) == "IDEMPOTENCY_KEY_REQUIRED"

    h = bot(CARMEN)
    r = client.post("/v1/solicitudes", json=cuerpo, headers=h)
    assert r.status_code == 201, r.text
    s = r.json()["data"]
    assert s["codigo_pasaporte"].startswith("BR-") and s["canal_origen"] == "whatsapp"
    assert len(s["ordenes"]) == 2 and {o["estado"] for o in s["ordenes"]} == {"nueva"}
    assert s["avance"] == {"ordenes_totales": 2, "ordenes_finalizadas": 0, "estado_general": "pendiente", "alcance": "propio"}
    E["solicitud"] = s
    gremio = {catalogo["gremios:ASORESCATAR"]: "rec", catalogo["gremios:ECORAZON"]: "huerta"}
    for o in s["ordenes"]:
        E[f"orden_{gremio[o['gremio_id']]}"] = o["id"]

    # Reintento con la misma clave: misma respuesta, sin crear otra solicitud.
    r2 = client.post("/v1/solicitudes", json=cuerpo, headers=h)
    assert r2.status_code == 201 and r2.json() == r.json()
    assert r2.headers.get("Idempotent-Replayed") == "true"

    # Misma clave con otro cuerpo → conflicto.
    r3 = client.post("/v1/solicitudes", json={**cuerpo, "observacion": "otra"}, headers=h)
    assert r3.status_code == 409 and _err(r3) == "IDEMPOTENCY_CONFLICT"

    # Otra solicitud del mismo servicio con una abierta → regla de solicitud abierta.
    r4 = client.post("/v1/solicitudes", json={"tipo_servicio_ids": [catalogo["tipos_servicio:RECICLABLES"]]}, headers=bot(CARMEN))
    assert r4.status_code == 409 and _err(r4) == "OPEN_REQUEST_EXISTS"
    assert r4.json()["error"]["codigo_pasaporte"] == s["codigo_pasaporte"]

    # Campos desconocidos y decimales/servicios inválidos.
    r5 = client.post("/v1/solicitudes", json={**cuerpo, "rol": "admin"}, headers=bot(CARMEN))
    assert r5.status_code == 422

    lista = client.get("/v1/solicitudes", params={"abiertas": "true"}, headers=bot(CARMEN, False)).json()
    assert [x["id"] for x in lista["data"]] == [s["id"]]


def test_bandeja_por_gremio(client, operador):
    rec = client.get("/v1/ordenes", headers=operador("coord-reciclaje", False)).json()["data"]
    assert [o["id"] for o in rec] == [E["orden_rec"]]
    assert rec[0]["ubicacion_operativa"] == "Torre 3 · Apto 402" and rec[0]["contacto_nombre"] == "Carmen"
    # La huerta no ve la orden de reciclaje.
    r = client.get(f"/v1/ordenes/{E['orden_rec']}", headers=operador("coord-huerta", False))
    assert r.status_code == 404
    # La solicitud mixta vista por coordinación solo muestra su gremio.
    s = client.get(f"/v1/solicitudes/{E['solicitud']['id']}", headers=operador("coord-reciclaje", False)).json()["data"]
    assert s["avance"]["alcance"] == "gremio" and len(s["ordenes"]) == 1
    # Un residente no ve bandejas.
    assert client.get("/v1/ordenes", headers=bot(CARMEN, False)).status_code == 403


def _recolector(client, operador, gremio_id, usuario):
    rs = client.get("/v1/recolectores", params={"gremio_id": gremio_id}, headers=operador(usuario, False)).json()["data"]
    return rs[0]


def test_asignacion_y_aviso(client, operador, catalogo):
    rosa = _recolector(client, operador, catalogo["gremios:ASORESCATAR"], "coord-reciclaje")
    E["rosa"] = rosa["id"]
    url = f"/v1/ordenes/{E['orden_rec']}/asignacion"
    cuerpo = {
        "version_esperada": 99,
        "recolector_id": rosa["id"],
        "inicio": "2026-11-20T16:00:00-05:00",
        "fin": "2026-11-20T17:00:00-05:00",
        "forma_aviso": "llamada",
    }
    r = client.post(url, json=cuerpo, headers=operador("coord-reciclaje"))
    assert r.status_code == 409 and _err(r) == "VERSION_CONFLICT"

    r = client.post(url, json={**cuerpo, "fin": "2026-11-20T15:00:00-05:00", "version_esperada": 1}, headers=operador("coord-reciclaje"))
    assert r.status_code == 422

    huerteros = _recolector(client, operador, catalogo["gremios:ECORAZON"], "coord-huerta")
    r = client.post(url, json={**cuerpo, "version_esperada": 1, "recolector_id": huerteros["id"]}, headers=operador("coord-reciclaje"))
    assert r.status_code == 422  # recolector de otro gremio

    r = client.post(url, json={**cuerpo, "version_esperada": 1}, headers=operador("coord-reciclaje"))
    assert r.status_code == 200, r.text
    o = r.json()["data"]
    assert o["estado"] == "asignada" and o["version"] == 2 and o["asignacion"]["recolector_nombre"] == rosa["nombre"]

    # Reasignación conserva historia.
    otro = client.get("/v1/recolectores", params={"gremio_id": catalogo["gremios:ASORESCATAR"]},
                      headers=operador("coord-reciclaje", False)).json()["data"][1]
    E["otro"] = otro["id"]
    r = client.post(url, json={**cuerpo, "version_esperada": 2, "recolector_id": otro["id"]}, headers=operador("coord-reciclaje"))
    assert r.json()["data"]["reasignaciones"] == 1
    r = client.post(url, json={**cuerpo, "version_esperada": 3}, headers=operador("coord-reciclaje"))
    assert r.json()["data"]["version"] == 4 and r.json()["data"]["reasignaciones"] == 2


def test_bot_reserva_y_confirma_avisos(client):
    r = client.post("/v1/canal/avisos/reservas", json={"limite": 10}, headers=BOT)
    assert r.status_code == 200
    avisos = r.json()["data"]
    assert len(avisos) == 3 and all(a["tipo"] == "asignacion" for a in avisos)
    a = avisos[-1]
    assert a["destino"]["celular"] == "+" + CARMEN and a["destino"]["nombre"] == "Carmen"
    assert "pasa" in a["datos"]["texto_sugerido"] and a["datos"]["codigo_pasaporte"] == E["solicitud"]["codigo_pasaporte"]

    # Reservados: otra reserva no los repite.
    assert client.post("/v1/canal/avisos/reservas", json={}, headers=BOT).json()["data"] == []

    for av in avisos[:-1]:
        r = client.post(f"/v1/canal/avisos/{av['id']}/resultado", json={"estado": "enviado", "id_externo": "wamid.X"}, headers=BOT)
        assert r.json()["data"]["estado"] == "enviado"
    r = client.post(f"/v1/canal/avisos/{a['id']}/resultado", json={"estado": "fallido", "error": "timeout"}, headers=BOT)
    assert r.json()["data"]["estado"] == "pendiente"  # reintento programado
    # Un residente no puede usar las rutas del canal como si fuera el bot de otro... pero sí el token del bot.
    assert client.post("/v1/canal/avisos/reservas", json={}, headers={"Authorization": "Bearer x"}).status_code == 401


def test_resultado_recogida_otorga_puntos_una_vez(client, operador):
    url = f"/v1/ordenes/{E['orden_rec']}/resultado"
    cuerpo = {"version_esperada": 4, "resultado": "recogida", "ocurrido_at": "2026-11-17T16:30:00-05:00"}
    r = client.post(url, json={**cuerpo, "motivo_rechazo_id": E["rosa"]}, headers=operador("coord-reciclaje"))
    assert r.status_code == 422  # una recogida no lleva motivo
    h = operador("coord-reciclaje")
    r = client.post(url, json=cuerpo, headers=h)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["estado"] == "recogida" and d["evaluacion_puntos"] == "acreditada" and d["puntos_otorgados"] == "10.00"
    assert client.post(url, json=cuerpo, headers=h).json() == r.json()  # reintento idempotente
    r = client.post(url, json={**cuerpo, "version_esperada": 5}, headers=operador("coord-reciclaje"))
    assert r.status_code == 409 and _err(r) == "INVALID_TRANSITION"

    pts = client.get("/v1/me/puntos", headers=bot(CARMEN, False)).json()["data"]
    assert pts["saldo"] == "10.00" and pts["movimientos"] == 1
    mov = client.get("/v1/me/movimientos-puntos", headers=bot(CARMEN, False)).json()["data"]
    assert mov[0]["codigo_pasaporte"] == E["solicitud"]["codigo_pasaporte"]


def test_rechazo_con_educacion(client, operador, catalogo):
    huertero = _recolector(client, operador, catalogo["gremios:ECORAZON"], "coord-huerta")
    E["huertero"] = huertero["id"]
    url = f"/v1/ordenes/{E['orden_huerta']}"
    r = client.post(url + "/resultado", json={"version_esperada": 1, "resultado": "rechazada", "ocurrido_at": "2026-11-17T10:00:00-05:00",
                                              "motivo_rechazo_id": catalogo["motivos_rechazo:MOJADO"]}, headers=operador("coord-huerta"))
    assert r.status_code == 409  # aún no asignada
    client.post(url + "/asignacion", json={"version_esperada": 1, "recolector_id": huertero["id"], "forma_aviso": "recado"},
                headers=operador("coord-huerta"))
    r = client.post(url + "/resultado", json={"version_esperada": 2, "resultado": "rechazada", "ocurrido_at": "2026-11-17T10:00:00-05:00"},
                    headers=operador("coord-huerta"))
    assert r.status_code == 422  # rechazo sin motivo
    r = client.post(url + "/resultado", json={"version_esperada": 2, "resultado": "rechazada", "ocurrido_at": "2026-11-17T10:00:00-05:00",
                                              "motivo_rechazo_id": catalogo["motivos_rechazo:NO_APROVECHABLE"]}, headers=operador("coord-huerta"))
    assert r.status_code == 200 and r.json()["data"]["evaluacion_puntos"] == "no_aplica"

    s = client.get(f"/v1/solicitudes/{E['solicitud']['id']}", headers=bot(CARMEN, False)).json()["data"]
    assert s["avance"]["estado_general"] == "atendida" and s["avance"]["ordenes_finalizadas"] == 2

    avisos = client.post("/v1/canal/avisos/reservas", json={"limite": 50}, headers=BOT).json()["data"]
    tipos = {a["tipo"]: a for a in avisos}
    assert "recoleccion_confirmada" in tipos and "rechazo_educativo" in tipos
    edu = tipos["rechazo_educativo"]["datos"]
    assert edu["contenido"]["titulo"] == "Qué va a la huerta"
    assert client.get("/v1/me/puntos", headers=bot(CARMEN, False)).json()["data"]["saldo"] == "10.00"


def test_pesaje_de_lote_borrador_y_confirmacion(client, operador, catalogo):
    base = {
        "gremio_id": catalogo["gremios:ASORESCATAR"],
        "fecha_medicion": "2026-11-17T17:00:00-05:00",
        "origen_captura": "manual",
        "orden_ids": [E["orden_rec"]],
        "torre_origen_id": catalogo["torre:3"],
        "numero_tiquete": "38298",
        "lineas": [
            {"material_id": catalogo["materiales:CARTON"], "metodo_medicion": "bascula", "kg_aceptados": "9.000", "kg_rechazados": "1.5"},
            {"material_id": catalogo["materiales:PET"], "metodo_medicion": "bascula", "kg_aceptados": "3", "kg_rechazados": "0"},
        ],
    }
    h = operador("coord-reciclaje")
    r = client.post("/v1/pesajes", json={**base, "recolector_id": E["otro"]}, headers=h)
    assert r.status_code == 422  # la orden está asignada a Rosa (no a este recolector) y falta motivo del rechazo
    fields = r.json()["error"]["fields"]
    assert "orden_ids" in fields and "lineas.0.motivo_rechazo_id" in fields

    orden = client.get(f"/v1/ordenes/{E['orden_rec']}", headers=operador("coord-reciclaje", False)).json()["data"]
    rec_id = orden["asignacion"]["recolector_id"]
    base["recolector_id"] = rec_id
    base["lineas"][0]["motivo_rechazo_id"] = catalogo["motivos_rechazo:MOJADO"]
    r = client.post("/v1/pesajes", json={**base, "lineas": [{**base["lineas"][0], "kg_aceptados": 9.0}]}, headers=operador("coord-reciclaje"))
    assert r.status_code == 422  # decimales como número → rechazado

    r = client.post("/v1/pesajes", json=base, headers=operador("coord-reciclaje"))
    assert r.status_code == 201, r.text
    p = r.json()["data"]
    assert p["estado"] == "borrador" and p["codigo"].startswith("PS-")
    assert p["totales"] == {"kg_aceptados": "12.000", "kg_rechazados": "1.500", "valor_estimado": "7050.0000", "kg_sin_precio": "0.000"}
    E["pesaje_lote"] = p

    desde, hasta = "2026-11-01T00:00:00Z", "2026-12-01T00:00:00Z"
    res = client.get("/v1/reportes/resumen", params={"desde": desde, "hasta": hasta}, headers=operador("fundacion", False)).json()["data"]
    assert res["kg_aceptados"] == "0.000"  # borrador no cuenta

    r = client.post(f"/v1/pesajes/{p['id']}/confirmacion", json={"version_esperada": 1}, headers=operador("coord-reciclaje"))
    assert r.status_code == 200 and r.json()["data"]["estado"] == "confirmado"

    # Segundo pesaje con el mismo tiquete → advertencia de posible duplicado (no bloquea).
    r = client.post("/v1/pesajes", json={**base, "orden_ids": [], "torre_origen_id": None}, headers=operador("coord-reciclaje"))
    assert r.status_code == 201 and r.json()["data"]["advertencias"]

    res = client.get("/v1/reportes/resumen", params={"desde": desde, "hasta": hasta}, headers=operador("fundacion", False)).json()["data"]
    assert res["kg_aceptados"] == "12.000" and res["kg_rechazados"] == "1.500"
    assert res["valor_estimado"] == "7050.00" and res["tasa_rechazo_peso"] == pytest.approx(0.1111, abs=1e-4)
    assert res["hogares_participantes"] == 1 and res["tasa_rechazo_ordenes"] == 0.5


def test_entrega_directa_con_baldes(client, operador, catalogo):
    me = client.get("/v1/me", headers=bot(CARMEN, False)).json()["data"]
    cuerpo = {
        "punto_recepcion_id": catalogo["puntos_recepcion:HUERTA_ECORAZON"],
        "participante_id": me["participante_id"],
        "pesaje": {
            "gremio_id": catalogo["gremios:ECORAZON"],
            "fecha_medicion": "2026-11-17T09:00:00-05:00",
            "origen_captura": "baldes",
            "lineas": [
                {"material_id": catalogo["materiales:ORGANICOS"], "metodo_medicion": "conversion_balde",
                 "cantidad_aceptada": "1.5", "cantidad_rechazada": "0", "version_equivalencia_id": catalogo["equivalencia_balde"]}
            ],
        },
    }
    assert client.post("/v1/entregas-directas", json=cuerpo, headers=operador("coord-reciclaje")).status_code == 403
    r = client.post("/v1/entregas-directas", json=cuerpo, headers=operador("coord-huerta"))
    assert r.status_code == 201, r.text
    p = r.json()["data"]
    linea = p["lineas"][0]
    assert linea["estimacion"] and linea["kg_aceptados"] == "12.000" and linea["cantidad_aceptada"] == "1.500"
    assert p["unidad_medida_id"] == E["unidad_402"] and p["torre_origen_id"] == catalogo["torre:3"]
    r = client.post(f"/v1/pesajes/{p['id']}/confirmacion", json={"version_esperada": 1}, headers=operador("coord-huerta"))
    assert r.json()["data"]["evaluacion_puntos"] == "acreditada"
    assert client.get("/v1/me/puntos", headers=bot(CARMEN, False)).json()["data"]["saldo"] == "25.00"
    E["pesaje_entrega"] = r.json()["data"]


def test_liga_de_torres(client, catalogo):
    r = client.get("/v1/liga", params={"conjunto_id": catalogo["conjunto"], "desde": "2026-11-01T00:00:00Z",
                                       "hasta": "2026-12-01T00:00:00Z"}, headers=bot(CARMEN, False))
    assert r.status_code == 200, r.text
    liga = r.json()["data"]
    primera = liga["torres"][0]
    assert primera["torre_codigo"] == "3" and primera["posicion"] == 1
    assert primera["hogares_participantes"] == 1 and primera["porcentaje_participacion"] == "0.91"
    assert primera["kg_aceptados_atribuidos"] == "24.000"
    assert "nombre" not in json.dumps(primera).replace("torre_nombre", "")


def test_correccion_excluye_el_anulado(client, operador, catalogo):
    p = E["pesaje_lote"]
    reemplazo = {
        "gremio_id": catalogo["gremios:ASORESCATAR"],
        "fecha_medicion": "2026-11-17T17:00:00-05:00",
        "origen_captura": "manual",
        "recolector_id": p["recolector_id"],
        "orden_ids": [E["orden_rec"]],
        "torre_origen_id": catalogo["torre:3"],
        "lineas": [{"material_id": catalogo["materiales:CARTON"], "metodo_medicion": "bascula", "kg_aceptados": "8.000", "kg_rechazados": "0"}],
    }
    r = client.post(f"/v1/pesajes/{p['id']}/correcciones", json={"version_esperada": 2, "motivo": "Error de digitación", "pesaje_reemplazo": reemplazo},
                    headers=operador("coord-reciclaje"))
    assert r.status_code == 201, r.text
    assert r.json()["data"]["sustituye_pesaje_id"] == p["id"]
    anterior = client.get(f"/v1/pesajes/{p['id']}", headers=operador("coord-reciclaje", False)).json()["data"]
    assert anterior["estado"] == "anulado"
    res = client.get("/v1/reportes/resumen", params={"desde": "2026-11-01T00:00:00Z", "hasta": "2026-12-01T00:00:00Z",
                                                     "gremio_id": catalogo["gremios:ASORESCATAR"]}, headers=operador("coord-reciclaje", False)).json()["data"]
    assert res["kg_aceptados"] == "8.000"


def test_reportes_permisos(client, operador, catalogo):
    q = {"desde": "2026-11-01T00:00:00Z", "hasta": "2026-12-01T00:00:00Z"}
    assert client.get("/v1/reportes/resumen", params=q, headers=bot(CARMEN, False)).status_code == 403
    r = client.get("/v1/reportes/resumen", params={**q, "gremio_id": catalogo["gremios:ASORESCATAR"]}, headers=operador("coord-huerta", False))
    assert r.status_code == 403
    serie = client.get("/v1/reportes/serie", params=q, headers=operador("fundacion", False)).json()["data"]
    assert serie["serie"][0]["inicio_local"] == "2026-11-01"
    r = client.get("/v1/reportes/resumen", params={"desde": q["hasta"], "hasta": q["desde"]}, headers=operador("fundacion", False))
    assert r.status_code == 400


def test_sync_offline_sin_duplicar(client, operador, catalogo):
    lote = {
        "dispositivo_id": "tablet-huerta",
        "operaciones": [
            {
                "operacion_id": "op-1",
                "accion": "crear_pesaje",
                "referencia_local": "local-pesaje-1",
                "creada_local_at": "2026-11-17T16:00:00-05:00",
                "datos": {
                    "gremio_id": catalogo["gremios:ECORAZON"],
                    "recolector_id": E["huertero"],
                    "fecha_medicion": "2026-11-17T16:00:00-05:00",
                    "origen_captura": "baldes",
                    "orden_ids": [],
                    "lineas": [{"material_id": catalogo["materiales:ORGANICOS"], "metodo_medicion": "conversion_balde",
                                "cantidad_aceptada": "2", "cantidad_rechazada": "0", "version_equivalencia_id": catalogo["equivalencia_balde"]}],
                },
            },
            {"operacion_id": "op-2", "accion": "confirmar_pesaje", "recurso_id": "local-pesaje-1", "depende_de": ["op-1"],
             "creada_local_at": "2026-11-17T16:01:00-05:00", "datos": {"version_esperada": 1}},
            {"operacion_id": "op-3", "accion": "confirmar_pesaje", "recurso_id": "no-existe", "depende_de": [],
             "creada_local_at": "2026-11-17T16:02:00-05:00", "datos": {"version_esperada": 1}},
            {"operacion_id": "op-4", "accion": "confirmar_pesaje", "recurso_id": "local-pesaje-1", "depende_de": ["op-3"],
             "creada_local_at": "2026-11-17T16:03:00-05:00", "datos": {"version_esperada": 2}},
        ],
    }
    h = operador("coord-huerta", False)
    r = client.post("/v1/sync", json=lote, headers=h)
    assert r.status_code == 200, r.text
    res = {x["operacion_id"]: x for x in r.json()["data"]["resultados"]}
    assert res["op-1"]["estado"] == "aplicada" and res["op-2"]["estado"] == "aplicada"
    assert res["op-3"]["estado"] == "conflicto" and res["op-4"]["estado"] == "bloqueada"
    pesaje_id = r.json()["data"]["referencias"]["local-pesaje-1"]

    q = {"desde": "2026-11-01T00:00:00Z", "hasta": "2026-12-01T00:00:00Z", "gremio_id": catalogo["gremios:ECORAZON"]}
    antes = client.get("/v1/reportes/resumen", params=q, headers=operador("coord-huerta", False)).json()["data"]["kg_aceptados"]
    r = client.post("/v1/sync", json=lote, headers=h)  # la tablet reintenta el mismo lote
    res = {x["operacion_id"]: x for x in r.json()["data"]["resultados"]}
    assert res["op-1"]["estado"] == "repetida" and res["op-1"]["data"]["id"] == pesaje_id
    assert res["op-2"]["estado"] == "repetida"
    despues = client.get("/v1/reportes/resumen", params=q, headers=operador("coord-huerta", False)).json()["data"]["kg_aceptados"]
    assert antes == despues == "28.000"

    ciclo = {"dispositivo_id": "t", "operaciones": [
        {**lote["operaciones"][1], "operacion_id": "a", "depende_de": ["b"]},
        {**lote["operaciones"][1], "operacion_id": "b", "depende_de": ["a"]},
    ]}
    assert client.post("/v1/sync", json=ciclo, headers=h).status_code == 400


def test_despachador_webhook_firma(client, monkeypatch):
    from app import despachador
    from app.config import get_settings

    # Un aviso pendiente nuevo: asignar la orden de una nueva solicitud.
    recibidos = []

    def manejar(request: httpx.Request) -> httpx.Response:
        firma = hmac.new(b"secreto-webhook-pruebas", request.content, hashlib.sha256).hexdigest()
        assert request.headers["X-Brota-Firma"] == f"sha256={firma}"
        recibidos.append(json.loads(request.content))
        return httpx.Response(200, json={"id_externo": "wamid.TEST"})

    monkeypatch.setattr(get_settings(), "bot_webhook_url", "https://bot.invalid/avisos")
    # Liberar el aviso que quedó pendiente con reintento programado.
    from sqlalchemy import update

    from app.db import get_sessionmaker
    from app.models import EventoSalida

    with get_sessionmaker()() as db:
        db.execute(update(EventoSalida).where(EventoSalida.estado.in_(("pendiente", "en_envio")))
                   .values(estado="pendiente", proximo_intento_at=EventoSalida.created_at))
        db.commit()
    with httpx.Client(transport=httpx.MockTransport(manejar)) as c:
        n = despachador.despachar_lote(c, limite=50)
    assert n >= 1 and len(recibidos) == n
    assert recibidos[0]["destino"]["celular"].startswith("+57")
    estados = client.get("/v1/canal/avisos", params={"estado": "enviado"}, headers=BOT).json()["data"]
    assert len(estados) >= n


def test_operadores_y_cuentas(client, operador, catalogo):
    r = client.post("/v1/auth/sesiones", json={"usuario": "admin", "pin": "0000"})
    assert r.status_code == 401
    assert client.get("/v1/cuentas-operadoras", headers=operador("coord-huerta", False)).status_code == 403
    r = client.post("/v1/cuentas-operadoras", json={"nombre": "Respaldo huerta", "usuario": "respaldo-huerta", "pin": "13579",
                                                     "permisos": [{"rol": "coordinacion", "gremio_id": catalogo["gremios:ECORAZON"]}]},
                    headers=operador("admin"))
    assert r.status_code == 201, r.text
    assert "pin" not in r.json()["data"]
    assert client.post("/v1/auth/sesiones", json={"usuario": "respaldo-huerta", "pin": "13579"}).status_code == 201


def test_configuracion_versionada(client, operador, catalogo):
    r = client.post("/v1/precios-material", json={"material_id": catalogo["materiales:CARTON"], "precio_kg": "500"}, headers=operador("admin"))
    assert r.status_code == 201, r.text
    precios = client.get("/v1/configuracion", params={"tipo": "precios"}, headers=operador("admin", False)).json()["data"]
    carton = [p for p in precios if p["material_id"] == catalogo["materiales:CARTON"]]
    assert len(carton) == 2 and sum(1 for p in carton if p["vigente_hasta"] is None) == 1
    assert client.post("/v1/precios-material", json={"material_id": catalogo["materiales:CARTON"], "precio_kg": "500"},
                       headers=operador("coord-reciclaje")).status_code == 403


def test_concurrencia_doble_toque(client, catalogo):
    """Dos envíos simultáneos: con la misma clave se crea una sola solicitud; con claves distintas,
    la regla de solicitud abierta deja pasar solo una."""
    from concurrent.futures import ThreadPoolExecutor

    cel = "573009998877"
    u = client.get("/v1/unidades", params={"torre_id": catalogo["torre:2"], "referencia": "301"}, headers=bot(cel, False)).json()["data"][0]
    client.post("/v1/registros", json={"nombre": "Ana", "unidad_id": u["id"],
                                       "consentimiento": {"version_politica": "2026-11", "decision": "aceptado"}}, headers=bot(cel))
    habilitar_piloto(client, cel)
    cuerpo = {"tipo_servicio_ids": [catalogo["tipos_servicio:ORGANICOS"]]}
    h = bot(cel)
    with ThreadPoolExecutor(4) as ex:
        rs = list(ex.map(lambda _: client.post("/v1/solicitudes", json=cuerpo, headers=h), range(4)))
    assert {r.status_code for r in rs} == {201}
    assert len({r.json()["data"]["id"] for r in rs}) == 1

    cuerpo = {"tipo_servicio_ids": [catalogo["tipos_servicio:RECICLABLES"]]}
    with ThreadPoolExecutor(4) as ex:
        rs = list(ex.map(lambda _: client.post("/v1/solicitudes", json=cuerpo, headers=bot(cel)), range(4)))
    codigos = sorted(r.status_code for r in rs)
    assert codigos == [201, 409, 409, 409], [r.text for r in rs]
