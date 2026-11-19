"""Soporte: reportar un problema, hablar con alguien y cancelar una solicitud enviada."""

from __future__ import annotations

from app.soporte import codigo_mencionado
from tests.test_bot import CEL, _texto, entorno, enviar  # noqa: F401 (fixture)


def _botones(msj: dict) -> list[str]:
    return [b["reply"]["id"] for b in msj["interactive"]["action"]["buttons"]]


def _solicitud(sid="s9", codigo="BR-00009"):
    return {"id": sid, "codigo_pasaporte": codigo,
            "ordenes": [{"gremio_nombre": "Asorescatar · Recicladores", "estado": "asignada"}]}


def test_codigo_de_solicitud_en_texto_libre():
    assert codigo_mencionado("me dejaron plantada la br 18") == "BR-00018"
    assert codigo_mencionado("BR-00007 no pasó nadie") == "BR-00007"
    assert codigo_mencionado("nadie vino") is None


def test_reportar_un_problema_desde_el_menu(entorno):
    c, api = entorno
    api.registrados[CEL] = "Carmen"
    assert "Cuéntame qué pasó" in _texto(enviar(c, lista="M_QUEJA")[0])
    r = enviar(c, "Rosa no pasó por la BR-00009 y dejé las cajas afuera", wamid="wamid.queja")
    assert "lo dejé registrado (CA-00001)" in _texto(r[0])
    assert api.casos == [{"tipo": "queja", "texto": "Rosa no pasó por la BR-00009 y dejé las cajas afuera",
                          "codigo_pasaporte": "BR-00009", "clave": "wamid.queja"}]
    # El siguiente mensaje ya no es parte del reporte.
    enviar(c, "hola")
    assert len(api.casos) == 1


def test_hablar_con_alguien(entorno):
    c, api = entorno
    api.registrados[CEL] = "Carmen"
    assert "una persona del equipo te responde" in _texto(enviar(c, lista="M_PERSONA")[0])
    enviar(c, "¿Pueden recoger un sofá viejo?")
    assert api.casos[0]["tipo"] == "ayuda" and "codigo_pasaporte" not in api.casos[0]


def test_cancelar_una_solicitud_con_confirmacion(entorno):
    c, api = entorno
    api.registrados[CEL] = "Carmen"
    api.solicitudes = [_solicitud()]
    r = enviar(c, "cancelar")
    assert "¿Cancelo tu solicitud BR-00009? (Asorescatar: asignada)" in _texto(r[0])
    assert _botones(r[0]) == ["S_CANCELAR_SI:s9", "M_MENU"]
    r = enviar(c, boton="S_CANCELAR_SI:s9")
    assert "cancelé tu solicitud BR-00009" in _texto(r[0]) and api.solicitudes == []
    r = enviar(c, boton="S_CANCELAR_SI:s9")  # botón viejo
    assert "ya no se puede cancelar" in _texto(r[0])


def test_cancelar_elige_entre_varias(entorno):
    c, api = entorno
    api.registrados[CEL] = "Carmen"
    api.solicitudes = [_solicitud(), _solicitud("s8", "BR-00008")]
    r = enviar(c, "cancelar")
    filas = [f["id"] for f in r[0]["interactive"]["action"]["sections"][0]["rows"]]
    assert filas == ["S_CANCELAR:s9", "S_CANCELAR:s8"]
    r = enviar(c, lista="S_CANCELAR:s8")
    assert _botones(r[0]) == ["S_CANCELAR_SI:s8", "M_MENU"]


def test_cancelar_con_un_pedido_a_medias_cancela_el_borrador(entorno):
    c, api = entorno
    api.registrados[CEL] = "Carmen"
    api.solicitudes = [_solicitud()]
    enviar(c, lista="P_ADD:CARTON")
    assert "no envié nada" in _texto(enviar(c, "cancelar")[0]) and len(api.solicitudes) == 1
