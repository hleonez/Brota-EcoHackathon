"""Pruebas contra una base PostgreSQL real y separada (`brota_test` por defecto).

Requiere PostgreSQL arriba (README principal). La base de pruebas se vacía en cada sesión;
nunca apuntes TEST_DB_NAME a la base de desarrollo o producción.
"""

from __future__ import annotations

import os
import uuid

import pytest

TEST_DB = os.environ.get("TEST_DB_NAME", "brota_test")
if TEST_DB in ("brota", "postgres"):
    raise RuntimeError("TEST_DB_NAME no puede ser la base de desarrollo")

os.environ.update(
    DB_NAME=TEST_DB,
    BOT_SERVICE_TOKEN="token-de-prueba-del-bot",
    JWT_SECRET="secreto-de-pruebas-" + "x" * 32,
    AVISOS_MODO="pull",
    BOT_WEBHOOK_URL="",
    BOT_WEBHOOK_SECRET="secreto-webhook-pruebas",
    SEED_PIN="2468",
    GEMINI_API_KEY="",  # las pruebas nunca llaman a Gemini de verdad
)

import psycopg  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import API_DIR, get_settings  # noqa: E402

BOT = {"Authorization": "Bearer token-de-prueba-del-bot"}


def _preparar_base() -> None:
    s = get_settings()
    admin = s.database_url().set(database="postgres").render_as_string(hide_password=False)
    admin = admin.replace("postgresql+psycopg", "postgresql")
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{TEST_DB}"')
    cfg = Config(str(API_DIR / "alembic.ini"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def client() -> TestClient:
    _preparar_base()
    from app.db import get_sessionmaker
    from app.main import crear_app
    from app.seed import sembrar

    with get_sessionmaker()() as db:
        sembrar(db)
    with TestClient(crear_app(iniciar_despachador=False)) as c:
        yield c


def clave() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


def bot(celular: str, con_clave: bool = True) -> dict[str, str]:
    h = {**BOT, "X-Canal-Celular": celular}
    return {**h, **clave()} if con_clave else h


@pytest.fixture(scope="session")
def operador(client: TestClient):
    cache: dict[str, dict[str, str]] = {}

    def _h(usuario: str, con_clave: bool = True) -> dict[str, str]:
        if usuario not in cache:
            r = client.post("/v1/auth/sesiones", json={"usuario": usuario, "pin": "2468"})
            assert r.status_code == 201, r.text
            cache[usuario] = {"Authorization": f"Bearer {r.json()['data']['token']}"}
        return {**cache[usuario], **(clave() if con_clave else {})}

    return _h


@pytest.fixture(scope="session")
def catalogo(client: TestClient) -> dict:
    data = client.get("/v1/catalogos", headers=BOT).json()["data"]
    por_codigo = {}
    for grupo in ("gremios", "tipos_servicio", "materiales", "motivos_rechazo", "puntos_recepcion"):
        for x in data[grupo]:
            por_codigo[f"{grupo}:{x['codigo']}"] = x["id"]
    por_codigo["equivalencia_balde"] = data["equivalencias"][0]["id"]
    conj = client.get("/v1/conjuntos", headers=BOT).json()["data"][0]["id"]
    por_codigo["conjunto"] = conj
    for t in client.get(f"/v1/conjuntos/{conj}/torres", headers=BOT).json()["data"]:
        por_codigo[f"torre:{t['codigo']}"] = t["id"]
    return por_codigo


def habilitar_piloto(client, celular):
    """La preparación de cada recorrido autoriza explícitamente a su solicitante."""
    me = client.get("/v1/me", headers=bot(celular, False)).json()["data"]
    sesion = client.post("/v1/auth/sesiones", json={"usuario": "admin", "pin": "2468"}).json()["data"]
    for unidad in me["unidades"]:
        r = client.post("/v1/piloto/habilitaciones", json={"participante_id": me["participante_id"], "unidad_id": unidad["id"]},
            headers={"Authorization": "Bearer " + sesion["token"], **clave()})
        assert r.status_code == 201, r.text
