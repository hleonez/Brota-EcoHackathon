"""Lecturas de administración que no abren el directorio ni la guía pública."""

import uuid


def _paginas(client, ruta, headers=None, params=None):
    filas = []
    offset = 0
    while True:
        consulta = {"limit": 100, "offset": offset, **(params or {})}
        respuesta = client.get(ruta, headers=headers, params=consulta)
        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()
        filas.extend(cuerpo["data"])
        if not cuerpo["pagination"]["has_more"]:
            return filas
        offset += len(cuerpo["data"])


def test_unidades_de_gestion_son_solo_de_admin(client, operador):
    unidades = _paginas(client, "/v1/unidades/gestion", operador("admin", False))
    assert any(u["tipo"] == "hogar" and u["etiqueta"] for u in unidades)
    assert any(u["tipo"] == "negocio" and u["etiqueta"] for u in unidades)
    negocios = _paginas(client, "/v1/unidades/gestion", operador("admin", False), {"tipo": "negocio"})
    assert negocios and all(u["tipo"] == "negocio" for u in negocios)

    assert client.get("/v1/unidades", headers=operador("admin", False)).status_code == 403
    for usuario in ("coord-reciclaje", "fundacion", "reciclador-demo"):
        assert client.get("/v1/unidades/gestion", headers=operador(usuario, False)).status_code == 403
    assert client.get("/v1/unidades/gestion").status_code == 401


def test_gestion_de_contenidos_incluye_borrador_y_retirado(client, operador):
    marca = uuid.uuid4().hex[:8]
    borrador = client.post(
        "/v1/contenidos-educativos",
        headers=operador("admin"),
        json={
            "titulo": f"Borrador {marca}",
            "tipo": "texto",
            "texto": "Aún no se publica.",
            "publicado": False,
            "tema": "servicio",
        },
    )
    assert borrador.status_code == 201, borrador.text
    publicado = client.post(
        "/v1/contenidos-educativos",
        headers=operador("admin"),
        json={
            "titulo": f"Para retirar {marca}",
            "tipo": "texto",
            "texto": "Se retira de la guía.",
            "publicado": True,
            "tema": "servicio",
        },
    )
    assert publicado.status_code == 201, publicado.text
    retirado = client.patch(
        f"/v1/contenidos-educativos/{publicado.json()['data']['id']}",
        headers=operador("admin"),
        json={"version_esperada": 1, "activo": False},
    )
    assert retirado.status_code == 200, retirado.text

    publicos = {c["titulo"] for c in _paginas(client, "/v1/contenidos-educativos")}
    assert f"Borrador {marca}" not in publicos
    assert f"Para retirar {marca}" not in publicos
    con_admin = {c["titulo"] for c in _paginas(client, "/v1/contenidos-educativos", operador("admin", False))}
    assert f"Borrador {marca}" not in con_admin

    gestion = {c["titulo"]: c for c in _paginas(client, "/v1/contenidos-educativos/gestion", operador("admin", False))}
    assert gestion[f"Borrador {marca}"]["publicado"] is False
    assert gestion[f"Borrador {marca}"]["activo"] is True
    assert gestion[f"Para retirar {marca}"]["activo"] is False
    assert gestion[f"Para retirar {marca}"]["publicado"] is False

    servicio = _paginas(
        client, "/v1/contenidos-educativos/gestion", operador("admin", False), {"tema": "servicio"},
    )
    assert all(c["tema"] == "servicio" for c in servicio)
    assert any(c["titulo"] == f"Borrador {marca}" for c in servicio)
    assert client.get("/v1/contenidos-educativos/gestion", headers=operador("coord-huerta", False)).status_code == 403
    assert client.get("/v1/contenidos-educativos/gestion", headers=operador("fundacion", False)).status_code == 403
    assert client.get("/v1/contenidos-educativos/gestion").status_code == 401


