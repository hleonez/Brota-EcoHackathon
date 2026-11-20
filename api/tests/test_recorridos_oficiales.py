"""Recorridos oficiales y casos negativos sobre la base compartida.

Corre después de test_recorrido.py: esa bandeja espera solo la orden de Carmen.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import bot, vaciar_avisos


def _ocurrido() -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()


def _negocio(client, operador, celular, referencia):
    unidad = client.post(
        "/v1/unidades", headers=operador("admin"),
        json={"tipo": "negocio", "referencia_local": referencia, "direccion_referencia": "Corredor de prueba"},
    )
    assert unidad.status_code == 201, unidad.text
    unidad = unidad.json()["data"]
    registro = client.post(
        "/v1/registros", headers=bot(celular),
        json={"nombre": referencia, "unidad_id": unidad["id"], "consentimiento": {"version_politica": "2026-11", "decision": "aceptado"}},
    )
    assert registro.status_code == 201, registro.text
    return unidad, registro.json()["data"]["participante_id"]


def _pedir(client, celular, unidad_id, servicio):
    return client.post("/v1/solicitudes", headers=bot(celular), json={
        "unidad_id": unidad_id, "tipo_servicio_ids": [servicio], "preferencia_sin_restriccion": True,
    })


@pytest.mark.parametrize("flujo,cuenta,material,tipo", [
    ("ORGANICOS", "coord-huerta", "ORGANICOS", "huertero"),
    ("RECICLABLES", "coord-reciclaje", "CARTON", "reciclador")])
def test_recorrido_oficial(client, operador, catalogo, flujo, cuenta, material, tipo):
    celular = "573199990001" if tipo == "huertero" else "573199990002"
    admin = lambda: operador("admin")
    unidad = client.post("/v1/unidades", headers=admin(), json={"tipo": "negocio", "referencia_local": "Piloto " + flujo, "direccion_referencia": "Dirección de prueba"}).json()["data"]
    registro = client.post("/v1/registros", headers=bot(celular), json={"nombre": "Contacto demo", "unidad_id": unidad["id"], "consentimiento": {"version_politica": "2026-11", "decision": "aceptado"}})
    assert registro.status_code == 201, registro.text
    pedido = {
        "unidad_id": unidad["id"],
        "tipo_servicio_ids": [catalogo["tipos_servicio:" + flujo]],
        "preferencia_inicio": "2026-11-21T14:00:00-05:00",
        "preferencia_fin": "2026-11-21T16:00:00-05:00",
    }
    assert client.post("/v1/solicitudes", headers=bot(celular), json=pedido).status_code == 403
    h = client.post("/v1/piloto/habilitaciones", headers=admin(), json={"participante_id": registro.json()["data"]["participante_id"], "unidad_id": unidad["id"]})
    assert h.status_code == 201, h.text
    respuesta = client.post("/v1/solicitudes", headers=bot(celular), json=pedido)
    assert respuesta.status_code == 201, respuesta.text
    solicitud = respuesta.json()["data"]
    assert solicitud["tipo_generador"] == "negocio" and solicitud["preferencia_sin_restriccion"] is False
    assert "entre" in solicitud["preferencia_horaria"]
    me = client.get("/v1/me", headers=bot(celular, False)).json()["data"]
    assert any(h["unidad_id"] == unidad["id"] for h in me["habilitaciones"])
    orden = solicitud["ordenes"][0]
    gremio = orden["gremio_id"]
    trabajador_datos = {"nombre": "Trabajador piloto", "gremio_id": gremio}
    if tipo == "huertero":
        huerta = client.post("/v1/huertas", headers=admin(), json={"nombre": "Huerta piloto", "ubicacion": "Zona demo", "gremio_id": gremio})
        assert huerta.status_code == 201, huerta.text
        trabajador_datos["huerta_id"] = huerta.json()["data"]["id"]
    trabajador = client.post("/v1/" + ("huerteros" if tipo == "huertero" else "recicladores"), headers=admin(), json=trabajador_datos)
    assert trabajador.status_code == 201, trabajador.text
    tid = trabajador.json()["data"]["id"]
    usuario = "piloto-" + tipo
    cuenta_r = client.post("/v1/cuentas-operadoras", headers=admin(), json={"usuario": usuario, "nombre": "Cuenta piloto", "pin": "2468", "trabajador_id": tid, "permisos": [{"rol": tipo, "gremio_id": gremio}]})
    assert cuenta_r.status_code == 201, cuenta_r.text
    url = "/v1/ordenes/" + orden["id"]
    otro_gremio = "coord-reciclaje" if tipo == "huertero" else "coord-huerta"
    assert client.get(url, headers=operador(otro_gremio, False)).status_code == 404
    asignada = client.post(url + "/asignacion", headers=operador(cuenta), json={"version_esperada": 1, "recolector_id": tid, "forma_aviso": "llamada"})
    assert asignada.status_code == 200 and asignada.json()["data"]["estado"] == "asignada", asignada.text
    assert asignada.json()["data"]["asignacion"]["inicio"] is None and asignada.json()["data"]["reasignaciones"] == 0
    r = client.post(url + "/programacion", headers=operador(cuenta), json={"version_esperada": 2, "inicio": "2026-11-21T14:00:00-05:00", "fin": "2026-11-21T16:00:00-05:00", "acuerdo_canal": "llamada", "acuerdo_observacion": "Acordado por teléfono"})
    assert r.status_code == 200 and r.json()["data"]["estado"] == "programada", r.text
    assert r.json()["data"]["reasignaciones"] == 0
    avisos = client.get(url + "/avisos", headers=operador(cuenta, False)).json()["data"]
    assert any(a["estado"] == "pendiente" and a["enviado_at"] is None for a in avisos)
    material_id = catalogo["materiales:" + material]
    ocurrido = _ocurrido()
    cierre = client.post(url + "/resultado", headers=operador(usuario), json={"version_esperada": 3, "resultado": "recogida", "ocurrido_at": ocurrido, "materiales_confirmados": [material_id]})
    assert cierre.status_code == 200, cierre.text
    assert cierre.json()["data"]["resultado"]["trabajador_id"] == tid
    assert cierre.json()["data"]["resultado"]["materiales_confirmados"] == [material_id]
    assert cierre.json()["data"]["resultado"]["registrado_por"]
    repetido = client.post(url + "/resultado", headers=operador(usuario), json={"version_esperada": 4, "resultado": "recogida", "ocurrido_at": ocurrido, "materiales_confirmados": [material_id]})
    assert repetido.status_code == 409
    movimientos = client.get("/v1/me/movimientos-puntos", headers=bot(celular, False)).json()["data"]
    assert len(movimientos) == 1 and movimientos[0]["detalle_calculo"]["total"] == "10"
    vaciar_avisos(client)


def test_piloto_vencido_revocado_y_no_se_hereda(client, operador, catalogo):
    servicio = catalogo["tipos_servicio:RECICLABLES"]
    unidad, participante = _negocio(client, operador, "573188800001", "Piloto vencido")
    vencida = client.post("/v1/piloto/habilitaciones", headers=operador("admin"), json={
        "participante_id": participante, "unidad_id": unidad["id"],
        "vigente_desde": "2026-11-01T00:00:00-05:00", "vigente_hasta": "2026-11-02T00:00:00-05:00",
    })
    assert vencida.status_code == 201, vencida.text
    assert _pedir(client, "573188800001", unidad["id"], servicio).status_code == 403
    otro = client.post("/v1/registros", headers=bot("573188800002"), json={
        "nombre": "Vecino de la misma unidad", "unidad_id": unidad["id"],
        "consentimiento": {"version_politica": "2026-11", "decision": "aceptado"},
    })
    assert otro.status_code == 201, otro.text
    assert _pedir(client, "573188800002", unidad["id"], servicio).status_code == 403

    unidad2, participante2 = _negocio(client, operador, "573188800003", "Piloto revocado")
    alta = client.post("/v1/piloto/habilitaciones", headers=operador("admin"), json={
        "participante_id": participante2, "unidad_id": unidad2["id"],
    })
    assert alta.status_code == 201, alta.text
    revocada = client.patch(f"/v1/piloto/habilitaciones/{alta.json()['data']['id']}", headers=operador("admin"), json={
        "version_esperada": 1, "activo": False,
    })
    assert revocada.status_code == 200 and revocada.json()["data"]["revocada_at"], revocada.text
    assert _pedir(client, "573188800003", unidad2["id"], servicio).status_code == 403


def test_privacidad_directorio_y_sync(client, operador):
    assert client.get("/v1/unidades", headers=operador("fundacion", False)).status_code == 403
    assert client.get("/v1/unidades", headers=operador("admin", False)).status_code == 403
    assert client.get("/v1/unidades", headers=operador("coord-reciclaje", False)).status_code == 200
    lote = {"dispositivo_id": "fundacion", "operaciones": [{
        "operacion_id": "no", "accion": "asignar_orden", "recurso_id": str(uuid.uuid4()),
        "creada_local_at": "2026-11-20T10:00:00-05:00",
        "datos": {"version_esperada": 1, "recolector_id": str(uuid.uuid4()), "forma_aviso": "llamada"},
    }]}
    assert client.post("/v1/sync", headers=operador("fundacion"), json=lote).status_code == 403
    resumen = client.get("/v1/reportes/resumen", params={"desde": "2026-11-01T00:00:00Z", "hasta": "2026-12-01T00:00:00Z"},
                          headers=operador("fundacion", False)).json()["data"]
    assert "celular" not in resumen and "contacto_nombre" not in resumen


def test_reasignar_no_hereda_horario_ni_acceso(client, operador, catalogo):
    servicio = catalogo["tipos_servicio:RECICLABLES"]
    gremio = catalogo["gremios:ASORESCATAR"]
    unidad, participante = _negocio(client, operador, "573188800010", "Reasignacion")
    client.post("/v1/piloto/habilitaciones", headers=operador("admin"), json={"participante_id": participante, "unidad_id": unidad["id"]})
    solicitud = _pedir(client, "573188800010", unidad["id"], servicio)
    assert solicitud.status_code == 201, solicitud.text
    orden_id = solicitud.json()["data"]["ordenes"][0]["id"]
    url = f"/v1/ordenes/{orden_id}"
    trabajadores = []
    for nombre, usuario in (("Primero", "piloto-primero"), ("Segundo", "piloto-segundo")):
        alta = client.post("/v1/recicladores", headers=operador("admin"), json={"nombre": nombre, "gremio_id": gremio})
        assert alta.status_code == 201, alta.text
        tid = alta.json()["data"]["id"]
        cuenta = client.post("/v1/cuentas-operadoras", headers=operador("admin"), json={
            "usuario": usuario, "nombre": nombre, "pin": "2468", "trabajador_id": tid,
            "permisos": [{"rol": "reciclador", "gremio_id": gremio}],
        })
        assert cuenta.status_code == 201, cuenta.text
        trabajadores.append(tid)
    creada = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    sync_trabajador = client.post("/v1/sync", headers=operador("piloto-primero"), json={"dispositivo_id": "trabajador", "operaciones": [{
        "operacion_id": "prog-ajena", "accion": "programar_orden", "recurso_id": orden_id, "creada_local_at": creada,
        "datos": {"version_esperada": 1, "inicio": "2026-11-21T14:00:00-05:00", "fin": "2026-11-21T15:00:00-05:00", "acuerdo_canal": "llamada"},
    }]})
    assert sync_trabajador.status_code == 200, sync_trabajador.text
    assert sync_trabajador.json()["data"]["resultados"][0]["codigo_http"] == 403
    asignada = client.post(url + "/asignacion", headers=operador("coord-reciclaje"), json={
        "version_esperada": 1, "recolector_id": trabajadores[0], "forma_aviso": "llamada",
    })
    assert asignada.status_code == 200 and asignada.json()["data"]["estado"] == "asignada", asignada.text
    assert client.get(url, headers=operador("piloto-primero", False)).status_code == 200
    reasignada = client.post(url + "/asignacion", headers=operador("coord-reciclaje"), json={
        "version_esperada": 2, "recolector_id": trabajadores[1], "forma_aviso": "recado",
    })
    assert reasignada.status_code == 200, reasignada.text
    cuerpo = reasignada.json()["data"]
    assert cuerpo["estado"] == "asignada" and cuerpo["asignacion"]["inicio"] is None and cuerpo["reasignaciones"] == 1
    assert client.get(url, headers=operador("piloto-primero", False)).status_code == 404
    assert client.get(url, headers=operador("piloto-segundo", False)).status_code == 200
    programada = client.post(url + "/programacion", headers=operador("coord-reciclaje"), json={
        "version_esperada": 3, "inicio": "2026-11-21T14:00:00-05:00", "fin": "2026-11-21T15:00:00-05:00", "acuerdo_canal": "whatsapp",
    })
    assert programada.status_code == 200 and programada.json()["data"]["reasignaciones"] == 1, programada.text
    otra = client.post(url + "/programacion", headers=operador("coord-reciclaje"), json={
        "version_esperada": 4, "inicio": "2026-11-22T09:00:00-05:00", "fin": "2026-11-22T10:00:00-05:00", "acuerdo_canal": "presencial",
    })
    assert otra.status_code == 200 and otra.json()["data"]["reasignaciones"] == 1, otra.text
    tipos = [e["tipo"] for e in client.get(f"/v1/solicitudes/{solicitud.json()['data']['id']}/pasaporte", headers=bot("573188800010", False)).json()["data"]["eventos"]]
    assert tipos.count("orden_reasignada") == 1
    assert "orden_programada" in tipos and "orden_reprogramada" in tipos
    ajeno = catalogo["materiales:ORGANICOS"]
    rechazo = client.post(url + "/resultado", headers=operador("piloto-segundo"), json={
        "version_esperada": 5, "resultado": "recogida", "ocurrido_at": _ocurrido(), "materiales_confirmados": [ajeno],
    })
    assert rechazo.status_code == 422
    vaciar_avisos(client)


def test_inactivos_programacion_y_sync_rechazan_igual(client, operador, catalogo):
    gremio = catalogo["gremios:ECORAZON"]
    huerta = client.post("/v1/huertas", headers=operador("admin"), json={"nombre": "Huerta inactiva", "ubicacion": "Fondo", "gremio_id": gremio})
    assert huerta.status_code == 201, huerta.text
    hid = huerta.json()["data"]["id"]
    huertero = client.post("/v1/huerteros", headers=operador("admin"), json={"nombre": "Huertero inactivo", "gremio_id": gremio, "huerta_id": hid})
    assert huertero.status_code == 201, huertero.text
    tid = huertero.json()["data"]["id"]
    unidad, participante = _negocio(client, operador, "573188800020", "Inactivos")
    client.post("/v1/piloto/habilitaciones", headers=operador("admin"), json={"participante_id": participante, "unidad_id": unidad["id"]})
    solicitud = _pedir(client, "573188800020", unidad["id"], catalogo["tipos_servicio:ORGANICOS"])
    assert solicitud.status_code == 201, solicitud.text
    orden_id = solicitud.json()["data"]["ordenes"][0]["id"]
    url = f"/v1/ordenes/{orden_id}"
    apagada = client.patch(f"/v1/huertas/{hid}", headers=operador("admin"), json={"version_esperada": 1, "activo": False})
    assert apagada.status_code == 200, apagada.text
    sin_huerta = client.post(url + "/asignacion", headers=operador("coord-huerta"), json={
        "version_esperada": 1, "recolector_id": tid, "forma_aviso": "llamada",
    })
    assert sin_huerta.status_code == 422
    client.patch(f"/v1/huertas/{hid}", headers=operador("admin"), json={"version_esperada": 2, "activo": True})
    client.patch(f"/v1/huerteros/{tid}", headers=operador("coord-huerta"), json={"version_esperada": 1, "activo": False})
    inactivo = client.post(url + "/asignacion", headers=operador("coord-huerta"), json={
        "version_esperada": 1, "recolector_id": tid, "forma_aviso": "llamada",
    })
    assert inactivo.status_code == 422
    sin_canal = client.post(url + "/programacion", headers=operador("coord-huerta"), json={
        "version_esperada": 1, "inicio": "2026-11-21T14:00:00-05:00", "fin": "2026-11-21T15:00:00-05:00",
    })
    assert sin_canal.status_code == 422
    sin_responsable = client.post(url + "/programacion", headers=operador("coord-huerta"), json={
        "version_esperada": 1, "inicio": "2026-11-21T14:00:00-05:00", "fin": "2026-11-21T15:00:00-05:00", "acuerdo_canal": "llamada",
    })
    assert sin_responsable.status_code == 409
    creada = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    lote = {"dispositivo_id": "coord", "operaciones": [{
        "operacion_id": "prog-1", "accion": "programar_orden", "recurso_id": orden_id, "creada_local_at": creada,
        "datos": {"version_esperada": 1, "inicio": "2026-11-21T14:00:00-05:00", "fin": "2026-11-21T15:00:00-05:00", "acuerdo_canal": "llamada"},
    }]}
    sync = client.post("/v1/sync", headers=operador("coord-huerta"), json=lote)
    assert sync.status_code == 200, sync.text
    assert sync.json()["data"]["resultados"][0]["codigo_http"] == 409
    vaciar_avisos(client)


def test_cancelada_no_cuenta_como_recogida_y_hay_educacion(client, operador, catalogo):
    params = {"desde": "2026-11-01T00:00:00Z", "hasta": "2026-12-01T00:00:00Z"}
    antes = client.get("/v1/reportes/resumen", params=params, headers=operador("fundacion", False)).json()["data"]
    unidad, participante = _negocio(client, operador, "573188800030", "Cancelada")
    client.post("/v1/piloto/habilitaciones", headers=operador("admin"), json={"participante_id": participante, "unidad_id": unidad["id"]})
    solicitud = _pedir(client, "573188800030", unidad["id"], catalogo["tipos_servicio:RECICLABLES"])
    assert solicitud.status_code == 201, solicitud.text
    sid = solicitud.json()["data"]["id"]
    cancelada = client.post(f"/v1/solicitudes/{sid}/cancelacion", headers=bot("573188800030"), json={"motivo": "Ya no hace falta"})
    assert cancelada.status_code == 200, cancelada.text
    assert cancelada.json()["data"]["avance"]["estado_general"] == "cancelada"
    puntos = client.get("/v1/me/puntos", headers=bot("573188800030", False)).json()["data"]["saldo"]
    assert puntos == "0.00"
    despues = client.get("/v1/reportes/resumen", params=params, headers=operador("fundacion", False)).json()["data"]
    assert despues["ordenes_por_estado"]["cancelada"] == antes["ordenes_por_estado"]["cancelada"] + 1
    assert despues["resultados"]["recogidas"] == antes["resultados"]["recogidas"]
    temas = {}
    for tema in ("separacion", "huerta", "horarios_rutas"):
        lista = client.get("/v1/contenidos-educativos", params={"tema": tema}, headers=bot("573188800030", False)).json()["data"]
        assert lista and all(c["tema"] == tema for c in lista)
        temas[tema] = lista[0]
    editado = client.patch(f"/v1/contenidos-educativos/{temas['horarios_rutas']['id']}", headers=operador("admin"), json={
        "version_esperada": temas["horarios_rutas"]["version"], "texto": "Ejemplo del piloto, actualizado.",
    })
    assert editado.status_code == 200 and editado.json()["data"]["tema"] == "horarios_rutas", editado.text
    vaciar_avisos(client)
