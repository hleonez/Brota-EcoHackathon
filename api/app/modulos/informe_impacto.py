"""Informe de impacto (PDF con gráficas) para la Fundación: barrio completo o un conjunto.

Usa las mismas cifras que el panel (`/v1/reportes/resumen` y `/v1/reportes/serie`), así el PDF y la
pantalla nunca se contradicen. Compara con el periodo anterior de igual duración. Sin nombres,
celulares ni apartamentos: solo totales.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errores import no_encontrado, prohibido
from app.core.seguridad import Actor
from app.core.tipos import ahora, zona
from app.models import Conjunto, Gremio
from app.modulos.certificado import (
    _BOSQUE, _CARBON, _FONDO, _GRIS, _HOJA, _LINEA, _MARIPOSA, _MESES, _PDF, _SOLAR, _TURQUESA, _VERDE,
    _espacio, _logo, _recortar, _tabla, _tarjeta, _texto, _titulo, slug_conjunto,
)

BARRIO = "Villas de San Pablo"
_CORTOS = ("", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def _num(valor: Decimal | float | int, decimales: int = 0) -> str:
    """Miles con punto y decimales con coma, como se lee en Colombia."""
    texto = f"{float(valor):,.{decimales}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def _variacion(actual: float, anterior: float) -> str:
    if anterior <= 0:
        return "nuevo" if actual > 0 else "sin cambio"
    cambio = (actual - anterior) / anterior * 100
    return f"{'+' if cambio >= 0 else ''}{_num(cambio, 0)} % vs. anterior"


def _fecha(d: datetime) -> str:
    return f"{d.day} {_CORTOS[d.month]} {d.year}"


def _paso(desde: datetime, hasta: datetime) -> str:
    return "semana" if (hasta - desde) <= timedelta(days=62) else "mes"


def _etiqueta_serie(iso: str, agrupacion: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{_CORTOS[d.month]} {str(d.year)[2:]}" if agrupacion == "mes" else f"{d.day} {_CORTOS[d.month]}"


def _maximo_redondo(valor: float) -> float:
    if valor <= 0:
        return 1.0
    base = 10 ** (len(str(int(valor))) - 1)
    for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if m * base >= valor:
            return m * base
    return 10 * base


def _barras_verticales(pdf: _PDF, x: float, y: float, w: float, h: float,
                       etiquetas: list[str], valores: list[float], color: tuple[int, int, int]) -> None:
    """Gráfica de barras con cuadrícula, eje en kg y el valor encima de cada barra."""
    pdf.set_fill_color(*_FONDO)
    pdf.rect(x, y, w, h, style="F", round_corners=True, corner_radius=3)
    if not any(v > 0 for v in valores):
        pdf.set_xy(x, y + h / 2 - 3)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_GRIS)
        pdf.cell(w, 6, _texto("Sin pesajes confirmados en el periodo."), align="C")
        return
    izquierda, abajo, arriba = x + 18, y + h - 9, y + 8
    ancho_util = x + w - 5 - izquierda
    tope = _maximo_redondo(max(valores))
    pdf.set_line_width(0.2)
    for i in range(5):
        yy = abajo - (abajo - arriba) * i / 4
        pdf.set_draw_color(*_LINEA)
        pdf.line(izquierda, yy, x + w - 5, yy)
        pdf.set_xy(x + 1, yy - 2)
        pdf.set_font("Helvetica", "", 6.5)
        pdf.set_text_color(*_GRIS)
        pdf.cell(16, 4, _texto(f"{_num(tope * i / 4)} kg"), align="R")
    if not valores:
        pdf.set_xy(x, y + h / 2 - 3)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(w, 6, _texto("Sin pesajes confirmados en el periodo."), align="C")
        return
    n = len(valores)
    hueco = ancho_util / n
    ancho_barra = min(16, hueco * 0.62)
    for i, (etiqueta, valor) in enumerate(zip(etiquetas, valores)):
        cx = izquierda + hueco * i + hueco / 2
        alto = (abajo - arriba) * (valor / tope)
        if alto > 0:
            pdf.set_fill_color(*color)
            pdf.rect(cx - ancho_barra / 2, abajo - alto, ancho_barra, alto, style="F",
                     round_corners=("TOP_LEFT", "TOP_RIGHT"), corner_radius=min(2, ancho_barra / 3))
            pdf.set_xy(cx - 12, abajo - alto - 4.5)
            pdf.set_font("Helvetica", "B", 6.5)
            pdf.set_text_color(*_CARBON)
            pdf.cell(24, 4, _texto(_num(valor)), align="C")
        pdf.set_xy(cx - 12, abajo + 1.5)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*_GRIS)
        pdf.cell(24, 4, _texto(etiqueta), align="C")


def _barras_horizontales(pdf: _PDF, filas: list[tuple[str, float, str]], color: tuple[int, int, int]) -> None:
    """Una barra por fila: etiqueta a la izquierda, barra proporcional y el valor al final."""
    if not filas:
        return
    _espacio(pdf, 8 * min(len(filas), 6) + 4)
    tope = max(v for _, v, _ in filas) or 1
    for etiqueta, valor, texto in filas:
        _espacio(pdf, 8)
        y = pdf.get_y()
        pdf.set_xy(15, y)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(*_CARBON)
        pdf.cell(46, 6, _recortar(pdf, etiqueta, 46))
        pdf.set_fill_color(*_FONDO)
        pdf.rect(62, y + 1, 98, 4, style="F", round_corners=True, corner_radius=2)
        largo = 98 * valor / tope
        if largo > 0:
            pdf.set_fill_color(*color)
            pdf.rect(62, y + 1, max(largo, 2), 4, style="F", round_corners=True, corner_radius=2)
        pdf.set_xy(162, y)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*_GRIS)
        pdf.cell(33, 6, _texto(texto), align="R")
        pdf.set_y(y + 8)
    pdf.ln(2)


def _cifras(db: Session, actor: Actor, desde: datetime, hasta: datetime, conjunto_id: uuid.UUID | None) -> dict[str, Any]:
    from app.modulos.reportes import get_resumen, get_serie

    def resumen(d: datetime, h: datetime, cid: uuid.UUID | None) -> dict[str, Any]:
        return get_resumen(desde=d, hasta=h, gremio_id=None, conjunto_id=cid, torre_id=None,
                           material_id=None, recolector_id=None, actor=actor, db=db)["data"]

    duracion = hasta - desde
    agrupacion = _paso(desde, hasta)
    serie = get_serie(desde=desde, hasta=hasta, agrupacion=agrupacion, gremio_id=None, material_id=None,
                      conjunto_id=conjunto_id, actor=actor, db=db)["data"]["serie"]
    conjuntos = list(db.execute(select(Conjunto).where(Conjunto.activo.is_(True)).order_by(Conjunto.nombre)).scalars())
    return {
        "actual": resumen(desde, hasta, conjunto_id),
        "anterior": resumen(desde - duracion, desde, conjunto_id),
        "serie": serie,
        "agrupacion": agrupacion,
        "por_conjunto": [] if conjunto_id else [(c.nombre, resumen(desde, hasta, c.id)) for c in conjuntos],
        "gremios": {str(g.id): g.nombre for g in db.execute(select(Gremio)).scalars()},
    }


def render_informe(nombre_territorio: str, desde: datetime, hasta: datetime, datos: dict[str, Any]) -> bytes:
    act, ant = datos["actual"], datos["anterior"]
    tz = zona(get_settings().zona_horaria)
    d_local, h_local = desde.astimezone(tz), (hasta - timedelta(seconds=1)).astimezone(tz)
    corte = ahora().astimezone(tz)

    pdf = _PDF(format="A4", unit="mm")
    pdf.pie = "Valores estimados (kg × precio vigente); no son pagos certificados. Brota · informe de impacto"
    pdf.set_compression(False)
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=28)
    pdf.alias_nb_pages()
    pdf.set_title(f"Informe de impacto {nombre_territorio}")
    pdf.set_author("Brota · EcoConecta Villas de San Pablo")
    pdf.set_subject("Impacto del programa de aprovechamiento de residuos")
    pdf.set_creator("Brota")
    pdf.add_page()

    # ---------------------------------------------------------------- encabezado
    _logo(pdf, "ecoconecta.png", 15, 9, 19)
    _logo(pdf, "brota.png", 159, 13, 36 * 100 / 420)
    pdf.set_fill_color(*_BOSQUE)
    pdf.rect(0, 33, 210, 30, style="F")
    pdf.set_fill_color(*_SOLAR)
    pdf.rect(0, 63, 210, 1.6, style="F")
    pdf.set_xy(15, 38)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(120, 11, _texto("Impacto del programa"))
    pdf.set_xy(15, 50)
    pdf.set_font("Helvetica", "", 10.5)
    pdf.set_text_color(214, 236, 222)
    pdf.cell(120, 6, _texto(f"Fundación Santo Domingo · {nombre_territorio}"))
    sello = _texto(f"{_fecha(d_local)} - {_fecha(h_local)}".upper())
    pdf.set_font("Helvetica", "B", 9)
    ancho_sello = pdf.get_string_width(sello) + 12
    pdf.set_fill_color(*_SOLAR)
    pdf.rect(195 - ancho_sello, 42, ancho_sello, 11, style="F", round_corners=True, corner_radius=5.5)
    pdf.set_xy(195 - ancho_sello, 42)
    pdf.set_text_color(*_BOSQUE)
    pdf.cell(ancho_sello, 11, sello, align="C")
    pdf.set_y(70)

    # ---------------------------------------------------------------- indicadores
    kg, kg_ant = float(act["kg_aceptados"]), float(ant["kg_aceptados"])
    hog, hog_ant = act["hogares_participantes"], ant["hogares_participantes"]
    valor = float(act["valor_estimado"]) if act["valor_estimado"] is not None else None
    valor_ant = float(ant["valor_estimado"] or 0)
    tasa = act["tasa_rechazo_peso"]
    _titulo(pdf, "Indicadores del periodo")
    y = pdf.get_y()
    ancho = (180 - 3 * 4) / 4
    tarjetas = [
        (_VERDE, f"{_num(kg, 1)}", "kg aprovechados", _variacion(kg, kg_ant)),
        (_TURQUESA, str(hog), "hogares participantes", _variacion(hog, hog_ant)),
        (_MARIPOSA, f"${_num(valor)}" if valor is not None else "Sin precio", "valor estimado (COP)",
         _variacion(valor or 0, valor_ant) if valor is not None else "Falta precio por kilo"),
        (_HOJA, f"{_num((tasa or 0) * 100, 1)} %" if tasa is not None else "-", "tasa de rechazo",
         "del peso entregado"),
    ]
    for i, (color, cifra, unidad, nota) in enumerate(tarjetas):
        _tarjeta(pdf, 15 + i * (ancho + 4), y, ancho, 28, color, cifra, unidad, nota)
    pdf.set_y(y + 33)
    rec = act["resultados"]
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_GRIS)
    pdf.multi_cell(180, 5, _texto(
        f"Recolecciones hechas: {rec['recogidas']} · rechazadas: {rec['rechazadas']} · "
        f"solicitudes creadas en el periodo: {sum(act['ordenes_por_estado'].values())}."))
    pdf.ln(2)

    # ---------------------------------------------------------------- serie
    agrupacion = datos["agrupacion"]
    _titulo(pdf, f"Kilos aprovechados por {'mes' if agrupacion == 'mes' else 'semana'}")
    _espacio(pdf, 66)
    y = pdf.get_y()
    serie = datos["serie"]
    _barras_verticales(pdf, 15, y, 180, 60, [_etiqueta_serie(p["inicio_local"], agrupacion) for p in serie],
                       [float(p["kg_aceptados"]) for p in serie], _VERDE)
    pdf.set_y(y + 64)

    # ---------------------------------------------------------------- materiales
    materiales = sorted(act["materiales"], key=lambda m: -float(m["kg_aceptados"]))
    if materiales:
        _titulo(pdf, "Qué se aprovechó, por material")
        _barras_horizontales(pdf, [(m["nombre"], float(m["kg_aceptados"]), f"{_num(float(m['kg_aceptados']), 1)} kg")
                                   for m in materiales], _HOJA)
        _tabla(
            pdf, ["Material", "Colectivo", "Aceptados", "Rechazados", "Valor estimado"], [46, 44, 28, 28, 34],
            [[m["nombre"], datos["gremios"].get(m["gremio_id"], ""), f"{_num(float(m['kg_aceptados']), 1)} kg",
              f"{_num(float(m['kg_rechazados']), 1)} kg",
              f"${_num(float(m['valor_estimado']))}" if m["valor_estimado"] else "Sin precio"] for m in materiales],
            ["L", "L", "R", "R", "R"],
        )

    # ---------------------------------------------------------------- conjuntos
    if datos["por_conjunto"]:
        _titulo(pdf, f"Comparación por conjunto · barrio {BARRIO}")
        filas = datos["por_conjunto"]
        _barras_horizontales(pdf, [(n, float(r["kg_aceptados"]), f"{_num(float(r['kg_aceptados']), 1)} kg") for n, r in filas],
                             _TURQUESA)
        _tabla(
            pdf, ["Conjunto", "Kilos aceptados", "Hogares", "Recolecciones", "Rechazo (peso)"], [56, 32, 26, 32, 34],
            [[n, f"{_num(float(r['kg_aceptados']), 1)} kg", str(r["hogares_participantes"]), str(r["resultados"]["recogidas"]),
              f"{_num(r['tasa_rechazo_peso'] * 100, 1)} %" if r["tasa_rechazo_peso"] is not None else "-"] for n, r in filas],
            ["L", "R", "R", "R", "R"],
        )
        if act.get("kg_sin_torre_identificada") and float(act["kg_sin_torre_identificada"]) > 0:
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*_GRIS)
            pdf.multi_cell(180, 4.5, _texto(
                f"{_num(float(act['kg_sin_torre_identificada']), 1)} kg del barrio no tienen torre de origen comprobada: "
                "suman al total, pero no a ningún conjunto."))

    # ---------------------------------------------------------------- cómo se calcula
    _titulo(pdf, "Cómo se calcula")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*_GRIS)
    for linea in (
        "Kilos: solo pesajes confirmados (no borradores ni anulados), por fecha de medición.",
        "Hogares: unidades tipo hogar con una recolección o entrega directa válida en el periodo.",
        "Valor estimado: kilos aceptados por el precio por kilo vigente; es una referencia, no un pago.",
        "Comparación: contra el periodo anterior de la misma duración.",
        f"Corte de datos: {_fecha(corte)}, {corte:%H:%M} (hora de Bogotá).",
    ):
        _espacio(pdf, 6)
        pdf.set_x(18)
        pdf.cell(4, 5, "-")
        pdf.multi_cell(170, 5, _texto(linea))
    return bytes(pdf.output())


def generar_informe(db: Session, actor: Actor, desde: datetime, hasta: datetime,
                    conjunto_id: uuid.UUID | None) -> tuple[bytes, str]:
    if not (actor.es_fundacion or actor.es_admin):
        raise prohibido("El informe de impacto es para la Fundación o la administración.")
    if conjunto_id is not None:
        conjunto = db.get(Conjunto, conjunto_id)
        if conjunto is None:
            raise no_encontrado("conjunto")
        nombre, slug = conjunto.nombre, slug_conjunto(conjunto.nombre, conjunto.id)
    else:
        nombre, slug = f"Barrio {BARRIO}", "barrio-villas-de-san-pablo"
    datos = _cifras(db, actor, desde, hasta, conjunto_id)
    tz = zona(get_settings().zona_horaria)
    sufijo = f"{desde.astimezone(tz):%Y-%m-%d}_{(hasta - timedelta(seconds=1)).astimezone(tz):%Y-%m-%d}"
    return render_informe(nombre, desde, hasta, datos), f"informe-impacto-{slug}-{sufijo}.pdf"
