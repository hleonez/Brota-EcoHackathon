"""Brisa con IA (simulada): texto libre, dudas, fotos y audios. La IA propone; la persona confirma."""

from __future__ import annotations

import asyncio
import base64

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import crear_app
from app.whatsapp import WhatsApp
from tests.test_bot import CEL, APIFalsa, _texto, ajustes, entorno, enviar  # noqa: F401 (fixture)

LAURA = "573000000001"
FOTO = base64.b64encode(b"\xff\xd8\xff jpeg de prueba").decode()


def _botones(msj: dict) -> list[str]:
    return [b["reply"]["id"] for b in msj["interactive"]["action"]["buttons"]]


def _carton(confianza="alta"):
    return {"codigo": "CARTON", "nombre": "Cartón", "confianza": confianza}


def test_texto_libre_con_ia_propone_y_pide_confirmar(entorno):
    c, api = entorno
    api.registrados[CEL] = "Carmen"
    api.ia = {"intencion": "pedir", "residuos": [_carton()]}
    r = enviar(c, "buenas, tengo un reguero de cosas de la mudanza")
    assert api.cuerpos_ia[-1] == {"contexto": "general", "texto": "buenas, tengo un reguero de cosas de la mudanza"}
    assert "Entendí: 📦 Cartón. ¿Es correcto?" in _texto(r[0]) and _botones(r[0]) == ["P_SI_TEXTO", "P_NO_TEXTO"]


def test_duda_respondida_por_la_ia(entorno):
    c, api = entorno
    api.registrados[CEL] = "Carmen"
    enviar(c, lista="M_DUDA")
    api.ia = {"intencion": "duda", "residuos": [_carton()],
              "respuesta": "Las cajas de pizza con grasa no sirven 🍕 Corta y entrega solo la parte limpia."}
    r = enviar(c, "¿las cajas de pizza se reciclan?")
    assert _texto(r[0]) == "Las cajas de pizza con grasa no sirven 🍕 Corta y entrega solo la parte limpia."
    assert _botones(r[1])[0] == "P_ADDS:CARTON"


def test_sin_ia_el_texto_libre_usa_los_sinonimos(entorno):
    c, api = entorno
    api.registrados[CEL] = "Carmen"  # api.ia = None → 503
    r = enviar(c, "qué hago con unas cajas")
    assert "se recibe en la ruta" in _texto(r[0])


@pytest.mark.parametrize(
    ("mensaje", "intencion", "esperado"),
    [
        ("nadie ha venido por mis cosas desde ayer", "queja", "lo dejé registrado (CA-00001)"),
        ("tengo un problema", "queja", "Cuéntame qué pasó"),
        ("quiero hablar con alguien", "persona", "una persona del equipo te responde"),
        ("ya no quiero que vengan", "cancelar", "No tienes solicitudes pendientes por cancelar"),
    ],
)
def test_la_ia_lleva_quejas_ayuda_y_cancelar_a_su_flujo(entorno, mensaje, intencion, esperado):
    c, api = entorno
    api.registrados[CEL] = "Carmen"
    api.ia = {"intencion": intencion}
    assert esperado in _texto(enviar(c, mensaje)[0])


# ------------------------------------------------------------------ fotos y audios (vía laboratorio)


@pytest.fixture
def lab():
    api = APIFalsa()
    api.registrados[LAURA] = "Laura"
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(api))
    with TestClient(crear_app(ajustes(lab_activo=True), cliente, procesar_en_linea=True)) as c:
        yield c, api


def _media(c, mime, pie=None) -> list[dict]:
    antes = c.get("/lab/estado").json()["seq"]
    r = c.post("/lab/mensaje", json={"de": LAURA, "texto": pie, "media": {"mime_type": mime, "datos_base64": FOTO}})
    assert r.status_code == 200, r.text
    eventos = c.get("/lab/estado", params={"desde": antes}).json()["eventos"]
    assert eventos[0]["dir"] == "in" and eventos[0]["texto"].startswith(("📸 Foto", "🎤 Audio"))
    return [e["mensaje"] for e in eventos if e["dir"] == "out"]


