"""Actividad (auditoría): GET /v1/eventos y /v1/eventos/tipos."""

from __future__ import annotations

from datetime import timedelta

from app.core.tipos import ahora
from tests.conftest import BOT


def _insertar(**campos):
    from app.db import get_sessionmaker
    from app.models import EventoDominio

    with get_sessionmaker()() as db:
        e = EventoDominio(**campos)
        db.add(e)
        db.commit()
        return e.id


def test_evento_de_administracion_con_nombre_del_actor(client, operador):
    r = client.patch("/v1/programa", json={"horario_atencion": "Lunes a viernes"}, headers=operador("admin"))
    assert r.status_code == 200, r.text

    r = client.get("/v1/eventos", params={"tipo": "programa_actualizado"}, headers=operador("admin", False))
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert set(cuerpo["pagination"]) == {"limit", "offset", "has_more"}
    e = cuerpo["data"][0]
    assert set(e) == {"id", "tipo", "ocurrido_at", "actor_tipo", "actor_nombre", "solicitud_id", "orden_id",
                      "pesaje_id", "datos"}
    assert e["tipo"] == "programa_actualizado" and e["actor_tipo"] == "operador"
    assert e["actor_nombre"] == "Administración Brota"
    assert e["datos"] == {"claves": ["horario_atencion"]}
    assert all(x["tipo"] == "programa_actualizado" for x in cuerpo["data"])

    tipos = client.get("/v1/eventos/tipos", headers=operador("admin", False)).json()["data"]
    assert "programa_actualizado" in tipos and tipos == sorted(set(tipos))
    client.patch("/v1/programa", json={"horario_atencion": None}, headers=operador("admin"))


def test_nombres_de_brisa_participante_y_sistema_y_celulares_ocultos(client, operador):
    from app.db import get_sessionmaker
    from app.models import Participante
    from sqlalchemy import select

    with get_sessionmaker()() as db:
        p = db.execute(select(Participante).where(Participante.celular_normalizado == "+573100000101")).scalar_one()
        pid = p.id
    _insertar(tipo="prueba_auditoria", actor_tipo="servicio", datos={"celular": "+573001234567",
                                                                      "nota": "llamar al 3001234567 hoy",
                                                                      "codigo": "BR-00001"})
    _insertar(tipo="prueba_auditoria", actor_tipo="participante", actor_id=pid, datos={})
    _insertar(tipo="prueba_auditoria", actor_tipo="sistema", datos={})
    _insertar(tipo="prueba_auditoria", actor_tipo="no_registrado", datos={})

    r = client.get("/v1/eventos", params={"tipo": "prueba_auditoria"}, headers=operador("admin", False))
    assert r.status_code == 200
    assert "3001234567" not in r.text
    por_tipo = {e["actor_tipo"]: e for e in r.json()["data"]}
    assert por_tipo["servicio"]["actor_nombre"] == "Brisa"
    assert por_tipo["servicio"]["datos"]["celular"] == "+57 300 ••• 4567"
    assert por_tipo["servicio"]["datos"]["nota"] == "llamar al 300 ••• 4567 hoy"
    assert por_tipo["servicio"]["datos"]["codigo"] == "BR-00001"
    assert por_tipo["participante"]["actor_nombre"] == "Residente Torre 1 apto 101"
    assert por_tipo["sistema"]["actor_nombre"] == "Sistema"
    assert por_tipo["no_registrado"]["actor_nombre"] is None


def test_filtros_de_fecha_y_orden(client, operador):
    h = operador("admin", False)
    viejo = _insertar(tipo="prueba_fechas", actor_tipo="sistema", datos={}, ocurrido_at=ahora() - timedelta(days=10))
    nuevo = _insertar(tipo="prueba_fechas", actor_tipo="sistema", datos={})
    ids = [e["id"] for e in client.get("/v1/eventos", params={"tipo": "prueba_fechas"}, headers=h).json()["data"]]
    assert ids == [str(nuevo), str(viejo)]

    desde = (ahora() - timedelta(days=1)).isoformat()
    r = client.get("/v1/eventos", params={"tipo": "prueba_fechas", "desde": desde}, headers=h)
    assert [e["id"] for e in r.json()["data"]] == [str(nuevo)]
    r = client.get("/v1/eventos", params={"tipo": "prueba_fechas", "hasta": desde}, headers=h)
    assert [e["id"] for e in r.json()["data"]] == [str(viejo)]
    hasta = (ahora() - timedelta(days=2)).isoformat()
    assert client.get("/v1/eventos", params={"desde": desde, "hasta": hasta}, headers=h).status_code == 422


def test_solo_administracion(client, operador):
    for usuario in ("coord-reciclaje", "fundacion"):
        assert client.get("/v1/eventos", headers=operador(usuario, False)).status_code == 403
        assert client.get("/v1/eventos/tipos", headers=operador(usuario, False)).status_code == 403
    assert client.get("/v1/eventos", headers=BOT).status_code == 403
    assert client.get("/v1/eventos").status_code == 401
