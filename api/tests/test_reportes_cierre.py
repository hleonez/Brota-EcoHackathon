"""Hoja de ruta (PDF operativo) y Excel institucional.

No usa la base brota: el fixture de la suite apunta a brota_test.
"""

from __future__ import annotations

import uuid
import zipfile
from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook

from tests.conftest import bot, vaciar_avisos
from tests.test_certificado_verde import _texto_pdf

DIA = "2031-05-20"
OTRO_DIA = "2031-08-02"
DIA_VACIO = "1999-06-15"
DESDE = "2024-02-14T00:00:00-05:00"
HASTA = "2024-02-15T00:00:00-05:00"
CUANDO = "2024-02-14T11:00:00-05:00"
TEL_RESIDENTE = "573008880011"
TEL_RECOLECTOR = "3007001122"
TEL_EXCEL = "573009991199"
NOMBRE_EXCEL = "Lorena Cierre Privada"
REF_EXCEL = "Cierre8841"


def _negocio(client, operador, celular: str, nombre: str, referencia: str, direccion: str) -> str:
    unidad = client.post(
        "/v1/unidades",
        headers=operador("admin"),
        json={"tipo": "negocio", "referencia_local": referencia, "direccion_referencia": direccion},
    )
    assert unidad.status_code == 201, unidad.text
    unidad_id = unidad.json()["data"]["id"]
    registro = client.post(
        "/v1/registros",
        headers=bot(celular),
        json={
            "nombre": nombre,
            "unidad_id": unidad_id,
            "consentimiento": {"version_politica": "2026-11", "decision": "aceptado"},
        },
    )
    assert registro.status_code == 201, registro.text
    alta = client.post(
        "/v1/piloto/habilitaciones",
        headers=operador("admin"),
        json={"participante_id": registro.json()["data"]["participante_id"], "unidad_id": unidad_id},
    )
    assert alta.status_code == 201, alta.text
    return unidad_id


def _pedir_servicio(client, celular: str, unidad_id: str, servicio_id: str) -> str:
    pedido = client.post(
        "/v1/solicitudes",
        headers=bot(celular),
        json={"unidad_id": unidad_id, "tipo_servicio_ids": [servicio_id], "preferencia_sin_restriccion": True},
    )
    assert pedido.status_code == 201, pedido.text
    return pedido.json()["data"]["ordenes"][0]["id"]


def _asignar(client, operador, orden_id: str, cuenta: str, recolector_id: str, inicio: str | None, fin: str | None):
    cuerpo = {"version_esperada": 1, "recolector_id": recolector_id, "forma_aviso": "llamada"}
    if inicio is not None:
        cuerpo["inicio"] = inicio
        cuerpo["fin"] = fin
        cuerpo["acuerdo_canal"] = "llamada"
    r = client.post(f"/v1/ordenes/{orden_id}/asignacion", headers=operador(cuenta), json=cuerpo)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _hoja(client, operador, gremio_id: str, fecha: str, usuario: str = "coord-reciclaje"):
    return client.get(
        "/v1/reportes/hoja-ruta",
        params={"gremio_id": gremio_id, "fecha": fecha},
        headers=operador(usuario, False),
    )


def _excel(client, operador, usuario: str = "fundacion", **params):
    return client.get("/v1/reportes/exportacion", params=params, headers=operador(usuario, False))


def _pesaje(client, operador, catalogo, *, kg_a: str, kg_r: str, torre: str | None, confirmar: bool):
    linea = {
        "material_id": catalogo["materiales:CARTON"],
        "metodo_medicion": "bascula",
        "kg_aceptados": kg_a,
        "kg_rechazados": kg_r,
    }
    if Decimal(kg_r) > 0:
        linea["motivo_rechazo_id"] = catalogo["motivos_rechazo:MOJADO"]
    recolectores = client.get(
        "/v1/recolectores",
        params={"gremio_id": catalogo["gremios:ASORESCATAR"]},
        headers=operador("coord-reciclaje", False),
    )
    assert recolectores.status_code == 200, recolectores.text
    creado = client.post(
        "/v1/pesajes",
        headers=operador("coord-reciclaje"),
        json={
            "gremio_id": catalogo["gremios:ASORESCATAR"],
            "fecha_medicion": CUANDO,
            "origen_captura": "manual",
            "recolector_id": recolectores.json()["data"][0]["id"],
            "orden_ids": [],
            "torre_origen_id": torre,
            "lineas": [linea],
        },
    )
    assert creado.status_code == 201, creado.text
    pesaje = creado.json()["data"]
    if not confirmar:
        return pesaje
    ok = client.post(
        f"/v1/pesajes/{pesaje['id']}/confirmacion",
        json={"version_esperada": pesaje["version"]},
        headers=operador("coord-reciclaje"),
    )
    assert ok.status_code == 200, ok.text
    return ok.json()["data"]


