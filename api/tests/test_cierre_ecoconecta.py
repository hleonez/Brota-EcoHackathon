"""Reglas finales del contrato y recorrido oficial sobre PostgreSQL separado."""
import uuid
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from app.core.errores import AppError
from app.modulos import coordinacion, ia
from app.modulos.solicitudes import SolicitudIn, _estado_general
from tests.conftest import bot


def test_solicitud_exige_preferencia():
    with pytest.raises(ValidationError):
        SolicitudIn(tipo_servicio_ids=[uuid.uuid4()])


def test_cierre_exige_materiales_y_programacion(monkeypatch):
    with pytest.raises(ValidationError):
        coordinacion.ResultadoIn(version_esperada=1, resultado="recogida", ocurrido_at="2026-11-20T12:00:00Z")
    monkeypatch.setattr(coordinacion, "orden_de_coordinacion", lambda *a, **kw: SimpleNamespace(version=1, estado="asignada"))
    with pytest.raises(AppError):
        coordinacion.registrar_resultado(None, None, uuid.uuid4(), coordinacion.ResultadoIn(
            version_esperada=1, resultado="recogida", materiales_confirmados=[uuid.uuid4()], ocurrido_at="2026-11-20T12:00:00Z"))


@pytest.mark.parametrize("estados,esperado", [
    (["cancelada"], "cancelada"), (["rechazada"], "rechazada"),
    (["recogida"], "atendida"), (["cancelada", "recogida"], "finalizada_con_novedades"),
    (["recogida", "programada"], "parcial"), (["programada"], "en_curso")])
def test_resumen_no_confunde_cancelacion_y_recoleccion(estados, esperado):
    assert _estado_general([SimpleNamespace(estado=e) for e in estados]) == esperado


def test_ia_no_llama_proveedor_no_autorizado(monkeypatch):
    monkeypatch.setattr(ia, "llamar_gemini", lambda *a: pytest.fail("No debe llamar a Gemini"))
    with pytest.raises(AppError):
        ia.interpretar(None, ia.InterpretarIn(texto="tengo cartón"))


@pytest.mark.parametrize("flujo,cuenta,material,tipo", [
    ("ORGANICOS", "coord-huerta", "ORGANICOS", "huertero"),
    ("RECICLABLES", "coord-reciclaje", "CARTON", "reciclador")])
def test_recorrido_oficial(client, operador, catalogo, flujo, cuenta, material, tipo):
    celular = "573199990001" if tipo == "huertero" else "573199990002"
    admin = lambda: operador("admin")
    unidad = client.post("/v1/unidades", headers=admin(), json={"tipo": "negocio", "referencia_local": "Piloto " + flujo, "direccion_referencia": "Dirección de prueba"}).json()["data"]
    registro = client.post("/v1/registros", headers=bot(celular), json={"nombre": "Contacto demo", "unidad_id": unidad["id"], "consentimiento": {"version_politica": "2026-11", "decision": "aceptado"}})
    assert registro.status_code == 201, registro.text
    pedido = {"unidad_id": unidad["id"], "tipo_servicio_ids": [catalogo["tipos_servicio:" + flujo]], "preferencia_horaria": "Hoy de 2 a 4"}
    assert client.post("/v1/solicitudes", headers=bot(celular), json=pedido).status_code == 403
    h = client.post("/v1/piloto/habilitaciones", headers=admin(), json={"participante_id": registro.json()["data"]["participante_id"], "unidad_id": unidad["id"]})
    assert h.status_code == 201, h.text
    respuesta = client.post("/v1/solicitudes", headers=bot(celular), json=pedido)
    assert respuesta.status_code == 201, respuesta.text
    orden = respuesta.json()["data"]["ordenes"][0]
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
    asignada = client.post(url + "/asignacion", headers=operador(cuenta), json={"version_esperada": 1, "recolector_id": tid, "forma_aviso": "llamada"})
    assert asignada.status_code == 200, asignada.text
    r = client.post(url + "/programacion", headers=operador(cuenta), json={"version_esperada": 2, "inicio": "2026-11-20T14:00:00-05:00", "fin": "2026-11-20T16:00:00-05:00", "acuerdo_canal": "llamada"})
    assert r.status_code == 200 and r.json()["data"]["estado"] == "programada", r.text
    cierre = client.post(url + "/resultado", headers=operador(usuario), json={"version_esperada": 3, "resultado": "recogida", "ocurrido_at": "2026-11-20T15:00:00-05:00", "materiales_confirmados": [catalogo["materiales:" + material]]})
    assert cierre.status_code == 200, cierre.text
    assert cierre.json()["data"]["resultado"]["trabajador_id"] == tid
    movimientos = client.get("/v1/me/movimientos-puntos", headers=bot(celular, False)).json()["data"]
    assert len(movimientos) == 1 and movimientos[0]["detalle_calculo"]["total"] == "10"
