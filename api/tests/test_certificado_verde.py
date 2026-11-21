"""Certificado Verde: PDF mensual por conjunto, solo con pesajes confirmados."""

from __future__ import annotations

import re
import uuid
import zlib
from decimal import Decimal

from tests.conftest import bot

MES_CON_DATOS = "2026-08"
MES_BORRADOR = "2026-07"
MES_VACIO = "2020-01"
_USUARIO = {"ASORESCATAR": "coord-reciclaje", "ECORAZON": "coord-huerta"}


def _texto_pdf(data: bytes) -> str:
    """Une las cadenas literales de los streams. Ignora coordenadas del dibujo."""
    piezas: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        raw = match.group(1)
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            pass
        piezas.append(raw.decode("latin-1", errors="ignore"))
    contenido = "\n".join(piezas)
    textos: list[str] = []
    i = 0
    n = len(contenido)
    while i < n:
        if contenido[i] != "(":
            i += 1
            continue
        i += 1
        chars: list[str] = []
        while i < n:
            c = contenido[i]
            if c == "\\":
                i += 1
                if i >= n:
                    break
                esc = contenido[i]
                if esc in "01234567":
                    octal = esc
                    for _ in range(2):
                        if i + 1 < n and contenido[i + 1] in "01234567":
                            i += 1
                            octal += contenido[i]
                        else:
                            break
                    chars.append(chr(int(octal, 8)))
                else:
                    chars.append({"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f"}.get(esc, esc))
            elif c == ")":
                i += 1
                break
            else:
                chars.append(c)
            i += 1
        textos.append("".join(chars))
    return "\n".join(textos)


def _fila(texto: str, etiqueta: str, valor: str) -> bool:
    """En el PDF el indicador y su valor son celdas seguidas de la tabla «Resumen del período»."""
    return f"{etiqueta}\n{valor}" in texto


def _pedir(client, operador, catalogo, mes: str, usuario: str = "fundacion", conjunto_id: str | None = None):
    return client.get(
        "/v1/reportes/certificado",
        params={"conjunto_id": conjunto_id or catalogo["conjunto"], "mes": mes},
        headers=operador(usuario, False),
    )


def _pesaje(
    client,
    operador,
    catalogo,
    *,
    gremio: str,
    material: str,
    kg_aceptados: str,
    kg_rechazados: str,
    cuando: str,
    torre: str | None,
    confirmar: bool,
):
    usuario = _USUARIO[gremio]
    linea = {
        "material_id": catalogo[f"materiales:{material}"],
        "metodo_medicion": "bascula",
        "kg_aceptados": kg_aceptados,
        "kg_rechazados": kg_rechazados,
    }
    if Decimal(kg_rechazados) > 0:
        linea["motivo_rechazo_id"] = catalogo["motivos_rechazo:MOJADO"]
    recolectores = client.get(
        "/v1/recolectores",
        params={"gremio_id": catalogo[f"gremios:{gremio}"]},
        headers=operador(usuario, False),
    )
    assert recolectores.status_code == 200, recolectores.text
    cuerpo = {
        "gremio_id": catalogo[f"gremios:{gremio}"],
        "fecha_medicion": cuando,
        "origen_captura": "manual",
        "recolector_id": recolectores.json()["data"][0]["id"],
        "orden_ids": [],
        "torre_origen_id": torre,
        "lineas": [linea],
    }
    creado = client.post("/v1/pesajes", json=cuerpo, headers=operador(usuario))
    assert creado.status_code == 201, creado.text
    pesaje = creado.json()["data"]
    if not confirmar:
        assert pesaje["estado"] == "borrador"
        return pesaje
    confirmado = client.post(
        f"/v1/pesajes/{pesaje['id']}/confirmacion",
        json={"version_esperada": pesaje["version"]},
        headers=operador(usuario),
    )
    assert confirmado.status_code == 200, confirmado.text
    assert confirmado.json()["data"]["estado"] == "confirmado"
    return confirmado.json()["data"]


