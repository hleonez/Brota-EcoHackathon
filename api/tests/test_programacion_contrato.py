from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import uuid
import pytest
from pydantic import ValidationError
from app.core.seguridad import Actor
from app.core.errores import AppError
from app.modulos.coordinacion import ProgramacionIn, programar
from app.modulos import coordinacion
from app.modulos.solicitudes import SolicitudIn, ABIERTAS
from app.modulos.reportes import ESTADOS


def test_programacion_requiere_franja_completa_y_ordenada():
    inicio = datetime.now(timezone.utc)
    for fin in (inicio, inicio - timedelta(hours=1)):
        with pytest.raises(ValidationError):
            ProgramacionIn(acuerdo_canal="llamada", version_esperada=1, inicio=inicio, fin=fin)
    with pytest.raises(ValidationError):
        ProgramacionIn(acuerdo_canal="llamada", version_esperada=1, inicio=inicio)


def test_programacion_no_admite_orden_sin_responsable(monkeypatch):
    gremio = uuid.uuid4()
    actor = Actor(tipo="operador", canal="tablet", permisos=[("coordinacion", gremio)])
    monkeypatch.setattr(coordinacion, "orden_de_coordinacion", lambda *a, **kw:
        SimpleNamespace(gremio_id=gremio, version=1, asignaciones=[], estado="nueva"))
    inicio = datetime.now(timezone.utc)
    with pytest.raises(AppError):
        programar(None, actor, uuid.uuid4(), ProgramacionIn(acuerdo_canal="llamada", version_esperada=1, inicio=inicio, fin=inicio+timedelta(hours=1)))


def test_preferencia_y_estados_en_contrato():
    datos = SolicitudIn(tipo_servicio_ids=[uuid.uuid4()], preferencia_sin_restriccion=True)
    assert datos.preferencia_sin_restriccion is True
    assert "programada" in ABIERTAS and "programada" in ESTADOS and "cancelada" in ESTADOS
    with pytest.raises(ValidationError):
        SolicitudIn(tipo_servicio_ids=[uuid.uuid4()])
    inicio = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        SolicitudIn(tipo_servicio_ids=[uuid.uuid4()], preferencia_sin_restriccion=True, preferencia_inicio=inicio, preferencia_fin=inicio)


def test_openapi_publica_nuevas_operaciones():
    from app.main import crear_app
    schema = crear_app(False).openapi()
    assert "/v1/ordenes/{orden_id}/programacion" in schema["paths"]
    assert "/v1/contenidos-educativos/{contenido_id}/publicacion" in schema["paths"]
    assert "materiales_confirmados" in schema["components"]["schemas"]["ResultadoIn"]["properties"]
