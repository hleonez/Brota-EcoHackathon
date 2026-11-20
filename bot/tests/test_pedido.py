"""Pedido guiado: Brisa enseña con las fichas, revisa cada material y solo envía tras el resumen."""

from __future__ import annotations

import json

from app.catalogo import buscar
from tests.test_bot import CEL, RESIDUOS, _texto, entorno, enviar  # noqa: F401 (fixture)


def _botones(msj: dict) -> list[str]:
    return [b["reply"]["id"] for b in msj["interactive"]["action"]["buttons"]]


def _filas(msj: dict) -> list[str]:
    return [r["id"] for r in msj["interactive"]["action"]["sections"][0]["rows"]]


def _registrada(entorno):
    c, api = entorno
    api.registrados[CEL] = "Carmen"
    return c, api


def test_reconoce_materiales_en_texto_libre():
    codigos = lambda t: [f["codigo"] for f in buscar(t, RESIDUOS)]  # noqa: E731
    assert codigos("Tengo unas CAJAS, 3 botellas de vidrio y cáscaras") == ["CARTON", "VIDRIO", "FRUVER"]
    assert codigos("una caja de leche") == ["TETRAPAK"]  # la frase más larga gana a «caja»
    assert codigos("botellas") == ["PET"]
    assert codigos("nada que ver") == []


def test_pedido_guiado_hasta_enviar(entorno):
    c, api = _registrada(entorno)
    lista = enviar(c, lista="M_PEDIR")[0]
    assert _filas(lista)[:2] == ["P_ADD:CARTON", "P_ADD:PET"] and _filas(lista)[-1] == "P_OTRO"

    r = enviar(c, "tengo cajas y botellas")
    assert "📦 Cartón y 🧴 Botellas plásticas" in _texto(r[0]) and _botones(r[0]) == ["P_SI_TEXTO", "P_NO_TEXTO"]

    r = enviar(c, boton="P_SI_TEXTO")
    assert "Limpio y seco." in _texto(r[0]) and "¿Tu cartón está limpio y seco?" in _texto(r[0])
    assert _botones(r[0]) == ["P_V:CARTON:seco:si", "P_V:CARTON:seco:mojado", "P_V:CARTON:seco:nose"]

    r = enviar(c, boton="P_V:CARTON:seco:mojado")  # el cartón mojado queda por fuera, con el consejo
    assert "Déjalo secar bajo techo." in _texto(r[0]) and "¿Están vacías?" in _texto(r[1])

    r = enviar(c, "sí")  # en medio de un chequeo se pide tocar una opción
    assert "Toca una de las opciones" in _texto(r[0]) and "¿Están vacías?" in _texto(r[1])

    enviar(c, boton="P_V:PET:vacias:si")
    r = enviar(c, boton="P_V:PET:quimicos:no")
    assert "Botellas plásticas: listo" in _texto(r[0]) and _botones(r[1]) == ["P_MAS", "P_LISTO"]

    r = enviar(c, lista="P_ADD:TETRAPAK")  # «revisión»: entra marcado para que el equipo lo confirme
    assert "el equipo confirme" in _texto(r[0])

    r = enviar(c, boton="P_LISTO")
    resumen = _texto(r[0])
    assert "🧴 Botellas plásticas ✅" in resumen and "🧃 Cajas de leche y jugo 🔎" in resumen
    assert "Queda por fuera: 📦 Cartón" in resumen
    assert _botones(r[0]) == ["P_ENVIAR", "P_CORREGIR", "P_CANCELAR"]
    assert api.cuerpos_solicitud == []  # nada se crea antes de confirmar

    r = enviar(c, boton="P_ENVIAR", wamid="wamid.enviar")
    assert "BR-00001" in _texto(r[0])
    assert api.cuerpos_solicitud == [{"residuos": [
        {"residuo_id": "r-pet", "estado": "listo", "respuestas": {"vacias": "si", "quimicos": "no"}, "fuente": "texto"},
        {"residuo_id": "r-tetrapak", "estado": "revision", "respuestas": {}, "fuente": "lista"},
    ]}]
    post = next(x for x in api.llamadas if x.url.path == "/v1/solicitudes" and x.method == "POST")
    assert post.headers["Idempotency-Key"] == "wamid.enviar"

    r = enviar(c, boton="P_ENVIAR")  # un botón viejo no reenvía nada
    assert "No tengo un pedido pendiente" in _texto(r[0]) and len(api.cuerpos_solicitud) == 1