def test_fundacion_recibe_pdf_con_kilos_confirmados(client, operador, catalogo):
    _pesaje(
        client, operador, catalogo,
        gremio="ASORESCATAR", material="CARTON", kg_aceptados="10.000", kg_rechazados="2.500",
        cuando="2026-08-15T10:00:00-05:00", torre=catalogo["torre:1"], confirmar=True,
    )
    _pesaje(
        client, operador, catalogo,
        gremio="ECORAZON", material="ORGANICOS", kg_aceptados="4.500", kg_rechazados="0.000",
        cuando="2026-08-16T10:00:00-05:00", torre=catalogo["torre:2"], confirmar=True,
    )
    _pesaje(
        client, operador, catalogo,
        gremio="ASORESCATAR", material="PET", kg_aceptados="77.000", kg_rechazados="0.000",
        cuando="2026-08-17T10:00:00-05:00", torre=catalogo["torre:1"], confirmar=False,
    )
    _pesaje(
        client, operador, catalogo,
        gremio="ASORESCATAR", material="VIDRIO", kg_aceptados="55.000", kg_rechazados="0.000",
        cuando="2026-08-18T10:00:00-05:00", torre=None, confirmar=True,
    )
    _pesaje(
        client, operador, catalogo,
        gremio="ASORESCATAR", material="PLASTICO", kg_aceptados="33.000", kg_rechazados="0.000",
        cuando="2026-06-15T10:00:00-05:00", torre=catalogo["torre:1"], confirmar=True,
    )

    r = _pedir(client, operador, catalogo, MES_CON_DATOS)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content.startswith(b"%PDF")
    nombre = 'filename="certificado-verde-brisas-de-san-pablo-2026-08.pdf"'
    assert nombre in r.headers["content-disposition"]

    texto = _texto_pdf(r.content)
    assert _fila(texto, "Kilos aprovechados (reciclables)", "10.000 kg")
    assert "Kilos compostados" in texto and "4.500 kg" in texto
    assert _fila(texto, "Kilos aceptados en total", "14.500 kg")
    assert _fila(texto, "Kilos rechazados", "2.500 kg")
    assert _fila(texto, "Tasa de rechazo por peso", "14.71 %")
    assert _fila(texto, "Hogares participantes", "0")
    assert _fila(texto, "Torres con pesaje confirmado", "2")
    assert "ASORESCATAR" in texto and "ECORAZON" in texto
    assert "apoyo documental" in texto
    assert "sustituye el aforo de la empresa de aseo" in texto
    for ausente in ("77.000", "55.000", "33.000", "Rosa", "apto", "+57", "celular", "Residente"):
        assert ausente not in texto

    admin = _pedir(client, operador, catalogo, MES_CON_DATOS, usuario="admin")
    assert admin.status_code == 200 and admin.content.startswith(b"%PDF")
    assert "14.500 kg" in _texto_pdf(admin.content)


def test_borrador_no_suma(client, operador, catalogo):
    _pesaje(
        client, operador, catalogo,
        gremio="ASORESCATAR", material="CARTON", kg_aceptados="6.250", kg_rechazados="1.250",
        cuando="2026-07-10T10:00:00-05:00", torre=catalogo["torre:1"], confirmar=True,
    )
    _pesaje(
        client, operador, catalogo,
        gremio="ASORESCATAR", material="PET", kg_aceptados="3.750", kg_rechazados="0.000",
        cuando="2026-07-11T10:00:00-05:00", torre=catalogo["torre:2"], confirmar=False,
    )

    r = _pedir(client, operador, catalogo, MES_BORRADOR)
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"%PDF")
    texto = _texto_pdf(r.content)
    assert _fila(texto, "Kilos aprovechados (reciclables)", "6.250 kg")
    assert _fila(texto, "Kilos aceptados en total", "6.250 kg")
    assert _fila(texto, "Kilos rechazados", "1.250 kg")
    assert _fila(texto, "Torres con pesaje confirmado", "1")
    assert "3.750" not in texto
    assert "10.000" not in texto


def test_coordinacion_sin_reporte_global_recibe_403(client, operador, catalogo):
    for usuario in ("coord-reciclaje", "coord-huerta", "reciclador-demo"):
        r = _pedir(client, operador, catalogo, MES_VACIO, usuario=usuario)
        assert r.status_code == 403, r.text
        assert r.json()["error"]["code"] == "FORBIDDEN"
    residente = client.get(
        "/v1/reportes/certificado",
        params={"conjunto_id": catalogo["conjunto"], "mes": MES_VACIO},
        headers=bot("573009998877", False),
    )
    assert residente.status_code == 403
    assert residente.json()["error"]["code"] == "FORBIDDEN"


def test_mes_mal_formado_es_error_de_validacion(client, operador, catalogo):
    for mes in ("2026-13", "noviembre", "2026/11", "2026-8", ""):
        r = _pedir(client, operador, catalogo, mes)
        assert r.status_code == 422, r.text
        error = r.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert "mes" in error["fields"]


def test_conjunto_inexistente_es_404(client, operador, catalogo):
    r = _pedir(client, operador, catalogo, MES_VACIO, conjunto_id=str(uuid.uuid4()))
    assert r.status_code == 404, r.text
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_mes_sin_datos_devuelve_pdf(client, operador, catalogo):
    for usuario in ("fundacion", "admin"):
        r = _pedir(client, operador, catalogo, MES_VACIO, usuario=usuario)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content.startswith(b"%PDF")
        assert r.headers["content-disposition"].endswith(f'-{MES_VACIO}.pdf"') or MES_VACIO in r.headers["content-disposition"]
        texto = _texto_pdf(r.content)
        assert _fila(texto, "Kilos aprovechados (reciclables)", "0.000 kg")
        assert "Kilos compostados" in texto and "0.000 kg" in texto
        assert _fila(texto, "Kilos rechazados", "0.000 kg")
        assert _fila(texto, "Tasa de rechazo por peso", "0 %")
        assert "Sin pesajes confirmados en este período." in texto
        assert _fila(texto, "Hogares participantes", "0")
        assert _fila(texto, "Torres con pesaje confirmado", "0")
        assert "apoyo documental" in texto
        assert "aforo de la empresa de aseo" in texto