def test_materiales_de_admin_incluyen_inactivos_y_version(client, operador, catalogo):
    codigo = "ADM" + uuid.uuid4().hex[:8].upper()
    creado = client.post(
        "/v1/materiales",
        headers=operador("admin"),
        json={"codigo": codigo, "nombre": f"Material {codigo}", "gremio_id": catalogo["gremios:ASORESCATAR"]},
    )
    assert creado.status_code == 201, creado.text
    material_id = creado.json()["data"]["id"]
    baja = client.patch(
        f"/v1/materiales/{material_id}",
        headers=operador("admin"),
        json={"version_esperada": creado.json()["data"]["version"], "activo": False},
    )
    assert baja.status_code == 200, baja.text

    materiales = _paginas(client, "/v1/materiales", operador("admin", False))
    encontrado = next(m for m in materiales if m["codigo"] == codigo)
    assert encontrado["activo"] is False
    assert encontrado["version"] == baja.json()["data"]["version"]

    renombre = client.patch(
        f"/v1/materiales/{material_id}",
        headers=operador("admin"),
        json={"version_esperada": encontrado["version"], "nombre": f"Material editado {codigo}"},
    )
    assert renombre.status_code == 200, renombre.text
    assert renombre.json()["data"]["nombre"] == f"Material editado {codigo}"
    assert renombre.json()["data"]["activo"] is False

    for usuario in ("coord-reciclaje", "fundacion", "reciclador-demo"):
        assert client.get("/v1/materiales", headers=operador(usuario, False)).status_code == 403
    assert client.get("/v1/materiales").status_code == 401


def test_unidad_se_desactiva_y_reactiva_sin_borrarse(client, operador):
    referencia = "Neg " + uuid.uuid4().hex[:6]
    creada = client.post(
        "/v1/unidades",
        headers=operador("admin"),
        json={"tipo": "negocio", "referencia_local": referencia, "direccion_referencia": "Corredor"},
    )
    assert creada.status_code == 201, creada.text
    unidad_id = creada.json()["data"]["id"]
    assert creada.json()["data"]["activo"] is True

    baja = client.patch(f"/v1/unidades/{unidad_id}", headers=operador("admin"), json={"activo": False})
    assert baja.status_code == 200, baja.text
    assert baja.json()["data"]["activo"] is False

    activas = _paginas(client, "/v1/unidades/gestion", operador("admin", False))
    assert all(u["id"] != unidad_id for u in activas)
    todas = _paginas(client, "/v1/unidades/gestion", operador("admin", False), {"incluir_inactivas": "true"})
    assert next(u for u in todas if u["id"] == unidad_id)["activo"] is False

    alta = client.patch(f"/v1/unidades/{unidad_id}", headers=operador("admin"), json={"activo": True})
    assert alta.status_code == 200, alta.text
    assert any(u["id"] == unidad_id for u in _paginas(client, "/v1/unidades/gestion", operador("admin", False)))

    for usuario in ("coord-reciclaje", "fundacion", "reciclador-demo"):
        r = client.patch(f"/v1/unidades/{unidad_id}", headers=operador(usuario), json={"activo": False})
        assert r.status_code == 403


def test_motivo_se_desactiva_sale_del_catalogo_y_se_reactiva(client, operador, catalogo):
    codigo = "MOT" + uuid.uuid4().hex[:8].upper()
    creado = client.post(
        "/v1/motivos-rechazo",
        headers=operador("admin"),
        json={"codigo": codigo, "nombre": f"Motivo {codigo}", "gremio_id": catalogo["gremios:ASORESCATAR"]},
    )
    assert creado.status_code == 201, creado.text
    motivo_id = creado.json()["data"]["id"]

    baja = client.patch(f"/v1/motivos-rechazo/{motivo_id}", headers=operador("admin"), json={"activo": False})
    assert baja.status_code == 200, baja.text
    assert baja.json()["data"]["activo"] is False
    publicos = client.get("/v1/catalogos", headers=operador("admin", False)).json()["data"]["motivos_rechazo"]
    assert all(m["id"] != motivo_id for m in publicos)
    gestion = _paginas(client, "/v1/motivos-rechazo", operador("admin", False))
    assert next(m for m in gestion if m["id"] == motivo_id)["activo"] is False

    alta = client.patch(f"/v1/motivos-rechazo/{motivo_id}", headers=operador("admin"), json={"activo": True})
    assert alta.status_code == 200, alta.text

    for usuario in ("coord-reciclaje", "fundacion"):
        assert client.get("/v1/motivos-rechazo", headers=operador(usuario, False)).status_code == 403
        r = client.patch(f"/v1/motivos-rechazo/{motivo_id}", headers=operador(usuario), json={"activo": False})
        assert r.status_code == 403


def test_admin_no_puede_desactivar_su_propia_cuenta(client, operador):
    cuentas = _paginas(client, "/v1/cuentas-operadoras", operador("admin", False))
    propia = next(c for c in cuentas if c["usuario"] == "admin")
    r = client.patch(
        f"/v1/cuentas-operadoras/{propia['id']}",
        headers=operador("admin"),
        json={"version_esperada": propia["version"], "activo": False},
    )
    assert r.status_code == 409, r.text
    despues = next(c for c in _paginas(client, "/v1/cuentas-operadoras", operador("admin", False)) if c["id"] == propia["id"])
    assert despues["activo"] is True and despues["version"] == propia["version"]
