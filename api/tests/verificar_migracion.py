"""Comprueba upgrade head en vacío y sobre una copia del esquema 0004.

No usa la base de la aplicación. Los nombres están fijos y se rechazan si coinciden
con la base de desarrollo.
"""
from __future__ import annotations

import os
import sys
import time

from alembic import command
from alembic.config import Config

PROHIBIDAS = {"brota", "postgres", "template0", "template1"}
VACIA = "brota_vacia_test"
HISTORICA = "brota_migrate_test"


def _exigir_nombre(nombre: str) -> None:
    if nombre.lower() in PROHIBIDAS or not nombre.endswith("_test"):
        raise SystemExit(f"Nombre de base de pruebas no permitido: {nombre}")


def _admin_url() -> str:
    from app.config import get_settings

    url = get_settings().database_url().set(database="postgres").render_as_string(hide_password=False)
    return url.replace("postgresql+psycopg", "postgresql")


def _conectar_admin():
    import psycopg

    ultimo = None
    for _ in range(15):
        try:
            return psycopg.connect(_admin_url(), autocommit=True, connect_timeout=3)
        except psycopg.OperationalError as exc:
            ultimo = exc
            time.sleep(1)
    raise ultimo


def _recrear(nombre: str) -> None:
    _exigir_nombre(nombre)
    with _conectar_admin() as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{nombre}"')


def _eliminar(nombre: str) -> None:
    _exigir_nombre(nombre)
    with _conectar_admin() as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)')


def _migrar(nombre: str, revision: str) -> None:
    from app.config import API_DIR, get_settings
    from app.db import get_engine

    os.environ["DB_NAME"] = nombre
    get_settings.cache_clear()
    get_engine.cache_clear()
    command.upgrade(Config(str(API_DIR / "alembic.ini")), revision)


def _engine(nombre: str):
    from app.config import get_settings
    from app.db import get_engine

    os.environ["DB_NAME"] = nombre
    get_settings.cache_clear()
    get_engine.cache_clear()
    return get_engine()


def _comparar(engine) -> None:
    from sqlalchemy import inspect

    from app.models import Base

    insp = inspect(engine)
    db_tables = set(insp.get_table_names())
    diferencias: list[str] = []
    for name, table in Base.metadata.tables.items():
        if name not in db_tables:
            diferencias.append(f"falta la tabla {name}")
            continue
        columnas_db = {c["name"] for c in insp.get_columns(name)}
        columnas = {c.name for c in table.columns}
        if columnas != columnas_db:
            diferencias.append(f"{name}: sobran {sorted(columnas_db - columnas)} faltan {sorted(columnas - columnas_db)}")
        nombres_fk = {fk["name"] for fk in insp.get_foreign_keys(name)}
        for fk in table.foreign_key_constraints:
            if fk.name not in nombres_fk:
                diferencias.append(f"falta la clave {fk.name} en {name}")
    if diferencias:
        raise SystemExit("El esquema no coincide con los modelos:\n" + "\n".join(diferencias))