def test_lo_que_no_se_recibe_se_explica_y_no_se_pide(entorno):
    c, api = _registrada(entorno)
    enviar(c, lista="M_PEDIR")
    enviar(c, "unas pilas")
    r = enviar(c, boton="P_SI_TEXTO")
    assert "no va en la ruta" in _texto(r[0]) and "punto posconsumo" in _texto(r[0])
    r = enviar(c, boton="P_LISTO")
    assert "no quedó ningún material listo" in _texto(r[0]) and "Queda por fuera: 🔋 Pilas y baterías" in _texto(r[0])
    r = enviar(c, "cancelar")
    assert "no envié nada" in _texto(r[0]) and api.cuerpos_solicitud == []


def test_corregir_y_volver_a_revisar(entorno):
    c, _ = _registrada(entorno)
    enviar(c, lista="P_ADD:CARTON")
    enviar(c, boton="P_V:CARTON:seco:mojado")
    enviar(c, lista="P_ADD:FRUVER")
    r = enviar(c, boton="P_LISTO")
    assert "Queda por fuera: 📦 Cartón" in _texto(r[0])
    r = enviar(c, boton="P_CORREGIR")
    assert _filas(r[0]) == ["P_REVISAR:CARTON", "P_QUITAR:FRUVER", "P_MAS", "P_REINICIAR"]
    r = enviar(c, lista="P_REVISAR:CARTON")  # «ya lo sequé»: se vuelve a preguntar
    assert "¿Tu cartón está limpio y seco?" in _texto(r[0])
    enviar(c, boton="P_V:CARTON:seco:si")
    r = enviar(c, boton="P_LISTO")
    assert "📦 Cartón ✅" in _texto(r[0]) and "Queda por fuera" not in _texto(r[0])


def test_dudas_con_fichas(entorno):
    c, _ = _registrada(entorno)
    assert "qué material tienes" in _texto(enviar(c, lista="M_DUDA")[0])
    r = enviar(c, "¿el cartón mojado sirve?")
    assert "se recibe en la ruta" in _texto(r[0]) and "Evita: Cartón mojado o con grasa." in _texto(r[0])
    assert _botones(r[1]) == ["P_ADDS:CARTON", "M_DUDA", "M_MENU"]

    enviar(c, lista="M_DUDA")
    assert "no está en mi lista" in _texto(enviar(c, "icopor")[0])

    # Sin tocar «Tengo una duda»: si menciona un material, primero se le enseña.
    r = enviar(c, "qué hago con unas pilas")
    assert "no va en la ruta" in _texto(r[0]) and _botones(r[1])[0] == "M_PEDIR"

    r = enviar(c, boton="P_ADDS:CARTON")  # pedir desde la duda arranca el pedido con ese material
    assert "¿Tu cartón está limpio y seco?" in _texto(r[0])


def test_el_menu_conserva_el_pedido(entorno):
    c, _ = _registrada(entorno)
    enviar(c, lista="P_ADD:CARTON")
    r = enviar(c, "hola")
    assert _filas(r[0])[0] == "P_SEGUIR"
    r = enviar(c, lista="P_SEGUIR")
    assert "¿Tu cartón está limpio y seco?" in _texto(r[0])


def test_solicitud_abierta(entorno):
    c, api = _registrada(entorno)
    for _ in range(2):
        enviar(c, lista="P_ADD:FRUVER")
        enviar(c, boton="P_LISTO")
        r = enviar(c, boton="P_ENVIAR")
    assert "Ya tienes una solicitud en camino (BR-00001)" in _texto(r[0])
    assert [json.dumps(b) for b in api.cuerpos_solicitud][0] == json.dumps(
        {"residuos": [{"residuo_id": "r-fruver", "estado": "listo", "respuestas": {}, "fuente": "lista"}]}
    )


def test_listo_con_algo_que_separar(entorno):
    c, _ = _registrada(entorno)
    enviar(c, lista="P_ADD:PET")
    enviar(c, boton="P_V:PET:vacias:si")
    r = enviar(c, boton="P_V:PET:quimicos:si")  # alguna tuvo químicos: se separa y las demás sí van
    assert _texto(r[0]) == "💡 Saca esas; las demás sí." and "Botellas plásticas: listo" in _texto(r[1])
    assert "🧴 Botellas plásticas ✅" in _texto(enviar(c, boton="P_LISTO")[0])
