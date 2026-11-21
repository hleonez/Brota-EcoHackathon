"""Informe de impacto (PDF con gráficas) y serie por conjunto, para la Fundación."""

from __future__ import annotations

import uuid

from tests.test_certificado_verde import _texto_pdf

DESDE = "2026-06-01T00:00:00-05:00"
HASTA = "2026-12-01T00:00:00-05:00"


def test_fundacion_descarga_el_informe_del_barrio_y_de_un_conjunto(client, operador, catalogo):
    for usuario in ("fundacion", "admin"):
        r = client.get("/v1/reportes/informe-impacto", params={"desde": DESDE, "hasta": HASTA},
                       headers=operador(usuario, False))
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("application/pdf") and r.content.startswith(b"%PDF")
        assert 'filename="informe-impacto-barrio-villas-de-san-pablo-2026-06-01_2026-11-30.pdf"' in r.headers["content-disposition"]
        texto = _texto_pdf(r.content)
        for frase in ("Impacto del programa", "Indicadores del periodo", "Kilos aprovechados por mes",
                      "Comparación por conjunto", "Cómo se calcula"):
            assert frase in texto, frase
        for ausente in ("+57", "celular", "Apto"):
            assert ausente not in texto

    r = client.get("/v1/reportes/informe-impacto",
                   params={"desde": DESDE, "hasta": HASTA, "conjunto_id": catalogo["conjunto"]},
                   headers=operador("fundacion", False))
    assert r.status_code == 200, r.text
    texto = _texto_pdf(r.content)
    assert "Comparación por conjunto" not in texto and "Impacto del programa" in texto


def test_informe_permisos_y_validacion(client, operador):
    for usuario in ("coord-reciclaje", "coord-huerta", "reciclador-demo"):
        r = client.get("/v1/reportes/informe-impacto", params={"desde": DESDE, "hasta": HASTA},
                       headers=operador(usuario, False))
        assert r.status_code == 403, r.text
    h = operador("fundacion", False)
    assert client.get("/v1/reportes/informe-impacto", params={"desde": HASTA, "hasta": DESDE}, headers=h).status_code == 400
    r = client.get("/v1/reportes/informe-impacto",
                   params={"desde": DESDE, "hasta": HASTA, "conjunto_id": str(uuid.uuid4())}, headers=h)
    assert r.status_code == 404


def test_serie_por_conjunto(client, operador, catalogo):
    h = operador("fundacion", False)
    todo = client.get("/v1/reportes/serie", params={"desde": DESDE, "hasta": HASTA}, headers=h)
    conjunto = client.get("/v1/reportes/serie", params={"desde": DESDE, "hasta": HASTA, "conjunto_id": catalogo["conjunto"]},
                          headers=h)
    otro = client.get("/v1/reportes/serie", params={"desde": DESDE, "hasta": HASTA, "conjunto_id": str(uuid.uuid4())},
                      headers=h)
    assert todo.status_code == conjunto.status_code == otro.status_code == 200
    total = lambda r: sum(float(p["kg_aceptados"]) for p in r.json()["data"]["serie"])  # noqa: E731
    assert total(conjunto) <= total(todo)
    assert otro.json()["data"]["serie"] == []
