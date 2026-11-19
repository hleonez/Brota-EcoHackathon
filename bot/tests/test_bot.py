"""Pruebas del bot con la API de Brota y la Graph API de Meta simuladas (httpx.MockTransport)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import avisos
from app.brota import Brota
from app.config import Settings
from app.main import crear_app
from app.simular import payload
from app.whatsapp import WhatsApp

SECRETO = "secreto-de-la-app"
CEL = "573001112233"


def ajustes(**extra) -> Settings:
    base = dict(
        whatsapp_dry_run=True, whatsapp_app_secret=SECRETO, whatsapp_verify_token="verificar",
        bot_service_token="token-bot", brota_api_url="http://brota.test", avisos_activos=False,
    )
    return Settings(_env_file=None, **{**base, **extra})


class APIFalsa:
    """Imita las rutas de la API de Brota que usa el bot."""

    def __init__(self) -> None:
        self.registrados: dict[str, str] = {}
        self.llamadas: list[httpx.Request] = []
        self.abiertas: set[str] = set()
        self.claves_solicitud: dict[str, dict] = {}
        self.avisos: list[dict] = []
        self.confirmaciones: list[tuple[str, dict]] = []
        self.cuerpos_solicitud: list[dict] = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.llamadas.append(req)
        assert req.headers["Authorization"] == "Bearer token-bot"
        cel = req.headers.get("X-Canal-Celular")
        p, m = req.url.path, req.method
        if p == "/v1/me":
            if cel in self.registrados:
                return _ok({"registrado": True, "nombre": self.registrados[cel], "politica_datos_version": "2026-11",
                            "unidades": [{"id": "u402", "conjunto_id": "c1", "torre_id": "t3"}]})
            return _ok({"registrado": False, "politica_datos_version": "2026-11", "unidades": []})
        if p == "/v1/conjuntos":
            return _ok([{"id": "c1", "nombre": "Brisas de San Pablo"}])
        if p == "/v1/conjuntos/c1/torres":
            return _ok([{"id": "t1", "codigo": "1", "nombre": "Torre 1"}, {"id": "t3", "codigo": "3", "nombre": "Torre 3"}])
        if p == "/v1/unidades":
            q = req.url.params
            if q.get("torre_id") == "t3" and q.get("referencia") == "402":
                return _ok([{"id": "u402", "etiqueta": "Torre 3 · Apto 402"}])
            return _ok([])
        if p == "/v1/registros" and m == "POST":
            cuerpo = json.loads(req.content)
            assert req.headers["Idempotency-Key"].startswith("wamid.")
            assert cuerpo["consentimiento"] == {"version_politica": "2026-11", "decision": "aceptado"}
            self.registrados[cel] = cuerpo["nombre"]
            return _ok({"participante_id": "p1", "estado_registro": "completo"}, 201)
        if p == "/v1/residuos":
            return _ok(RESIDUOS)
        if p == "/v1/catalogos":
            return _ok({"tipos_servicio": [{"id": "s-rec", "codigo": "RECICLABLES"}, {"id": "s-org", "codigo": "ORGANICOS"}]})
        if p == "/v1/solicitudes" and m == "POST":
            clave = req.headers["Idempotency-Key"]
            if clave in self.claves_solicitud:
                return _ok(self.claves_solicitud[clave], 201)
            cuerpo = json.loads(req.content)
            self.cuerpos_solicitud.append(cuerpo)
            servicio = {r["id"]: r["tipo_servicio_id"] for r in RESIDUOS}
            ids = cuerpo.get("tipo_servicio_ids") or sorted({servicio[r["residuo_id"]] for r in cuerpo["residuos"]})
            if self.abiertas & set(ids):
                return httpx.Response(409, json={"error": {"code": "OPEN_REQUEST_EXISTS", "message": "x",
                                                           "codigo_pasaporte": "BR-00001"}})
            self.abiertas |= set(ids)
            s = {"id": "s1", "codigo_pasaporte": "BR-00001", "tipo_servicio_ids": ids}
            self.claves_solicitud[clave] = s
            return _ok(s, 201)
        if p == "/v1/me/puntos":
            return _ok({"saldo": "25.00", "movimientos": 2})
        if p == "/v1/canal/avisos/reservas":
            lote, self.avisos = self.avisos, []
            return _ok(lote)
        if p.startswith("/v1/canal/avisos/") and p.endswith("/resultado"):
            self.confirmaciones.append((p.split("/")[4], json.loads(req.content)))
            return _ok({"estado": "ok"})
        return httpx.Response(404, json={"error": {"code": "NOT_FOUND", "message": p}})


def _v(id_, pregunta, *opciones):
    return {"id": id_, "pregunta": pregunta,
            "opciones": [{"id": o[0], "texto": o[1], "resultado": o[2], "consejo": o[3] if len(o) > 3 else None}
                         for o in opciones]}


def _residuo(codigo, nombre, emoji, acepta, servicio, menu, sinonimos, verificaciones=(), **extra):
    return {"id": f"r-{codigo.lower()}", "codigo": codigo, "nombre": nombre, "emoji": emoji, "acepta": acepta,
            "tipo_servicio_id": servicio, "en_menu": menu, "orden": len(sinonimos), "sinonimos": sinonimos,
            "verificaciones": list(verificaciones), "preparacion": extra.get("preparacion", "Limpio y seco."),
            "evitar": extra.get("evitar"), "alternativa": extra.get("alternativa")}


RESIDUOS = [
    _residuo("CARTON", "Cartón", "📦", "si", "s-rec", True, ["caja", "carton"],
             [_v("seco", "¿Tu cartón está limpio y seco?", ("si", "Sí, está listo", "listo"),
                 ("mojado", "Está mojado", "preparar", "Déjalo secar bajo techo."),
                 ("nose", "No estoy seguro", "revision", "Lo marco para que lo revisen."))],
             evitar="Cartón mojado o con grasa."),
    _residuo("PET", "Botellas plásticas", "🧴", "si", "s-rec", True, ["botella", "pet"],
             [_v("vacias", "¿Están vacías?", ("si", "Sí, vacías", "listo"), ("no", "Todavía no", "preparar", "Vacíalas.")),
              _v("quimicos", "¿Alguna tuvo químicos?", ("no", "No, ninguna", "listo"), ("si", "Sí, alguna", "listo", "Saca esas; las demás sí."))]),
    _residuo("VIDRIO", "Vidrio (botellas)", "🍾", "si", "s-rec", True, ["botella de vidrio", "frasco"]),
    _residuo("FRUVER", "Frutas y verduras", "🍌", "si", "s-org", True, ["cascara", "fruta"]),
    _residuo("TETRAPAK", "Cajas de leche y jugo", "🧃", "revision", "s-rec", False, ["caja de leche"],
             preparacion="Vacías y aplastadas."),
    _residuo("PILAS", "Pilas y baterías", "🔋", "no", None, False, ["pila", "bateria"], preparacion=None,
             evitar="Tienen metales pesados.", alternativa="Llévalas a un punto posconsumo."),
]


def _ok(data, status=200) -> httpx.Response:
    return httpx.Response(status, json={"data": data})


@pytest.fixture
def entorno():
    api = APIFalsa()
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(api))
    with TestClient(crear_app(ajustes(), cliente, procesar_en_linea=True)) as c:
        yield c, api


def enviar(c: TestClient, texto=None, boton=None, lista=None, de=CEL, wamid=None) -> list[dict]:
    datos = payload(de, texto, boton, lista, "Carmen")
    if wamid:
        datos["entry"][0]["changes"][0]["value"]["messages"][0]["id"] = wamid
    cuerpo = json.dumps(datos).encode()
    firma = "sha256=" + hmac.new(SECRETO.encode(), cuerpo, hashlib.sha256).hexdigest()
    antes = len(c.get("/dev/mensajes", params={"para": de}).json()["data"])
    r = c.post("/webhook", content=cuerpo, headers={"X-Hub-Signature-256": firma, "Content-Type": "application/json"})
    assert r.status_code == 200, r.text
    return c.get("/dev/mensajes", params={"para": de}).json()["data"][antes:]


def _texto(msj: dict) -> str:
    return msj["text"]["body"] if msj["type"] == "text" else msj["interactive"]["body"]["text"]


def test_verificacion_del_webhook(entorno):
    c, _ = entorno
    ok = c.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verificar", "hub.challenge": "123"})
    assert ok.status_code == 200 and ok.text == "123"
    malo = c.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "otro", "hub.challenge": "123"})
    assert malo.status_code == 403


def test_firma_invalida_se_descarta(entorno):
    c, api = entorno
    cuerpo = json.dumps(payload(CEL, "hola", None, None, "x")).encode()
    r = c.post("/webhook", content=cuerpo, headers={"X-Hub-Signature-256": "sha256=falsa"})
    assert r.status_code == 401 and api.llamadas == []


def test_registro_completo_y_menu(entorno):
    c, api = entorno
    r = enviar(c, "hola")
    assert "Soy Brisa" in _texto(r[0])

    r = enviar(c, "carmen")
    lista = r[0]["interactive"]
    assert lista["type"] == "list" and "Carmen" in lista["body"]["text"]
    assert [row["id"] for row in lista["action"]["sections"][0]["rows"]] == ["t1", "t3"]

    r = enviar(c, lista="t3")
    assert "apartamento" in _texto(r[0])
    r = enviar(c, "999")
    assert "No encontré" in _texto(r[0])
    r = enviar(c, "Apto 402")
    assert "Torre 3 · Apto 402" in _texto(r[0]) and r[0]["interactive"]["type"] == "button"

    r = enviar(c, boton="VER_MAS")
    assert "Ley 1581" in _texto(r[0]) and r[1]["type"] == "interactive"

    r = enviar(c, boton="ACEPTO")
    assert api.registrados == {CEL: "Carmen"}
    assert "Ya quedaste registrado" in _texto(r[0])
    filas = [row["id"] for row in r[1]["interactive"]["action"]["sections"][0]["rows"]]
    assert filas == ["M_PEDIR", "M_DUDA", "M_ESTADO", "M_PUNTOS", "M_LIGA"]


@pytest.mark.parametrize("escrito", ["402", "Apto 402", "apartamento #402", "4-02", "apto. 402"])
def test_referencia_de_apartamento(escrito):
    from app.conversacion import referencia_apto

    assert referencia_apto(escrito) == "402"


def test_rechazar_consentimiento_no_registra(entorno):
    c, api = entorno
    for paso in ({"texto": "hola"}, {"texto": "Ana"}, {"lista": "t3"}, {"texto": "402"}):
        enviar(c, **paso)
    r = enviar(c, boton="NO_ACEPTO")
    assert "Sin tu autorización" in _texto(r[0]) and not api.registrados


def test_puntos_y_menu_por_defecto(entorno):
    c, api = entorno
    api.registrados[CEL] = "Carmen"
    assert "Tienes 25 puntos" in _texto(enviar(c, "PUNTOS")[0])
    r = enviar(c, "hola")
    assert r[0]["interactive"]["type"] == "list" and "Carmen" in _texto(r[0])


def _graph(respuestas: list[httpx.Response], enviados: list[dict]):
    def handler(req: httpx.Request) -> httpx.Response:
        enviados.append(json.loads(req.content))
        return respuestas.pop(0)
    return handler


def _aviso(tipo="asignacion") -> dict:
    return {"id": "a1", "tipo": tipo, "destino": {"celular": "+" + CEL, "nombre": "Carmen"},
            "datos": {"texto_sugerido": "🚲 Rosa pasa hoy", "recolector_nombre": "Rosa", "franja_texto": "hoy",
                      "codigo_pasaporte": "BR-00001"}}


@pytest.mark.parametrize("plantillas", [False, True])
def test_aviso_fuera_de_ventana(plantillas):
    api = APIFalsa()
    api.avisos = [_aviso()]
    enviados: list[dict] = []
    fuera = httpx.Response(400, json={"error": {"code": 131047, "message": "Re-engagement message"}})
    ok = httpx.Response(200, json={"messages": [{"id": "wamid.plantilla"}]})
    graph = _graph([fuera, ok], enviados)

    def ruteo(req: httpx.Request) -> httpx.Response:
        return graph(req) if req.url.host == "graph.facebook.com" else api(req)

    s = ajustes(whatsapp_dry_run=False, whatsapp_token="t", whatsapp_phone_number_id="123",
                whatsapp_usar_plantillas=plantillas)

    async def correr():
        async with httpx.AsyncClient(transport=httpx.MockTransport(ruteo)) as cli:
            return await avisos.procesar_lote(WhatsApp(s, cli), Brota(s, cli), s)

    assert asyncio.run(correr()) == 1
    assert enviados[0]["to"] == CEL and enviados[0]["text"]["body"] == "🚲 Rosa pasa hoy"
    aviso_id, resultado = api.confirmaciones[0]
    if plantillas:
        assert enviados[1]["template"]["name"] == "brota_asignacion"
        params = [p["text"] for p in enviados[1]["template"]["components"][0]["parameters"]]
        assert params == ["Rosa", "hoy", "BR-00001"]
        assert resultado == {"estado": "enviado", "reintentar": True, "id_externo": "wamid.plantilla"}
    else:
        assert len(enviados) == 1
        assert resultado["estado"] == "fallido" and resultado["reintentar"] is False


def test_saludo_no_se_toma_como_nombre(entorno):
    c, _ = entorno
    enviar(c, "hola")
    r = enviar(c, "Hola!")
    assert "tu nombre" in _texto(r[0])
    r = enviar(c, "Laura")
    assert r[0]["interactive"]["type"] == "list"
