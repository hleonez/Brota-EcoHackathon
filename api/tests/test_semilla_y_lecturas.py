"""Cuentas y contactos de la semilla, lecturas públicas y el rechazo de una solicitud sin preferencia."""

from tests.conftest import bot

TITULOS_SEMILLA = {
    "Cómo entregar el cartón",
    "Separa bien tus reciclables",
    "Qué va a la huerta",
    "Consejo de Brisa",
    "Horarios y rutas del piloto",
}
NEGOCIO = "573100000201"
HOGAR = "573100000101"
SIN_PILOTO = "573100000102"


def test_cuentas_demo_traen_al_trabajador(client, operador, catalogo):
    esperados = {
        "huertero-demo": ("huertero", "gremios:ECORAZON", "Huertero demo 1", "/v1/huerteros"),
        "reciclador-demo": ("reciclador", "gremios:ASORESCATAR", "Rosa (demo)", "/v1/recicladores"),
    }
    for usuario, (rol, gremio, nombre, ruta) in esperados.items():
        me = client.get("/v1/me", headers=operador(usuario, False)).json()["data"]
        lista = client.get(ruta, headers=operador("admin", False), params={"limit": 100}).json()["data"]
        trabajador = next(t for t in lista if t["nombre"] == nombre and t["gremio_id"] == catalogo[gremio])
        assert me["trabajador_id"] == trabajador["id"]
        assert me["permisos"] == [{"rol": rol, "gremio_id": catalogo[gremio]}]


def test_habilitacion_de_los_celulares_de_la_semilla(client):
    def me(celular: str) -> dict:
        r = client.get("/v1/me", headers=bot(celular, False))
        assert r.status_code == 200, r.text
        return r.json()["data"]

    for celular in (NEGOCIO, HOGAR):
        datos = me(celular)
        assert datos["registrado"] is True
        assert datos["habilitaciones"]
        assert all(h["vigente_hasta"] is None for h in datos["habilitaciones"])

    habilitado = me(HOGAR)
    tercero = me(SIN_PILOTO)
    assert tercero["registrado"] is True
    assert tercero["habilitaciones"] == []
    assert tercero["unidades"][0]["id"] == habilitado["unidades"][0]["id"]


def test_contenidos_sin_sesion_ocultan_borrador_y_retirado(client, operador):
    borrador = client.post(
        "/v1/contenidos-educativos",
        headers=operador("admin"),
        json={"titulo": "Borrador que no se publica", "tipo": "texto", "texto": "Aún no.", "publicado": False},
    )
    assert borrador.status_code == 201, borrador.text
    creado = client.post(
        "/v1/contenidos-educativos",
        headers=operador("admin"),
        json={"titulo": "Contenido retirado en la prueba", "tipo": "texto", "texto": "Se retira.", "publicado": True},
    )
    assert creado.status_code == 201, creado.text
    retirado = client.patch(
        f"/v1/contenidos-educativos/{creado.json()['data']['id']}",
        headers=operador("admin"),
        json={"version_esperada": 1, "activo": False},
    )
    assert retirado.status_code == 200, retirado.text
    vencido = client.post(
        "/v1/contenidos-educativos",
        headers=operador("admin"),
        json={"titulo": "Contenido fuera de vigencia", "tipo": "texto", "texto": "Ya no aplica.", "publicado": True},
    )
    assert vencido.status_code == 201, vencido.text
    fuera = client.patch(
        f"/v1/contenidos-educativos/{vencido.json()['data']['id']}",
        headers=operador("admin"),
        json={
            "version_esperada": 1,
            "vigente_desde": "2020-01-01T00:00:00Z",
            "vigente_hasta": "2020-06-01T00:00:00Z",
        },
    )
    assert fuera.status_code == 200, fuera.text

    ocultos = {"Borrador que no se publica", "Contenido retirado en la prueba", "Contenido fuera de vigencia"}
    sin_sesion = client.get("/v1/contenidos-educativos", params={"limit": 100})
    con_sesion = client.get("/v1/contenidos-educativos", params={"limit": 100}, headers=operador("admin", False))
    assert sin_sesion.status_code == 200, sin_sesion.text
    assert [c["id"] for c in sin_sesion.json()["data"]] == [c["id"] for c in con_sesion.json()["data"]]
    titulos = {c["titulo"] for c in sin_sesion.json()["data"]}
    assert TITULOS_SEMILLA <= titulos
    assert ocultos.isdisjoint(titulos)

    invalido = client.get("/v1/contenidos-educativos", headers={"Authorization": "Bearer no-es-valido"})
    assert invalido.status_code == 401


def test_participantes_solo_admin(client, operador):
    r = client.get("/v1/participantes", headers=operador("admin", False), params={"limit": 100})
    assert r.status_code == 200, r.text
    por_nombre = {p["nombre"]: p for p in r.json()["data"]}
    residente = por_nombre["Residente Torre 1 apto 101"]
    otro = por_nombre["Otro residente Torre 1 apto 101"]
    negocio = por_nombre["Contacto Asadero El Corredor (demo)"]
    assert residente["id"] and residente["unidades"][0]["tipo"] == "hogar"
    assert residente["unidades"][0]["etiqueta"] == "Torre 1 · Apto 101"
    assert otro["unidades"][0]["id"] == residente["unidades"][0]["id"]
    assert negocio["unidades"][0]["tipo"] == "negocio"
    assert negocio["unidades"][0]["etiqueta"] == "Asadero El Corredor (demo) · Corredor comercial"
    for usuario in ("coord-huerta", "fundacion"):
        denegado = client.get("/v1/participantes", headers=operador(usuario, False))
        assert denegado.status_code == 403, usuario


def test_solicitud_sin_preferencia_responde_422(client, catalogo):
    r = client.post(
        "/v1/solicitudes",
        json={"tipo_servicio_ids": [catalogo["tipos_servicio:RECICLABLES"]]},
        headers=bot(HOGAR),
    )
    assert r.status_code == 422, r.text
    error = r.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert any("preferencia" in mensaje.lower() for mensaje in error["fields"].values())
