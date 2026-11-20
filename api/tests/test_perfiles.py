import uuid
from types import SimpleNamespace
import pytest
from app.core.seguridad import Actor
from app.core.errores import AppError
from app.modulos import coordinacion, identidad


@pytest.mark.parametrize("tipo", ["reciclador", "huertero"])
def test_perfil_debe_coincidir_con_trabajador_y_gremio(monkeypatch, tipo):
    gremio, trabajador = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(identidad, "referencia_activa", lambda *args: SimpleNamespace(tipo=tipo, gremio_id=gremio))
    permiso = identidad.PermisoIn(rol=tipo, gremio_id=gremio)
    identidad._validar_trabajador(None, trabajador, [permiso])
    with pytest.raises(AppError):
        identidad._validar_trabajador(None, trabajador, [permiso, identidad.PermisoIn(rol="admin")])
    with pytest.raises(AppError):
        identidad._validar_trabajador(None, None, [permiso])
    with pytest.raises(AppError):
        identidad._validar_trabajador(None, trabajador, [identidad.PermisoIn(rol=tipo, gremio_id=uuid.uuid4())])


def test_trabajador_solo_consulta_asignacion_vigente(monkeypatch):
    trabajador, gremio, orden = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    asignacion = SimpleNamespace(recolector_id=trabajador, vigente_hasta=None)
    objeto = SimpleNamespace(gremio_id=gremio, asignaciones=[asignacion])
    monkeypatch.setattr(coordinacion, "_cargar_orden", lambda *args: objeto)
    actor = Actor(tipo="operador", canal="tablet", trabajador_id=trabajador)
    assert coordinacion.orden_de_coordinacion(None, actor, orden) is objeto
    with pytest.raises(AppError):
        coordinacion.asignar(None, actor, orden, None)
    asignacion.vigente_hasta = object()
    with pytest.raises(AppError):
        coordinacion.orden_de_coordinacion(None, actor, orden)


def test_contrato_publica_piloto_y_trabajadores():
    from app.main import crear_app
    schema = crear_app(False).openapi()
    assert "/v1/piloto/habilitaciones" in schema["paths"]
    assert "/v1/huerteros" in schema["paths"]
    assert "/v1/recicladores" in schema["paths"]
