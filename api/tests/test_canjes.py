"""Canjes de Moneda Verde contra PostgreSQL de prueba (brota_test), nunca contra brota."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errores import AppError
from app.core.seguridad import Actor
from app.core.tipos import ahora
from app.db import get_sessionmaker
from app.models import MovimientoPuntos
from app.modulos.canjes import reservar_canje
from tests.conftest import bot

_seq = 0


def _err(r) -> str:
    return r.json()["error"]["code"]


def _persona(client, catalogo) -> tuple[str, str]:
    global _seq
    _seq += 1
    celular = f"57319991{_seq:04d}"
    piso = ((_seq - 1) // 4) + 1
    apto = ((_seq - 1) % 4) + 1
    unidades = client.get(
        "/v1/unidades",
        params={"torre_id": catalogo["torre:4"], "referencia": f"{piso}{apto:02d}"},
        headers=bot(celular, False),
    )
    assert unidades.status_code == 200 and unidades.json()["data"], unidades.text
    me = client.get("/v1/me", headers=bot(celular, False)).json()["data"]
    alta = client.post(
        "/v1/registros",
        headers=bot(celular),
        json={
            "nombre": f"Persona Canje {_seq}",
            "unidad_id": unidades.json()["data"][0]["id"],
            "consentimiento": {"version_politica": me["politica_datos_version"], "decision": "aceptado"},
        },
    )
    assert alta.status_code == 201, alta.text
    return celular, client.get("/v1/me", headers=bot(celular, False)).json()["data"]["participante_id"]


def _abonar(participante_id: str, puntos: str, clave: str) -> None:
    with get_sessionmaker()() as db:
        db.add(
            MovimientoPuntos(
                participante_id=uuid.UUID(participante_id),
                delta=Decimal(puntos),
                tipo="abono",
                clave_aplicacion=clave,
                ocurrido_at=ahora(),
                detalle_calculo={
                    "modalidad": "entrega_valida",
                    "cantidad": "1",
                    "puntos_por_entrega": puntos,
                    "total": puntos,
                },
            )
        )
        db.commit()


def _item(client, operador, catalogo, costo: str, existencias: int | None, nombre: str) -> dict:
    aliado = client.post(
        "/v1/aliados",
        headers=operador("admin"),
        json={"nombre": f"Aliado {nombre}", "gremio_id": catalogo["gremios:ECORAZON"]},
    )
    assert aliado.status_code == 201, aliado.text
    cuerpo: dict = {"aliado_id": aliado.json()["data"]["id"], "nombre": nombre, "costo_puntos": costo}
    if existencias is not None:
        cuerpo["existencias"] = existencias
    item = client.post("/v1/items-canje", headers=operador("admin"), json=cuerpo)
    assert item.status_code == 201, item.text
    return item.json()["data"]


def _saldo(client, celular: str) -> str:
    return client.get("/v1/me/puntos", headers=bot(celular, False)).json()["data"]["saldo"]


def _movs(client, celular: str) -> list[dict]:
    return client.get("/v1/me/movimientos-puntos", headers=bot(celular, False), params={"limit": 100}).json()["data"]


def _stock(client, operador, item_id: str):
    filas = client.get("/v1/items-canje", headers=operador("admin", False), params={"limit": 100}).json()["data"]
    return next(x["existencias"] for x in filas if x["id"] == item_id)


def _sin_celular(valor) -> None:
    if isinstance(valor, dict):
        assert "celular" not in valor
        for hijo in valor.values():
            _sin_celular(hijo)
    elif isinstance(valor, list):
        for hijo in valor:
            _sin_celular(hijo)


def test_catalogo_de_la_semilla_y_modulo_activo(client):
    caps = client.get("/v1/capacidades").json()["data"]
    assert caps["modulos"]["canjes"] is True
    r = client.get("/v1/catalogo-canjes", headers=bot("573100000101", False), params={"limit": 100})
    assert r.status_code == 200, r.text
    nombres = {x["nombre"] for x in r.json()["data"]}
    assert {"Bolsa de abono", "Plántula", "Descuento del corredor"} <= nombres
    descuento = next(x for x in r.json()["data"] if x["nombre"] == "Descuento del corredor")
    assert descuento["existencias"] is None
    _sin_celular(r.json())


def test_canje_descuenta_una_vez_y_la_misma_clave_no_repite(client, catalogo, operador):
    celular, pid = _persona(client, catalogo)
    _abonar(pid, "40.00", f"abono-feliz-{pid}")
    item = _item(client, operador, catalogo, "15.00", 4, f"Bolsa prueba {pid[:8]}")
    cuerpo = {"item_id": item["id"]}
    headers = bot(celular)
    r = client.post("/v1/canjes", headers=headers, json=cuerpo)
    assert r.status_code == 201, r.text
    canje = r.json()["data"]
    assert canje["estado"] == "reservado" and canje["total_puntos"] == "15.00"
    assert canje["participante_id"] == pid
    _sin_celular(r.json())
    assert _saldo(client, celular) == "25.00"
    assert _stock(client, operador, item["id"]) == 3
    debitos = [m for m in _movs(client, celular) if m["tipo"] == "debito_canje"]
    assert len(debitos) == 1 and debitos[0]["delta"] == "-15.00"
    repetido = client.post("/v1/canjes", headers=headers, json=cuerpo)
    assert repetido.status_code == 201 and repetido.json() == r.json()
    assert repetido.headers.get("Idempotent-Replayed") == "true"
    assert _saldo(client, celular) == "25.00"
    assert _stock(client, operador, item["id"]) == 3
    assert len([m for m in _movs(client, celular) if m["tipo"] == "debito_canje"]) == 1
    with get_sessionmaker()() as db:
        claves = db.execute(
            select(MovimientoPuntos.clave_aplicacion).where(MovimientoPuntos.participante_id == uuid.UUID(pid))
        ).scalars().all()
    assert f"canje:{canje['id']}" in claves


def test_saldo_insuficiente_responde_409_y_no_mueve_nada(client, catalogo, operador):
    celular, pid = _persona(client, catalogo)
    _abonar(pid, "10.00", f"abono-corto-{pid}")
    item = _item(client, operador, catalogo, "30.00", 5, f"Premio caro {pid[:8]}")
    r = client.post("/v1/canjes", headers=bot(celular), json={"item_id": item["id"]})
    assert r.status_code == 409 and _err(r) == "SALDO_INSUFICIENTE"
    assert _saldo(client, celular) == "10.00"
    assert _stock(client, operador, item["id"]) == 5
    assert [m for m in _movs(client, celular) if m["tipo"] == "debito_canje"] == []


def test_la_ultima_unidad_queda_en_un_solo_canje(client, catalogo, operador):
    celular, pid = _persona(client, catalogo)
    _abonar(pid, "100.00", f"abono-stock-{pid}")
    item = _item(client, operador, catalogo, "10.00", 1, f"Ultima unidad {pid[:8]}")
    primero = client.post("/v1/canjes", headers=bot(celular), json={"item_id": item["id"]})
    segundo = client.post("/v1/canjes", headers=bot(celular), json={"item_id": item["id"]})
    assert primero.status_code == 201, primero.text
    assert segundo.status_code == 409 and _err(segundo) == "SIN_EXISTENCIAS"
    assert _stock(client, operador, item["id"]) == 0
    assert _saldo(client, celular) == "90.00"
    assert len([m for m in _movs(client, celular) if m["tipo"] == "debito_canje"]) == 1


def test_dos_canjes_concurrentes_no_gastan_el_mismo_saldo(client, catalogo, operador):
    celular, pid = _persona(client, catalogo)
    _abonar(pid, "40.00", f"abono-carrera-{pid}")
    premio_a = _item(client, operador, catalogo, "40.00", None, f"Premio A {pid[:8]}")
    premio_b = _item(client, operador, catalogo, "40.00", None, f"Premio B {pid[:8]}")
    actor = Actor(tipo="participante", canal="whatsapp", participante_id=uuid.UUID(pid))
    barrera = threading.Barrier(2)

    def correr(item_id: str) -> str:
        with get_sessionmaker()() as db:
            try:
                barrera.wait(timeout=10)
                reservar_canje(db, actor, item_id=uuid.UUID(item_id), participante_id=None, cantidad=1)
                db.commit()
                return "ok"
            except AppError as exc:
                db.rollback()
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = set(pool.map(correr, [premio_a["id"], premio_b["id"]]))
    assert resultados == {"ok", "SALDO_INSUFICIENTE"}
    assert _saldo(client, celular) == "0.00"
    assert len([m for m in _movs(client, celular) if m["tipo"] == "debito_canje"]) == 1


def test_cancelar_devuelve_el_saldo_una_sola_vez_y_entregado_no_se_revierte(client, catalogo, operador):
    celular, pid = _persona(client, catalogo)
    _abonar(pid, "50.00", f"abono-cancel-{pid}")
    item = _item(client, operador, catalogo, "20.00", 2, f"Plantula prueba {pid[:8]}")
    creado = client.post("/v1/canjes", headers=bot(celular), json={"item_id": item["id"], "cantidad": 1})
    assert creado.status_code == 201, creado.text
    canje_id = creado.json()["data"]["id"]
    assert _saldo(client, celular) == "30.00"
    clave = bot(celular)
    cancelado = client.post(f"/v1/canjes/{canje_id}/cancelacion", headers=clave)
    assert cancelado.status_code == 200, cancelado.text
    assert cancelado.json()["data"]["estado"] == "cancelado"
    _sin_celular(cancelado.json())
    repetido = client.post(f"/v1/canjes/{canje_id}/cancelacion", headers=clave)
    assert repetido.headers.get("Idempotent-Replayed") == "true"
    otra = client.post(f"/v1/canjes/{canje_id}/cancelacion", headers=bot(celular))
    assert otra.status_code == 409 and _err(otra) == "INVALID_TRANSITION"
    assert _saldo(client, celular) == "50.00"
    assert _stock(client, operador, item["id"]) == 2
    reintegros = [m for m in _movs(client, celular) if m["tipo"] == "reintegro"]
    assert len(reintegros) == 1 and reintegros[0]["delta"] == "20.00"

    segundo = client.post("/v1/canjes", headers=bot(celular), json={"item_id": item["id"]})
    assert segundo.status_code == 201, segundo.text
    entregado = client.post(
        f"/v1/canjes/{segundo.json()['data']['id']}/entrega", headers=operador("coord-huerta")
    )
    assert entregado.status_code == 200 and entregado.json()["data"]["estado"] == "entregado"
    assert _saldo(client, celular) == "30.00"
    no = client.post(f"/v1/canjes/{segundo.json()['data']['id']}/cancelacion", headers=operador("coord-huerta"))
    assert no.status_code == 409 and _err(no) == "INVALID_TRANSITION"
    assert _saldo(client, celular) == "30.00"
    assert _stock(client, operador, item["id"]) == 1


def test_otro_gremio_recibe_403(client, catalogo, operador):
    celular, pid = _persona(client, catalogo)
    _abonar(pid, "40.00", f"abono-gremio-{pid}")
    item = _item(client, operador, catalogo, "10.00", 3, f"Premio huerta {pid[:8]}")
    creado = client.post("/v1/canjes", headers=bot(celular), json={"item_id": item["id"]})
    assert creado.status_code == 201, creado.text
    canje_id = creado.json()["data"]["id"]
    propios = client.get("/v1/canjes", headers=bot(celular, False)).json()["data"]
    assert [c["id"] for c in propios] == [canje_id]
    huerta = client.get("/v1/canjes", headers=operador("coord-huerta", False), params={"limit": 100}).json()["data"]
    assert canje_id in {c["id"] for c in huerta}
    reciclaje = client.get("/v1/canjes", headers=operador("coord-reciclaje", False), params={"limit": 100}).json()["data"]
    assert canje_id not in {c["id"] for c in reciclaje}
    ajeno = client.post(f"/v1/canjes/{canje_id}/entrega", headers=operador("coord-reciclaje"))
    assert ajeno.status_code == 403 and _err(ajeno) == "FORBIDDEN"
    cancelar = client.post(f"/v1/canjes/{canje_id}/cancelacion", headers=operador("coord-reciclaje"))
    assert cancelar.status_code == 403
    fundacion = client.get("/v1/canjes", headers=operador("fundacion", False))
    assert fundacion.status_code == 403
    sigue = client.get(f"/v1/canjes", headers=bot(celular, False)).json()["data"][0]
    assert sigue["estado"] == "reservado"


def test_coordinacion_canjea_por_la_persona_y_el_costo_tiene_que_ser_positivo(client, catalogo, operador):
    celular, pid = _persona(client, catalogo)
    _abonar(pid, "25.00", f"abono-coord-{pid}")
    item = _item(client, operador, catalogo, "25.00", None, f"Descuento prueba {pid[:8]}")
    falta = client.post("/v1/canjes", headers=operador("coord-huerta"), json={"item_id": item["id"]})
    assert falta.status_code == 422
    otro = client.post(
        "/v1/canjes",
        headers=operador("coord-reciclaje"),
        json={"item_id": item["id"], "participante_id": pid},
    )
    assert otro.status_code == 403
    ok = client.post(
        "/v1/canjes",
        headers=operador("coord-huerta"),
        json={"item_id": item["id"], "participante_id": pid},
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["data"]["participante_nombre"] == f"Persona Canje {_seq}"
    _sin_celular(ok.json())
    assert _saldo(client, celular) == "0.00"
    caro = client.post(
        "/v1/items-canje",
        headers=operador("admin"),
        json={"aliado_id": item["aliado_id"], "nombre": "Costo cero", "costo_puntos": "0.00"},
    )
    assert caro.status_code == 422


def test_el_libro_rechaza_debito_positivo_y_acepta_el_abono(client):
    me = client.get("/v1/me", headers=bot("573100000101", False)).json()["data"]
    pid = uuid.UUID(me["participante_id"])
    with get_sessionmaker()() as db:
        db.add(
            MovimientoPuntos(
                participante_id=pid,
                delta=Decimal("1.00"),
                tipo="debito_canje",
                clave_aplicacion=f"debito-malo-{uuid.uuid4()}",
                ocurrido_at=ahora(),
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(
            MovimientoPuntos(
                participante_id=pid,
                delta=Decimal("-1.00"),
                tipo="reintegro",
                clave_aplicacion=f"reintegro-malo-{uuid.uuid4()}",
                ocurrido_at=ahora(),
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(
            MovimientoPuntos(
                participante_id=pid,
                delta=Decimal("3.00"),
                tipo="abono",
                clave_aplicacion=f"abono-sigue-{uuid.uuid4()}",
                ocurrido_at=ahora(),
            )
        )
        db.commit()
