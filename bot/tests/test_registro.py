"""Registro de la conversación en la API y saludo editable desde Administración."""

from __future__ import annotations

import asyncio
import json

import httpx
from fastapi.testclient import TestClient

from app import textos as T
from app.brota import Brota
from app.main import crear_app
from app.registro import Registro, describir_entrante, describir_saliente
from app.whatsapp import Boton, Entrante, WhatsApp
from tests.test_bot import CEL, APIFalsa, _texto, ajustes, enviar


def _correr(api: APIFalsa, *pasos: dict) -> list[list[dict]]:
    """Envía los mensajes y cierra la app: al apagar se esperan los registros pendientes."""
    respuestas = []
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(api))
    with TestClient(crear_app(ajustes(), cliente, procesar_en_linea=True)) as c:
        for paso in pasos:
            respuestas.append(enviar(c, **paso))
    return respuestas


def test_registra_entrantes_y_salientes():
    api = APIFalsa()
    respuestas = _correr(api, {"texto": "hola", "wamid": "wamid.in.1"}, {"texto": "Carmen", "wamid": "wamid.in.2"})
    entrantes = [m for m in api.mensajes if m["direccion"] == "entrante"]
    salientes = [m for m in api.mensajes if m["direccion"] == "saliente"]
    assert entrantes == [
        {"celular": CEL, "direccion": "entrante", "tipo": "texto", "texto": "hola", "wamid": "wamid.in.1"},
        {"celular": CEL, "direccion": "entrante", "tipo": "texto", "texto": "Carmen", "wamid": "wamid.in.2"},
    ]
    assert salientes[0] == {"celular": CEL, "direccion": "saliente", "tipo": "texto",
                            "texto": _texto(respuestas[0][0]), "wamid": None}  # dry-run: sin id de Meta
    lista = salientes[1]
    assert lista["tipo"] == "interactivo"
    assert lista["texto"] == _texto(respuestas[1][0]) + " · Torre 1 | Torre 3"


def test_respuesta_de_boton_se_registra_con_su_titulo():
    api = APIFalsa()
    api.registrados[CEL] = "Carmen"
    _correr(api, {"boton": "M_PUNTOS"})
    entrante = next(m for m in api.mensajes if m["direccion"] == "entrante")
    assert entrante["tipo"] == "interactivo" and entrante["texto"] == "M_PUNTOS"


def test_si_la_api_falla_brisa_sigue_igual():
    api = APIFalsa()
    api.mensajes_falla = True
    respuestas = _correr(api, {"texto": "hola"}, {"texto": "Carmen"})
    assert "Soy Brisa" in _texto(respuestas[0][0])
    assert respuestas[1][0]["interactive"]["type"] == "list"
    llamadas = [r for r in api.llamadas if r.url.path == "/v1/canal/mensajes"]
    assert len(llamadas) == 4 and api.mensajes == []  # se intentó y falló sin romper nada


def test_si_la_api_no_responde_brisa_sigue_igual():
    api = APIFalsa()

    def caida(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/v1/canal/mensajes":
            raise httpx.ConnectError("sin conexión")
        return api(req)

    cliente = httpx.AsyncClient(transport=httpx.MockTransport(caida))
    with TestClient(crear_app(ajustes(), cliente, procesar_en_linea=True)) as c:
        assert "Soy Brisa" in _texto(enviar(c, "hola")[0])


def test_descripciones_de_entrantes():
    def e(tipo, **kw):
        return describir_entrante(Entrante(wamid="w", de=CEL, tipo=tipo, **kw))

    assert e("text", texto="hola") == ("texto", "hola")
    assert e("audio") == ("audio", "🎤 Nota de voz")
    assert e("image") == ("imagen", "📷 Foto")
    assert e("image", texto="mis botellas") == ("imagen", "📷 Foto: mis botellas")
    assert e("interactive", respuesta_id="ACEPTO", respuesta_titulo="Sí, acepto") == ("interactivo", "Sí, acepto")
    assert e("button", respuesta_id="X", respuesta_titulo="Listo") == ("interactivo", "Listo")
    assert e("sticker")[0] == "sistema"


def test_descripciones_de_salientes():
    plantilla = {"to": CEL, "type": "template", "template": {
        "name": "brota_asignacion", "language": {"code": "es"},
        "components": [{"type": "body", "parameters": [{"type": "text", "text": "Rosa"}, {"type": "text", "text": "hoy"}]}],
    }}
    assert describir_saliente(plantilla) == ("plantilla", "Plantilla brota_asignacion: Rosa | hoy")
    assert describir_saliente({"status": "read", "message_id": "w"}) is None


def test_envio_real_usa_el_wamid_de_meta():
    api = APIFalsa()

    def ruteo(req: httpx.Request) -> httpx.Response:
        if req.url.host == "graph.facebook.com":
            return httpx.Response(200, json={"messages": [{"id": "wamid.meta.123"}]})
        return api(req)

    s = ajustes(whatsapp_dry_run=False, whatsapp_token="t", whatsapp_phone_number_id="123")

    async def correr():
        async with httpx.AsyncClient(transport=httpx.MockTransport(ruteo)) as cli:
            registro = Registro(Brota(s, cli))
            wa = WhatsApp(s, cli, registro=registro)
            await wa.botones(CEL, "¿Aceptas?", [Boton("SI", "Sí"), Boton("NO", "No")])
            await registro.esperar()

    asyncio.run(correr())
    assert api.mensajes == [{"celular": CEL, "direccion": "saliente", "tipo": "interactivo",
                             "texto": "¿Aceptas? · Sí | No", "wamid": "wamid.meta.123"}]


def test_saludo_editado_en_administracion_con_cache():
    api = APIFalsa()
    api.programa = {"mensaje_bienvenida": "¡Bienvenido a EcoConecta! 🌱"}
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(api))
    with TestClient(crear_app(ajustes(), cliente, procesar_en_linea=True)) as c:
        assert _texto(enviar(c, "hola")[0]) == "¡Bienvenido a EcoConecta! 🌱\n\n" + T.PREGUNTA_NOMBRE
        api.programa = {"mensaje_bienvenida": "Otro saludo, ¿cómo te llamas?"}
        # En caché 5 minutos: otro vecino nuevo recibe todavía el mismo saludo.
        assert _texto(enviar(c, "hola", de="573009998877")[0]).startswith("¡Bienvenido a EcoConecta!")
    pedidas = [r for r in api.llamadas if r.url.path == "/v1/programa"]
    assert len(pedidas) == 1


def test_saludo_vacio_o_api_caida_usa_el_de_siempre():
    api = APIFalsa()
    api.programa = {"mensaje_bienvenida": ""}
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(api))
    with TestClient(crear_app(ajustes(), cliente, procesar_en_linea=True)) as c:
        assert _texto(enviar(c, "hola")[0]) == T.BIENVENIDA
    api = APIFalsa()  # sin /v1/programa: 404
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(api))
    with TestClient(crear_app(ajustes(), cliente, procesar_en_linea=True)) as c:
        assert _texto(enviar(c, "hola")[0]) == T.BIENVENIDA


def test_cuerpo_del_registro_va_como_servicio():
    api = APIFalsa()
    _correr(api, {"texto": "hola"})
    req = next(r for r in api.llamadas if r.url.path == "/v1/canal/mensajes")
    assert "X-Canal-Celular" not in req.headers and req.method == "POST"
    assert set(json.loads(req.content)) == {"celular", "direccion", "tipo", "texto", "wamid"}
