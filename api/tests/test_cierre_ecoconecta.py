"""Reglas de contrato que no dependen del orden de la base compartida."""
import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.config import get_settings
from app.core.errores import AppError
from app.modulos import coordinacion, ia
from app.modulos.solicitudes import SolicitudIn, _estado_general


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
    llamadas: list[tuple] = []

    def falso(*args):
        llamadas.append(args)
        return {"intencion": "pedir", "residuos": []}

    monkeypatch.setattr(ia, "llamar_gemini", falso)
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    with pytest.raises(AppError) as exc:
        ia.interpretar(None, ia.InterpretarIn(texto="tengo cartón"))
    assert exc.value.status == 503 and exc.value.code == "IA_NO_DISPONIBLE"
    assert llamadas == []

    monkeypatch.setattr(get_settings(), "gemini_api_key", "clave-de-prueba")
    db = SimpleNamespace(execute=lambda *a, **k: SimpleNamespace(scalars=lambda: []))
    salida = ia.interpretar(db, ia.InterpretarIn(texto="tengo cartón"))
    assert len(llamadas) == 1
    assert salida.intencion == "pedir"