def _plano_xlsx(data: bytes) -> str:
    piezas: list[str] = []
    libro = load_workbook(BytesIO(data), read_only=True, data_only=True)
    for hoja in libro.worksheets:
        piezas.append(hoja.title)
        for fila in hoja.iter_rows(values_only=True):
            piezas.append(" ".join("" if v is None else str(v) for v in fila))
    libro.close()
    with zipfile.ZipFile(BytesIO(data)) as z:
        for nombre in z.namelist():
            if nombre.endswith(".xml"):
                piezas.append(z.read(nombre).decode("utf-8", errors="ignore"))
    return "\n".join(piezas).lower()


def test_hoja_de_un_gremio_no_incluye_ordenes_del_otro(client, operador, catalogo):
    reciclaje = catalogo["gremios:ASORESCATAR"]
    huerta = catalogo["gremios:ECORAZON"]
    manana = _negocio(client, operador, TEL_RESIDENTE, "Nidia Hoja Reciclaje", "ParadaMananaUnica", "Porteria norte hoja")
    tarde = _negocio(client, operador, "573008880012", "Petra Hoja Reciclaje", "ParadaTardeUnica", "Porteria sur hoja")
    ajena = _negocio(client, operador, "573008880013", "Omar Hoja Huerta", "ParadaAjenaHuerta", "Corredor ajeno hoja")
    otro = _negocio(client, operador, "573008880014", "Olga Hoja Otro Dia", "ParadaOtroDia", "Corredor otro dia")
    sin_hora = _negocio(client, operador, "573008880015", "Silvia Hoja Sin Hora", "ParadaSinHora", "Corredor sin hora")

    ciclista = client.post(
        "/v1/recicladores",
        headers=operador("admin"),
        json={"nombre": "Ciclista Hoja Unica", "gremio_id": reciclaje, "telefono_contacto": TEL_RECOLECTOR},
    )
    assert ciclista.status_code == 201, ciclista.text
    ciclista_id = ciclista.json()["data"]["id"]
    huerteros = client.get(
        "/v1/recolectores",
        params={"gremio_id": huerta, "activo": "true"},
        headers=operador("coord-huerta", False),
    )
    assert huerteros.status_code == 200 and huerteros.json()["data"], huerteros.text
    huertero_id = huerteros.json()["data"][0]["id"]

    servicio_r = catalogo["tipos_servicio:RECICLABLES"]
    servicio_h = catalogo["tipos_servicio:ORGANICOS"]
    id_manana = _pedir_servicio(client, TEL_RESIDENTE, manana, servicio_r)
    id_tarde = _pedir_servicio(client, "573008880012", tarde, servicio_r)
    id_ajena = _pedir_servicio(client, "573008880013", ajena, servicio_h)
    id_otro = _pedir_servicio(client, "573008880014", otro, servicio_r)
    id_sin = _pedir_servicio(client, "573008880015", sin_hora, servicio_r)

    assert _asignar(client, operador, id_manana, "coord-reciclaje", ciclista_id, f"{DIA}T09:00:00-05:00", f"{DIA}T10:00:00-05:00")["estado"] == "programada"
    assert _asignar(client, operador, id_tarde, "coord-reciclaje", ciclista_id, f"{DIA}T15:00:00-05:00", f"{DIA}T16:00:00-05:00")["estado"] == "programada"
    assert _asignar(client, operador, id_ajena, "coord-huerta", huertero_id, f"{DIA}T11:00:00-05:00", f"{DIA}T12:00:00-05:00")["estado"] == "programada"
    assert _asignar(client, operador, id_otro, "coord-reciclaje", ciclista_id, f"{OTRO_DIA}T09:00:00-05:00", f"{OTRO_DIA}T10:00:00-05:00")["estado"] == "programada"
    assert _asignar(client, operador, id_sin, "coord-reciclaje", ciclista_id, None, None)["estado"] == "asignada"

    r = _hoja(client, operador, reciclaje, DIA)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content.startswith(b"%PDF")
    assert f'filename="hoja-ruta-{DIA}.pdf"' in r.headers["content-disposition"]
    texto = _texto_pdf(r.content)
    assert "Ciclista Hoja Unica" in texto
    assert TEL_RECOLECTOR in texto
    assert "Nidia Hoja Reciclaje" in texto and "ParadaMananaUnica" in texto
    assert "Petra Hoja Reciclaje" in texto and "ParadaTardeUnica" in texto
    assert "Reciclable" in texto
    assert texto.index("09:00") < texto.index("15:00")
    for ausente in (
        "Omar Hoja Huerta",
        "ParadaAjenaHuerta",
        "Olga Hoja Otro Dia",
        "ParadaOtroDia",
        "Silvia Hoja Sin Hora",
        "ParadaSinHora",
        "Orgánico",
        TEL_RESIDENTE,
        "573008880012",
        "573008880013",
        "+57",
    ):
        assert ausente not in texto

    huerta_pdf = _hoja(client, operador, huerta, DIA, usuario="coord-huerta")
    assert huerta_pdf.status_code == 200, huerta_pdf.text
    texto_huerta = _texto_pdf(huerta_pdf.content)
    assert "Omar Hoja Huerta" in texto_huerta and "ParadaAjenaHuerta" in texto_huerta
    assert "Nidia Hoja Reciclaje" not in texto_huerta
    assert "ParadaMananaUnica" not in texto_huerta
    assert TEL_RESIDENTE not in texto_huerta

    admin = _hoja(client, operador, reciclaje, DIA, usuario="admin")
    assert admin.status_code == 200 and "Nidia Hoja Reciclaje" in _texto_pdf(admin.content)
    assert "Omar Hoja Huerta" not in _texto_pdf(admin.content)

    vacio = _hoja(client, operador, reciclaje, DIA_VACIO)
    assert vacio.status_code == 200 and vacio.content.startswith(b"%PDF")
    assert f'filename="hoja-ruta-{DIA_VACIO}.pdf"' in vacio.headers["content-disposition"]
    texto_vacio = _texto_pdf(vacio.content)
    assert "No hay paradas programadas para este día." in texto_vacio
    assert "Nidia Hoja Reciclaje" not in texto_vacio
    vaciar_avisos(client)