def test_foto_propone_materiales_y_queda_como_fuente_foto(lab):
    c, api = lab
    api.ia = {"intencion": "pedir", "observado": "dos botellas plásticas y una caja",
              "residuos": [{"codigo": "PET", "nombre": "Botellas plásticas", "confianza": "alta"}, _carton("media")]}
    r = _media(c, "image/jpeg", pie="esto es lo que tengo")
    assert api.cuerpos_ia[-1]["media"] == {"mime_type": "image/jpeg", "datos_base64": FOTO}
    assert api.cuerpos_ia[-1]["texto"] == "esto es lo que tengo"
    cuerpo = _texto(r[0])
    assert cuerpo.startswith("📸 En la foto veo: dos botellas plásticas y una caja")
    assert "Entendí: 📦 Cartón y 🧴 Botellas plásticas" in cuerpo or "Entendí: 🧴 Botellas plásticas y 📦 Cartón" in cuerpo

    c.post("/lab/mensaje", json={"de": LAURA, "respuesta_id": "P_SI_TEXTO", "respuesta_titulo": "Sí"})
    for boton in ("P_V:PET:vacias:si", "P_V:PET:quimicos:no", "P_V:CARTON:seco:si", "P_LISTO", "P_SIN", "P_ENVIAR"):
        c.post("/lab/mensaje", json={"de": LAURA, "respuesta_id": boton, "respuesta_titulo": "x"})
    cuerpo = api.cuerpos_solicitud[0]
    assert {r["fuente"] for r in cuerpo["residuos"]} == {"foto"}
    assert cuerpo["preferencia_sin_restriccion"] is True
    assert "preferencia_inicio" not in cuerpo and "preferencia_fin" not in cuerpo


def test_audio_con_peligro_y_consulta_de_puntos(lab):
    c, api = lab
    api.ia = {"intencion": "puntos", "transcripcion": "¿cuántos puntos tengo?"}
    r = _media(c, "audio/ogg; codecs=opus")
    assert _texto(r[0]) == "🎤 Te escuché: «¿cuántos puntos tengo?»"
    assert "Tienes 25 puntos" in _texto(r[1])

    api.ia = {"intencion": "pedir", "transcripcion": "tengo pilas viejas",
              "residuos": [{"codigo": "PILAS", "nombre": "Pilas y baterías", "confianza": "alta"}],
              "peligros": ["Las pilas tienen metales pesados."]}
    cuerpo = _texto(_media(c, "audio/ogg")[0])
    assert "🎤 Te escuché: «tengo pilas viejas»\n⚠ Las pilas tienen metales pesados." in cuerpo


def test_foto_sin_ia_o_sin_material_reconocible(lab):
    c, api = lab
    assert "no puedo escuchar audios ni ver fotos" in _texto(_media(c, "image/png")[0])  # IA no disponible
    api.ia = {"intencion": "otro", "observado": "una foto borrosa"}
    assert "otra foto más de cerca" in _texto(_media(c, "image/png")[0])


def test_descarga_de_media_desde_meta():
    pedidas: list[httpx.Request] = []

    def graph(req: httpx.Request) -> httpx.Response:
        pedidas.append(req)
        if req.url.host == "graph.facebook.com":
            return httpx.Response(200, json={"url": "https://lookaside.fbsbx.com/whatsapp/abc", "mime_type": "audio/ogg",
                                             "file_size": 12})
        return httpx.Response(200, content=b"OggS audio..", headers={"content-type": "audio/ogg"})

    s = ajustes(whatsapp_dry_run=False, whatsapp_token="t", whatsapp_phone_number_id="123")

    async def correr():
        async with httpx.AsyncClient(transport=httpx.MockTransport(graph)) as cli:
            return await WhatsApp(s, cli).descargar_media("media123")

    assert asyncio.run(correr()) == (b"OggS audio..", "audio/ogg")
    assert pedidas[0].url.path.endswith("/media123")
    assert all(p.headers["Authorization"] == "Bearer t" for p in pedidas)
