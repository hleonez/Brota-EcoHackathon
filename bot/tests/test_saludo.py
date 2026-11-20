"""El saludo de Brisa: cálido al saludar, corto cuando ya están conversando."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import textos as T
from app.conversacion import _saludo_del_momento
from tests.test_bot import CEL, _texto, entorno, enviar  # noqa: F401 (fixture)

BOGOTA = timezone(timedelta(hours=-5))


def test_saludo_segun_la_hora_en_bogota():
    assert _saludo_del_momento(datetime(2026, 11, 20, 7, 0, tzinfo=BOGOTA)) == "Buenos días"
    assert _saludo_del_momento(datetime(2026, 11, 20, 14, 0, tzinfo=BOGOTA)) == "Buenas tardes"
    assert _saludo_del_momento(datetime(2026, 11, 20, 21, 0, tzinfo=BOGOTA)) == "Buenas noches"


def test_al_saludar_brisa_se_presenta_con_el_primer_nombre(entorno):
    c, api = entorno
    api.registrados[CEL] = "Jeremy Fontalvo"
    msj = enviar(c, "Hola!")[0]
    cuerpo = _texto(msj)
    assert "Soy Brisa, tu asistente de reciclaje de Brota" in cuerpo
    assert ", Jeremy! 👋" in cuerpo and "Fontalvo" not in cuerpo
    assert any(f in cuerpo for f in T.FRASES_SALUDO) and cuerpo.endswith("¿En qué te puedo ayudar hoy?")
    assert msj["interactive"]["footer"]["text"] == T.MENU_LISTA_PIE


def test_volver_al_menu_no_repite_la_presentacion(entorno):
    c, api = entorno
    api.registrados[CEL] = "Jeremy Fontalvo"
    cuerpo = _texto(enviar(c, boton="M_MENU")[0])
    assert cuerpo == "¿En qué más te puedo ayudar, Jeremy? 🌱"