def _historica(engine) -> None:
    with engine.begin() as conn:
        gremio = conn.exec_driver_sql(
            "INSERT INTO gremio (codigo, nombre) VALUES ('HIST', 'Histórico') RETURNING id"
        ).scalar_one()
        conn.exec_driver_sql(
            "INSERT INTO recolector (gremio_id, nombre) VALUES (%(g)s, 'Persona histórica')",
            {"g": gremio},
        )
        unidad = conn.exec_driver_sql(
            "INSERT INTO unidad (tipo, referencia_local) VALUES ('negocio', 'Local histórico') RETURNING id"
        ).scalar_one()
        participante = conn.exec_driver_sql(
            "INSERT INTO participante (nombre) VALUES ('Contacto histórico') RETURNING id"
        ).scalar_one()
        cuenta = conn.exec_driver_sql(
            "INSERT INTO cuenta_operadora (nombre, usuario) VALUES ('Cuenta histórica', 'historica') RETURNING id"
        ).scalar_one()
        solicitud = conn.exec_driver_sql(
            """INSERT INTO solicitud (codigo_pasaporte, unidad_id, participante_id, canal_origen, ubicacion_operativa)
               VALUES ('BR-HIST', %(u)s, %(p)s, 'whatsapp', 'Local histórico') RETURNING id""",
            {"u": unidad, "p": participante},
        ).scalar_one()
        orden = conn.exec_driver_sql(
            "INSERT INTO orden (solicitud_id, gremio_id, estado) VALUES (%(s)s, %(g)s, 'recogida') RETURNING id",
            {"s": solicitud, "g": gremio},
        ).scalar_one()
        conn.exec_driver_sql(
            """INSERT INTO resultado_orden (orden_id, resultado, confirmado_por, ocurrido_at)
               VALUES (%(o)s, 'recogida', %(c)s, '2020-06-01T12:00:00Z')""",
            {"o": orden, "c": cuenta},
        )
        conn.exec_driver_sql(
            "INSERT INTO contenido_educativo (titulo, tipo, texto) VALUES ('Texto viejo', 'texto', 'Contenido previo')"
        )
        material = conn.exec_driver_sql(
            "INSERT INTO material (codigo, nombre, gremio_id) VALUES ('HISTMAT', 'Material viejo', %(g)s) RETURNING id",
            {"g": gremio},
        ).scalar_one()
        conn.exec_driver_sql(
            """INSERT INTO movimiento_puntos (participante_id, delta, tipo, clave_aplicacion, ocurrido_at)
               VALUES (%(p)s, 10, 'abono', 'historico-no-tocar', '2020-06-01T12:00:00Z')""",
            {"p": participante},
        )
    _migrar(HISTORICA, "0006")
    with _engine(HISTORICA).begin() as conn:
        conn.exec_driver_sql(
            """INSERT INTO habilitacion_piloto (participante_id, unidad_id, habilitada_por, created_at)
               VALUES (%(p)s, %(u)s, %(c)s, '2020-01-15T00:00:00Z')""",
            {"p": participante, "u": unidad, "c": cuenta},
        )
    _migrar(HISTORICA, "0009")
    with _engine(HISTORICA).begin() as conn:
        conn.exec_driver_sql(
            """UPDATE resultado_orden
               SET materiales_confirmados = jsonb_build_array(%(m)s::text, '00000000-0000-0000-0000-000000000099', 'no-es-uuid')""",
            {"m": material},
        )
    _migrar(HISTORICA, "head")
    with _engine(HISTORICA).connect() as conn:
        fila = conn.exec_driver_sql(
            """SELECT s.preferencia_horaria, s.preferencia_inicio, s.preferencia_fin, s.preferencia_sin_restriccion,
                      s.tipo_generador, r.huerta_id, r.tipo, res.trabajador_id, res.asignacion_id, ro.acuerdo_canal,
                      res.materiales_confirmados, h.vigente_desde, h.created_at, c.texto, c.tema,
                      (SELECT count(*) FROM resultado_material) AS materiales,
                      (SELECT count(*) FROM movimiento_puntos) AS movimientos,
                      (SELECT detalle_calculo FROM movimiento_puntos WHERE clave_aplicacion = 'historico-no-tocar') AS calculo
               FROM solicitud s
               JOIN orden o ON o.solicitud_id = s.id
               JOIN recolector r ON r.gremio_id = o.gremio_id
               LEFT JOIN asignacion ro ON ro.orden_id = o.id
               JOIN resultado_orden res ON res.orden_id = o.id
               JOIN habilitacion_piloto h ON h.participante_id = s.participante_id
               JOIN contenido_educativo c ON c.titulo = 'Texto viejo'"""
        ).one()
        (
            preferencia, inicio, fin, sin_restriccion, tipo_generador, huerta, tipo, trabajador, asignacion, canal,
            jsonb, vigente, creado, texto, tema, materiales, movimientos, calculo,
        ) = fila
        errores = []
        if any(v is not None for v in (preferencia, inicio, fin, sin_restriccion, tipo_generador, huerta, trabajador, asignacion, canal)):
            errores.append("se inventó preferencia, huerta, ejecutor o canal histórico")
        if tipo != "reciclador":
            errores.append(f"el tipo histórico no quedó en el valor por defecto: {tipo}")
        if texto != "Contenido previo":
            errores.append("se alteró el texto educativo histórico")
        if tema != "separacion":
            errores.append(f"el tema por defecto de 0010 cambió: {tema}")
        if materiales != 1:
            errores.append(f"se copiaron {materiales} materiales; solo el UUID existente debía pasar")
        if movimientos != 1 or calculo is not None:
            errores.append("el movimiento histórico se duplicó o recibió un cálculo inventado")
        if vigente != creado:
            errores.append("vigente_desde no conservó created_at")
        guardados = conn.exec_driver_sql("SELECT materiales_confirmados::text FROM resultado_orden").scalar_one()
        if "no-es-uuid" not in guardados or "00000000-0000-0000-0000-000000000099" not in guardados:
            errores.append("se borró la lista histórica de materiales no identificables")
        if errores:
            raise SystemExit("; ".join(errores))
        if jsonb is None:
            raise SystemExit("la lista histórica no puede volverse nula")


def main() -> None:
    host = os.environ.get("DB_HOST", "127.0.0.1").strip().lower()
    if host not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("BROTA_ALLOW_REMOTE_TEST") != "1":
        raise SystemExit("La verificación solo corre contra un Postgres en loopback")
    try:
        _recrear(VACIA)
        _migrar(VACIA, "head")
        _comparar(_engine(VACIA))
        _recrear(HISTORICA)
        _migrar(HISTORICA, "0004")
        _historica(_engine(HISTORICA))
        _comparar(_engine(HISTORICA))
    finally:
        for nombre in (VACIA, HISTORICA):
            try:
                _eliminar(nombre)
            except Exception as exc:
                print(f"No se pudo borrar {nombre}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
