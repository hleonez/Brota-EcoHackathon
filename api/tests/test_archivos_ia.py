"""Evidencia del tiquete y dictado: disco local, borrador y vencimiento. No llama a Gemini real."""

from __future__ import annotations

import base64
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.core.tipos import ahora
from app.db import get_sessionmaker
from app.modulos import ia
from app.modulos.archivos import depurar_vencidos
from app.models import Archivo, ProcesamientoIA, Pesaje, PesajeArchivo

RUTA_FOTO = "/v1/pesajes/desde-foto"
RUTA_DICTADO = "/v1/pesajes/desde-dictado"
FOTO = b"\xff\xd8\xff evidencia-de-tiquete-brota"


def _imagen() -> str:
    return base64.b64encode(FOTO).decode()


def _cuerpo_foto(catalogo, recolector_id: str | None = None) -> dict:
    cuerpo = {
        "gremio_id": catalogo["gremios:ASORESCATAR"],
        "imagen": {"mime_type": "image/jpeg", "datos_base64": _imagen()},
    }
    if recolector_id is not None:
        cuerpo["recolector_id"] = recolector_id
    return cuerpo


@pytest.fixture
def rosa(client, operador, catalogo):
    r = client.get(
        "/v1/recicladores",
        params={"gremio_id": catalogo["gremios:ASORESCATAR"]},
        headers=operador("coord-reciclaje", False),
    )
    assert r.status_code == 200, r.text
    return next(item for item in r.json()["data"] if item["nombre"].startswith("Rosa"))


@pytest.fixture
def gemini(monkeypatch):
    llamadas: list[dict] = []
    respuesta: dict = {}

    def falso(s, sistema, partes, esquema):
        llamadas.append({"sistema": sistema, "partes": partes, "esquema": esquema})
        return dict(respuesta)

    monkeypatch.setattr(get_settings(), "gemini_api_key", "clave-de-prueba")
    monkeypatch.setattr(ia, "proveedor_autorizado", lambda: True)
    monkeypatch.setattr(ia, "llamar_gemini", falso)
    return llamadas, respuesta


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "archivos_dir", str(tmp_path))
    return tmp_path


def _n_archivos() -> int:
    with get_sessionmaker()() as db:
        return db.execute(select(func.count()).select_from(Archivo)).scalar_one()


def _vinculo(pesaje_id: str) -> tuple[Archivo, ProcesamientoIA]:
    with get_sessionmaker()() as db:
        archivo = db.execute(
            select(Archivo)
            .join(PesajeArchivo, PesajeArchivo.archivo_id == Archivo.id)
            .where(PesajeArchivo.pesaje_id == pesaje_id)
        ).scalar_one()
        proceso = db.execute(
            select(ProcesamientoIA).where(ProcesamientoIA.pesaje_id == pesaje_id)
        ).scalar_one()
        db.expunge_all()
        return archivo, proceso


def _lectura_util(**extra) -> dict:
    base = {
        "numero_tiquete": "38298",
        "fecha": "2026-11-17",
        "proveedor": "Bodega Norte",
        "observaciones": "Pesaje de acopio",
        "lineas": [
            {"material": "CARTON", "kg": 9, "confianza": 0.95},
            {"material": "PET", "kg": 3, "confianza": 0.4},
        ],
    }
    base.update(extra)
    return base


