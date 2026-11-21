"""Conversaciones de Brisa: registro por el bot, lectura por Administración y privacidad."""

from __future__ import annotations

import random
import uuid
from datetime import timedelta

from app.core.tipos import ahora
from tests.conftest import BOT


def _celular() -> str:
    return "5731" + "".join(random.choice("0123456789") for _ in range(8))


def _registrar(client, celular, texto, direccion="entrante", tipo="texto", wamid=None, headers=None):
    cuerpo = {"celular": celular, "direccion": direccion, "tipo": tipo, "texto": texto, "wamid": wamid}
    return client.post("/v1/canal/mensajes", json=cuerpo, headers=BOT if headers is None else headers)


def _conversaciones(client, operador, limit=100) -> list[dict]:
    r = client.get("/v1/conversaciones", params={"limit": limit}, headers=operador("admin", False))
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _sin_celular(texto: str, celular: str) -> None:
    digitos = celular.lstrip("+")
    assert digitos not in texto and digitos[-10:] not in texto


def test_registro_idempotente_por_wamid(client):
    cel = _celular()
    wamid = f"wamid.prueba.{uuid.uuid4().hex}"
    r1 = _registrar(client, cel, "hola", wamid=wamid)
    assert r1.status_code == 201, r1.text
    r2 = _registrar(client, cel, "hola", wamid=wamid)
    assert r2.status_code == 200 and r2.json()["data"]["id"] == r1.json()["data"]["id"]
    # Sin wamid no hay deduplicación: son dos mensajes distintos.
    a = _registrar(client, cel, "otro")
    b = _registrar(client, cel, "otro")
    assert a.status_code == b.status_code == 201 and a.json()["data"]["id"] != b.json()["data"]["id"]


def test_solo_el_servicio_del_bot_registra(client, operador):
    cel = _celular()
    r = _registrar(client, cel, "hola", headers={**BOT, "X-Canal-Celular": cel})
    assert r.status_code == 403
    r = _registrar(client, cel, "hola", headers=operador("admin", False))
    assert r.status_code == 403
    assert _registrar(client, cel, "hola", headers={}).status_code == 401
    assert _registrar(client, "abc", "hola").status_code == 422
    r = client.post("/v1/canal/mensajes", json={"celular": cel, "direccion": "x", "tipo": "texto", "texto": ""},
                    headers=BOT)
    assert r.status_code == 422


def test_texto_largo_se_recorta(client, operador):
    cel = _celular()
    assert _registrar(client, cel, "a" * 5000).status_code == 201
    conv = next(c for c in _conversaciones(client, operador) if c["celular_enmascarado"].endswith(cel[-4:]))
    msjs = client.get(f"/v1/conversaciones/{conv['clave']}/mensajes", headers=operador("admin", False)).json()["data"]
    assert len(msjs[-1]["texto"]) == 4000
    assert len(conv["ultimo_texto"]) <= 120