def test_fecha_invalida_y_gremio_inexistente(client, operador, catalogo):
    reciclaje = catalogo["gremios:ASORESCATAR"]
    for fecha in ("2026-13-01", "2026-02-29", "20-11-2026", "hoy", "", "2026-11-20T09:00:00-05:00"):
        r = _hoja(client, operador, reciclaje, fecha)
        assert r.status_code == 422, r.text
        error = r.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert "fecha" in error["fields"]

    faltante = _hoja(client, operador, str(uuid.uuid4()), DIA)
    assert faltante.status_code == 404, faltante.text
    assert faltante.json()["error"]["code"] == "NOT_FOUND"

    for usuario in ("fundacion", "coord-huerta", "reciclador-demo"):
        r = _hoja(client, operador, reciclaje, DIA_VACIO, usuario=usuario)
        assert r.status_code == 403, r.text
        assert r.json()["error"]["code"] == "FORBIDDEN"


def test_excel_de_fundacion_no_lleva_datos_de_contacto(client, operador, catalogo):
    unidad = client.post(
        "/v1/unidades",
        headers=operador("admin"),
        json={"tipo": "hogar", "torre_id": catalogo["torre:1"], "referencia_local": REF_EXCEL},
    )
    assert unidad.status_code == 201, unidad.text
    unidad_id = unidad.json()["data"]["id"]
    registro = client.post(
        "/v1/registros",
        headers=bot(TEL_EXCEL),
        json={
            "nombre": NOMBRE_EXCEL,
            "unidad_id": unidad_id,
            "consentimiento": {"version_politica": "2026-11", "decision": "aceptado"},
        },
    )
    assert registro.status_code == 201, registro.text
    alta = client.post(
        "/v1/piloto/habilitaciones",
        headers=operador("admin"),
        json={"participante_id": registro.json()["data"]["participante_id"], "unidad_id": unidad_id},
    )
    assert alta.status_code == 201, alta.text
    orden_id = _pedir_servicio(client, TEL_EXCEL, unidad_id, catalogo["tipos_servicio:RECICLABLES"])
    recolectores = client.get(
        "/v1/recolectores",
        params={"gremio_id": catalogo["gremios:ASORESCATAR"]},
        headers=operador("coord-reciclaje", False),
    )
    assert recolectores.status_code == 200 and recolectores.json()["data"], recolectores.text
    asignada = _asignar(
        client, operador, orden_id, "coord-reciclaje", recolectores.json()["data"][0]["id"],
        f"{DIA}T09:00:00-05:00", f"{DIA}T10:00:00-05:00",
    )
    cierre = client.post(
        f"/v1/ordenes/{orden_id}/resultado",
        headers=operador("coord-reciclaje"),
        json={
            "version_esperada": asignada["version"],
            "resultado": "recogida",
            "ocurrido_at": CUANDO,
            "materiales_confirmados": [catalogo["materiales:CARTON"]],
        },
    )
    assert cierre.status_code == 200, cierre.text

    _pesaje(client, operador, catalogo, kg_a="8.642", kg_r="1.357", torre=catalogo["torre:1"], confirmar=True)
    _pesaje(client, operador, catalogo, kg_a="9.991", kg_r="0.000", torre=catalogo["torre:1"], confirmar=False)
    _pesaje(client, operador, catalogo, kg_a="7.777", kg_r="0.000", torre=None, confirmar=True)

    params = {"desde": DESDE, "hasta": HASTA, "conjunto_id": catalogo["conjunto"]}
    resumen = client.get("/v1/reportes/resumen", params=params, headers=operador("fundacion", False))
    assert resumen.status_code == 200, resumen.text
    datos = resumen.json()["data"]

    r = _excel(client, operador, **params)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert r.content[:2] == b"PK"
    assert 'filename="reporte-2024-02-14-2024-02-15.xlsx"' in r.headers["content-disposition"]

    libro = load_workbook(BytesIO(r.content), data_only=True)
    assert libro.sheetnames == ["Ordenes", "Materiales", "Hogares"]
    ordenes = list(libro["Ordenes"].iter_rows(values_only=True))
    assert ordenes[0] == ("Estado", "Cantidad")
    assert {estado: cantidad for estado, cantidad in ordenes[1:]} == datos["ordenes_por_estado"]
    materiales = list(libro["Materiales"].iter_rows(values_only=True))
    assert materiales[0] == ("Codigo", "Material", "Kg aceptados", "Kg rechazados")
    por_codigo = {fila[0]: fila for fila in materiales[1:]}
    assert len(por_codigo) == len(datos["materiales"])
    for material in datos["materiales"]:
        fila = por_codigo[material["codigo"]]
        assert fila[1] == material["nombre"]
        assert fila[2] == material["kg_aceptados"]
        assert fila[3] == material["kg_rechazados"]
    assert por_codigo["CARTON"][2] == "8.642"
    assert por_codigo["CARTON"][3] == "1.357"
    hogares = list(libro["Hogares"].iter_rows(values_only=True))
    assert hogares == [("Indicador", "Cantidad"), ("Hogares participantes", datos["hogares_participantes"])]
    assert datos["hogares_participantes"] >= 1
    libro.close()

    plano = _plano_xlsx(r.content)
    for ausente in (
        "celular",
        "telefono",
        "teléfono",
        "apartamento",
        "apto",
        TEL_EXCEL,
        "+573009991199",
        NOMBRE_EXCEL.lower(),
        REF_EXCEL.lower(),
        "9.991",
        "7.777",
        "contacto",
    ):
        assert ausente not in plano

    admin = _excel(client, operador, usuario="admin", **params)
    assert admin.status_code == 200 and admin.content[:2] == b"PK"
    assert "8.642" in _plano_xlsx(admin.content)
    vaciar_avisos(client)


def test_coordinacion_no_descarga_el_excel_y_fechas_invalidas(client, operador, catalogo):
    params = {"desde": DESDE, "hasta": HASTA, "conjunto_id": catalogo["conjunto"]}
    for usuario in ("coord-reciclaje", "coord-huerta", "reciclador-demo"):
        r = _excel(client, operador, usuario=usuario, **params)
        assert r.status_code == 403, r.text
        assert r.json()["error"]["code"] == "FORBIDDEN"

    for malo in ("no-es-fecha", "2026-13-01T00:00:00-05:00", "2031-04-10", "2031-04-10T00:00:00"):
        r = _excel(client, operador, desde=malo, hasta=HASTA, conjunto_id=catalogo["conjunto"])
        assert r.status_code == 422, r.text
        error = r.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert "desde" in error["fields"]

    invertido = _excel(client, operador, desde=HASTA, hasta=DESDE, conjunto_id=catalogo["conjunto"])
    assert invertido.status_code == 400, invertido.text
    assert invertido.json()["error"]["code"] == "BAD_REQUEST"