def test_linea_dudosa_queda_en_borrador_y_la_foto_vence(client, operador, catalogo, rosa, gemini, carpeta):
    _llamadas, respuesta = gemini
    respuesta.update(_lectura_util())
    antes = _n_archivos()
    r = client.post(RUTA_FOTO, json=_cuerpo_foto(catalogo, rosa["id"]), headers=operador("coord-reciclaje"))
    assert r.status_code == 201, r.text
    p = r.json()["data"]
    assert p["estado"] == "borrador" and p["origen_captura"] == "foto_ia" and p["confirmado_at"] is None
    pet = next(d for d in p["dudosos"] if d["campo"] == "lineas.PET")
    assert pet["confianza"] == pytest.approx(0.4)
    assert "por debajo de 0.6" in pet["detalle"]
    assert _n_archivos() == antes + 1

    archivo, proceso = _vinculo(p["id"])
    assert archivo.proposito == "tiquete" and archivo.eliminado_at is None and archivo.expira_at is None
    assert archivo.mime == "image/jpeg" and archivo.tamano == len(FOTO)
    assert archivo.storage_key != "tiquete.jpg" and "/" not in archivo.storage_key
    destino = Path(carpeta) / archivo.storage_key
    assert destino.is_file() and destino.read_bytes() == FOTO
    assert proceso.estado == "propuesto" and proceso.tarea == "leer_tiquete"
    assert proceso.archivo_id == archivo.id and proceso.proveedor == "gemini"
    assert proceso.propuesta["lineas"][1]["codigo"] == "PET"
    assert _imagen() not in r.text

    propio = client.get(f"/v1/archivos/{archivo.id}", headers=operador("coord-reciclaje", False))
    assert propio.status_code == 200
    assert propio.content == FOTO
    assert propio.headers["content-type"].startswith("image/jpeg")

    ajeno = client.get(f"/v1/archivos/{archivo.id}", headers=operador("coord-huerta", False))
    assert ajeno.status_code in (403, 404)
    assert FOTO not in ajeno.content

    publico = client.get(f"/v1/archivos/{archivo.id}")
    assert publico.status_code == 401
    assert FOTO not in publico.content

    ok = client.post(
        f"/v1/pesajes/{p['id']}/confirmacion",
        json={"version_esperada": p["version"]},
        headers=operador("coord-reciclaje"),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["estado"] == "confirmado"
    with get_sessionmaker()() as db:
        guardado = db.get(Archivo, archivo.id)
        assert guardado is not None and guardado.expira_at is not None
        delta = guardado.expira_at - ahora()
        assert timedelta(days=6, hours=23) < delta < timedelta(days=7, minutes=5)
        proceso_db = db.execute(
            select(ProcesamientoIA).where(ProcesamientoIA.pesaje_id == p["id"])
        ).scalar_one()
        assert proceso_db.estado == "confirmado"
        guardado.expira_at = ahora() - timedelta(hours=1)
        db.commit()
        assert depurar_vencidos(db) == 1
        db.commit()
        db.refresh(guardado)
        assert guardado.eliminado_at is not None
        pesaje = db.get(Pesaje, p["id"])
        assert pesaje is not None and pesaje.estado == "confirmado"
    assert not destino.exists()
    despues = client.get(f"/v1/pesajes/{p['id']}", headers=operador("coord-reciclaje", False))
    assert despues.status_code == 200 and despues.json()["data"]["estado"] == "confirmado"
    borrado = client.get(f"/v1/archivos/{archivo.id}", headers=operador("coord-reciclaje", False))
    assert borrado.status_code == 404
    assert FOTO not in borrado.content


def test_foto_ilegible_no_crea_archivo(client, operador, catalogo, rosa, gemini, carpeta):
    _llamadas, respuesta = gemini
    respuesta.update(
        {
            "numero_tiquete": None,
            "fecha": None,
            "proveedor": None,
            "observaciones": None,
            "lineas": [{"material": "CARTON", "kg": None, "confianza": 0.2}],
        }
    )
    antes = _n_archivos()
    nombres = set(Path(carpeta).iterdir())
    r = client.post(RUTA_FOTO, json=_cuerpo_foto(catalogo, rosa["id"]), headers=operador("coord-reciclaje"))
    assert r.status_code == 422 and r.json()["error"]["code"] == "TIQUETE_ILEGIBLE"
    assert _n_archivos() == antes
    assert set(Path(carpeta).iterdir()) == nombres


def test_sin_clave_no_crea_archivo(client, operador, catalogo, carpeta, monkeypatch):
    def no_llames(*_a, **_k):
        raise AssertionError("Gemini no debe llamarse")

    monkeypatch.setattr(ia, "llamar_gemini", no_llames)
    monkeypatch.setattr(ia, "proveedor_autorizado", lambda: False)
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    antes = _n_archivos()
    nombres = set(Path(carpeta).iterdir())
    r = client.post(RUTA_FOTO, json=_cuerpo_foto(catalogo), headers=operador("coord-reciclaje"))
    assert r.status_code == 503 and r.json()["error"]["code"] == "IA_NO_DISPONIBLE"
    assert "a mano" in r.json()["error"]["message"]
    assert _n_archivos() == antes
    assert set(Path(carpeta).iterdir()) == nombres


def test_dictado_crea_borrador_sin_audio(client, operador, catalogo, rosa, gemini, carpeta):
    llamadas, respuesta = gemini
    respuesta.update(_lectura_util(numero_tiquete="D-1", observaciones=None))
    antes = _n_archivos()
    frase = "Rosa trajo 9 kg de cartón y 3 de PET"
    r = client.post(
        RUTA_DICTADO,
        json={
            "gremio_id": catalogo["gremios:ASORESCATAR"],
            "texto": frase,
            "recolector_id": rosa["id"],
        },
        headers=operador("coord-reciclaje"),
    )
    assert r.status_code == 201, r.text
    p = r.json()["data"]
    assert p["estado"] == "borrador" and p["origen_captura"] == "dictado" and p["confirmado_at"] is None
    assert any(d["campo"] == "lineas.PET" and d["confianza"] == pytest.approx(0.4) for d in p["dudosos"])
    assert _n_archivos() == antes
    assert list(Path(carpeta).iterdir()) == []
    with get_sessionmaker()() as db:
        audios = db.execute(select(func.count()).select_from(Archivo).where(Archivo.mime.like("audio/%"))).scalar_one()
        proceso = db.execute(select(ProcesamientoIA).where(ProcesamientoIA.pesaje_id == p["id"])).scalar_one()
        assert audios == 0
        assert proceso.archivo_id is None and proceso.tarea == "dictado" and proceso.estado == "propuesto"
    partes = llamadas[0]["partes"]
    assert all("inline_data" not in parte for parte in partes)
    assert frase in partes[-1]["text"]
    assert "audio" not in partes[-1]["text"]


def test_interpretar_no_guarda_foto_ni_audio(client, operador, gemini, carpeta):
    _llamadas, respuesta = gemini
    respuesta.update({"intencion": "pedir", "residuos": [{"codigo": "PET", "confianza": "alta"}]})
    antes = _n_archivos()
    foto = base64.b64encode(b"\xff\xd8\xff foto-del-vecino").decode()
    r = client.post(
        "/v1/ia/interpretar",
        json={"media": {"mime_type": "image/jpeg", "datos_base64": foto}},
        headers=operador("coord-reciclaje", False),
    )
    assert r.status_code == 200, r.text
    audio = base64.b64encode(b"audio-del-vecino").decode()
    r = client.post(
        "/v1/ia/interpretar",
        json={"media": {"mime_type": "audio/ogg", "datos_base64": audio}},
        headers=operador("coord-reciclaje", False),
    )
    assert r.status_code == 200, r.text
    assert _n_archivos() == antes
    assert not any(Path(carpeta).iterdir())
