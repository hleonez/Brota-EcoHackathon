"""Pruebas contra una base PostgreSQL real y separada (`brota_test` por defecto).

Requiere PostgreSQL arriba (README principal). La base de pruebas se vacía en cada sesión;
nunca apuntes TEST_DB_NAME a la base de desarrollo o producción.
"""

from __future__ import annotations

import os
import re
import time
import uuid

import pytest

TEST_DB = os.environ.get("TEST_DB_NAME", "brota_test")
_PROHIBIDAS = {"brota", "postgres", "template0", "template1"}
if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", TEST_DB):
    raise RuntimeError("TEST_DB_NAME debe ser un identificador simple")
if TEST_DB.lower() in _PROHIBIDAS:
    raise RuntimeError("TEST_DB_NAME no puede ser la base de desarrollo ni una base del sistema")

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

_host = get_settings().db_host.strip().lower()
if _host not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("BROTA_ALLOW_REMOTE_TEST") != "1":
    raise RuntimeError(
        "La base de pruebas solo se acepta en loopback. "
        "Define BROTA_ALLOW_REMOTE_TEST=1 para autorizar otro host."
    )
if get_settings().db_name.lower() in {"brota", "postgres", "template0", "template1"}:
    raise RuntimeError("La conexión de pruebas apunta a la base de desarrollo o del sistema")

BOT = {"Authorization": "Bearer token-de-prueba-del-bot"}


def _conectar_admin(url: str):
    """Reintenta: el puerto local puede tardar unos segundos en aceptar conexiones."""
    ultimo: Exception | None = None
    for _ in range(15):
        try:
            return psycopg.connect(url, autocommit=True, connect_timeout=3)
        except psycopg.OperationalError as exc:
            ultimo = exc
            time.sleep(1)
    assert ultimo is not None
    raise ultimo


def _preparar_base() -> None:
    s = get_settings()
    admin = s.database_url().set(database="postgres").render_as_string(hide_password=False)
    admin = admin.replace("postgresql+psycopg", "postgresql")
    with _conectar_admin(admin) as conn:
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


def vaciar_avisos(client) -> None:
    """Confirma los avisos pendientes para que otra prueba no los confunda con los suyos."""
    while True:
        avisos = client.post("/v1/canal/avisos/reservas", json={"limite": 50}, headers=BOT).json()["data"]
        if not avisos:
            return
        for aviso in avisos:
            client.post(
                f"/v1/canal/avisos/{aviso['id']}/resultado",
                json={"estado": "enviado", "id_externo": "prueba"},
                headers=BOT,
            )


def habilitar_piloto(client, celular):
    """La preparación de cada recorrido autoriza explícitamente a su solicitante."""
    me = client.get("/v1/me", headers=bot(celular, False)).json()["data"]
    sesion = client.post("/v1/auth/sesiones", json={"usuario": "admin", "pin": "2468"}).json()["data"]
    for unidad in me["unidades"]:
        r = client.post("/v1/piloto/habilitaciones", json={"participante_id": me["participante_id"], "unidad_id": unidad["id"]},
            headers={"Authorization": "Bearer " + sesion["token"], **clave()})
        assert r.status_code == 201, r.text