def test_agrupa_ordena_y_no_revela_el_celular(client, operador):
    viejo, nuevo = _celular(), _celular()
    _registrar(client, viejo, "primero")
    _registrar(client, viejo, f"mi número es {viejo}", direccion="saliente", tipo="interactivo")
    _registrar(client, nuevo, "📷 Foto", tipo="imagen")
    _registrar(client, nuevo, "🎤 Nota de voz", tipo="audio")
    _registrar(client, nuevo, "Gracias", direccion="saliente")

    r = client.get("/v1/conversaciones", params={"limit": 100}, headers=operador("admin", False))
    assert r.status_code == 200
    _sin_celular(r.text, viejo)
    _sin_celular(r.text, nuevo)
    filas = r.json()["data"]
    assert set(r.json()["pagination"]) == {"limit", "offset", "has_more"}
    claves = [f["clave"] for f in filas]
    assert len(claves) == len(set(claves))  # una fila por celular
    i_nuevo = next(i for i, f in enumerate(filas) if f["celular_enmascarado"].endswith(nuevo[-4:]))
    i_viejo = next(i for i, f in enumerate(filas) if f["celular_enmascarado"].endswith(viejo[-4:]))
    assert i_nuevo < i_viejo  # el último mensaje más reciente va primero

    fila = filas[i_nuevo]
    assert set(fila) == {"clave", "nombre", "celular_enmascarado", "ultimo_texto", "ultimo_at",
                         "ultima_direccion", "total", "registrado"}
    assert fila["nombre"] == "Vecino sin registrar" and fila["registrado"] is False
    assert fila["celular_enmascarado"] == f"+57 {nuevo[2:5]} ••• {nuevo[-4:]}"
    assert fila["ultimo_texto"] == "Gracias" and fila["ultima_direccion"] == "saliente" and fila["total"] == 3
    assert len(fila["clave"]) == 24

    r = client.get(f"/v1/conversaciones/{filas[i_viejo]['clave']}/mensajes", headers=operador("admin", False))
    assert r.status_code == 200
    _sin_celular(r.text, viejo)
    msjs = r.json()["data"]
    assert [m["texto"][:7] for m in msjs] == ["primero", "mi núme"]
    assert set(msjs[0]) == {"id", "direccion", "tipo", "texto", "created_at"}
    assert msjs[1]["tipo"] == "interactivo" and "•••" in msjs[1]["texto"]

    # Paginación en orden cronológico.
    r = client.get(f"/v1/conversaciones/{fila['clave']}/mensajes", params={"limit": 2}, headers=operador("admin", False))
    pagina = r.json()
    assert [m["texto"] for m in pagina["data"]] == ["📷 Foto", "🎤 Nota de voz"] and pagina["pagination"]["has_more"]
    r = client.get(f"/v1/conversaciones/{fila['clave']}/mensajes", params={"limit": 2, "offset": 2},
                   headers=operador("admin", False))
    assert [m["texto"] for m in r.json()["data"]] == ["Gracias"]


def test_participante_registrado_tiene_nombre(client, operador):
    _registrar(client, "573100000101", "hola desde la semilla")
    fila = next(c for c in _conversaciones(client, operador) if c["ultimo_texto"] == "hola desde la semilla")
    assert fila["registrado"] is True and fila["nombre"] == "Residente Torre 1 apto 101"


def test_clave_inexistente_y_permisos(client, operador):
    h = operador("admin", False)
    assert client.get("/v1/conversaciones/" + "0" * 24 + "/mensajes", headers=h).status_code == 404
    assert client.get("/v1/conversaciones/no-es-clave/mensajes", headers=h).status_code == 404
    for usuario in ("coord-reciclaje", "fundacion"):
        assert client.get("/v1/conversaciones", headers=operador(usuario, False)).status_code == 403
        assert client.get("/v1/conversaciones/" + "0" * 24 + "/mensajes",
                          headers=operador(usuario, False)).status_code == 403
    assert client.get("/v1/conversaciones", headers=BOT).status_code == 403
    assert client.get("/v1/conversaciones").status_code == 401


def test_retencion_borra_los_mensajes_viejos(client, operador):
    from app.db import get_sessionmaker
    from app.models import MensajeConversacion

    cel = _celular()
    with get_sessionmaker()() as db:
        viejo = MensajeConversacion(celular_normalizado="+" + cel, direccion="entrante", tipo="texto",
                                    texto="mensaje de hace mucho", created_at=ahora() - timedelta(days=31))
        reciente = MensajeConversacion(celular_normalizado="+" + cel, direccion="entrante", tipo="texto",
                                       texto="mensaje de hace poco", created_at=ahora() - timedelta(days=29))
        db.add_all([viejo, reciente])
        db.commit()
        viejo_id, reciente_id = viejo.id, reciente.id

    assert _registrar(client, _celular(), "dispara la limpieza").status_code == 201

    with get_sessionmaker()() as db:
        assert db.get(MensajeConversacion, viejo_id) is None
        assert db.get(MensajeConversacion, reciente_id) is not None
