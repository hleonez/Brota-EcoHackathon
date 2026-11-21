"""Certificado Verde mensual en PDF.

Salida agregada, calculada al vuelo. No se persiste la emisión.

Cifras, y de dónde salen:
- Kilos: ``linea_pesaje`` de pesajes en estado ``confirmado`` (no borrador, no anulado),
  con ``fecha_medicion`` dentro del mes local y ``torre_origen_id`` de una torre del conjunto.
- Tipo de aprovechamiento: gremio del material, clasificado con ``tipo_servicio``
  (``RECICLABLES`` = kilos aprovechados, ``ORGANICOS`` = kilos compostados).
- Tasa de rechazo por peso: kilos rechazados / kilos pesados de esas mismas líneas.
- Hogares: la misma regla que el resumen (recogida cerrada o entrega directa con pesaje confirmado).
- Torres: torres del conjunto con al menos un pesaje confirmado en el mes.

Un sync pendiente no entra: el pesaje sigue en borrador hasta que se confirma.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from decimal import ROUND_HALF_UP, Decimal

from fpdf import FPDF
from sqlalchemy import distinct, false, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errores import invalido
from app.core.tipos import ahora, zona
from app.models import Conjunto, Gremio, LineaPesaje, Material, Pesaje, TipoServicio, Torre
from app.modulos.comun import obtener

FORMULA = "certificado_verde_v1"
_MES = re.compile(r"(?P<anio>[0-9]{4})-(?P<mes>0[1-9]|1[0-2])")
_MESES = (
    "",
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
_TIPO_RECICLABLES = "reciclables"
_TIPO_ORGANICOS = "organicos"
_TIPO_OTRO = "otro"
_ETIQUETA_TIPO = {
    _TIPO_RECICLABLES: "reciclables",
    _TIPO_ORGANICOS: "orgánicos",
    _TIPO_OTRO: "otro",
}


@dataclass
class _GremioCifra:
    codigo: str
    nombre: str
    tipo: str
    kg_aceptados: Decimal = Decimal(0)
    kg_rechazados: Decimal = Decimal(0)


@dataclass
class _MaterialCifra:
    codigo: str
    nombre: str
    gremio_codigo: str
    kg_aceptados: Decimal
    kg_rechazados: Decimal


@dataclass
class _Cifras:
    conjunto_nombre: str
    conjunto_id: uuid.UUID
    mes: str
    etiqueta_mes: str
    desde: datetime
    hasta: datetime
    zona: str
    corte: datetime
    kg_aprovechados: Decimal
    kg_compostados: Decimal
    kg_otros: Decimal
    kg_aceptados: Decimal
    kg_rechazados: Decimal
    tasa_pct: str
    tasa_ratio: str
    hogares: int
    torres: int
    sin_pesajes: bool
    gremios: list[_GremioCifra] = field(default_factory=list)
    materiales: list[_MaterialCifra] = field(default_factory=list)


def periodo_mes(mes: str) -> tuple[datetime, datetime, str]:
    """Mes calendario ``AAAA-MM`` en la zona de la API. ``hasta`` es exclusivo."""
    encontrado = _MES.fullmatch((mes or "").strip())
    if encontrado is None:
        raise invalido({"mes": "Usa el formato AAAA-MM, por ejemplo 2026-11"})
    anio = int(encontrado.group("anio"))
    mes_n = int(encontrado.group("mes"))
    tz = zona(get_settings().zona_horaria)
    try:
        desde = datetime(anio, mes_n, 1, tzinfo=tz)
        if mes_n == 12:
            hasta = datetime(anio + 1, 1, 1, tzinfo=tz)
        else:
            hasta = datetime(anio, mes_n + 1, 1, tzinfo=tz)
    except ValueError:
        raise invalido({"mes": "Usa el formato AAAA-MM, por ejemplo 2026-11"}) from None
    return desde, hasta, f"{_MESES[mes_n]} de {anio}"


def slug_conjunto(nombre: str, conjunto_id: uuid.UUID) -> str:
    base = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower()[:60]
    return base or conjunto_id.hex[:12]


def _fmt_kg(valor: Decimal) -> str:
    return f"{Decimal(valor).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP):.3f}"


def _tasa(aceptados: Decimal, rechazados: Decimal) -> tuple[str, str]:
    total = aceptados + rechazados
    if total == 0:
        return "0 %", "0.0000"
    ratio = (rechazados / total).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    pct = (ratio * Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{pct} %", f"{ratio:.4f}"


def _texto(valor: str) -> str:
    """Helvetica solo cubre Latin-1. Un emoji de catálogo no puede romper el PDF."""
    return valor.encode("latin-1", errors="replace").decode("latin-1")


def _clasificar(codigos: set[str]) -> str:
    organico = "ORGANICOS" in codigos
    reciclable = "RECICLABLES" in codigos
    if organico and not reciclable:
        return _TIPO_ORGANICOS
    if reciclable and not organico:
        return _TIPO_RECICLABLES
    return _TIPO_OTRO


def _tipos_por_gremio(db: Session) -> dict[uuid.UUID, str]:
    mapa: dict[uuid.UUID, set[str]] = {}
    for gremio_id, codigo in db.execute(select(TipoServicio.gremio_id, TipoServicio.codigo)):
        mapa.setdefault(gremio_id, set()).add(codigo)
    return {gremio_id: _clasificar(codigos) for gremio_id, codigos in mapa.items()}


def _hogares(db: Session, desde: datetime, hasta: datetime, torre_ids: list[uuid.UUID]) -> int:
    if not torre_ids:
        return 0
    # Misma cohorte que GET /reportes/resumen: no se duplica la consulta en este módulo.
    from app.modulos.reportes import _hogares_participantes

    hogares = _hogares_participantes(db, desde, hasta, torre_ids, None)
    return int(db.execute(select(func.count(distinct(hogares.c.unidad_id)))).scalar_one())


def _cifras(db: Session, conjunto_id: uuid.UUID, mes: str) -> _Cifras:
    desde, hasta, etiqueta = periodo_mes(mes)
    conjunto = obtener(db, Conjunto, conjunto_id, "conjunto")
    torre_ids = list(db.execute(select(Torre.id).where(Torre.conjunto_id == conjunto_id)).scalars())
    filtros = [
        Pesaje.estado == "confirmado",
        Pesaje.fecha_medicion >= desde,
        Pesaje.fecha_medicion < hasta,
        Pesaje.torre_origen_id.in_(torre_ids) if torre_ids else false(),
    ]
    filas = db.execute(
        select(
            Gremio.id,
            Gremio.codigo,
            Gremio.nombre,
            Material.codigo,
            Material.nombre,
            func.sum(LineaPesaje.kg_aceptados),
            func.sum(LineaPesaje.kg_rechazados),
        )
        .select_from(LineaPesaje)
        .join(Pesaje, Pesaje.id == LineaPesaje.pesaje_id)
        .join(Material, Material.id == LineaPesaje.material_id)
        .join(Gremio, Gremio.id == Material.gremio_id)
        .where(*filtros)
        .group_by(Gremio.id, Gremio.codigo, Gremio.nombre, Material.id, Material.codigo, Material.nombre)
        .order_by(Gremio.nombre, Material.nombre)
    ).all()
    tipos = _tipos_por_gremio(db)
    gremios: dict[str, _GremioCifra] = {}
    materiales: list[_MaterialCifra] = []
    for gremio_id, g_codigo, g_nombre, m_codigo, m_nombre, kg_a, kg_r in filas:
        aceptados = Decimal(kg_a or 0)
        rechazados = Decimal(kg_r or 0)
        cifra = gremios.get(g_codigo)
        if cifra is None:
            cifra = _GremioCifra(codigo=g_codigo, nombre=g_nombre, tipo=tipos.get(gremio_id, _TIPO_OTRO))
            gremios[g_codigo] = cifra
        cifra.kg_aceptados += aceptados
        cifra.kg_rechazados += rechazados
        materiales.append(
            _MaterialCifra(
                codigo=m_codigo,
                nombre=m_nombre,
                gremio_codigo=g_codigo,
                kg_aceptados=aceptados,
                kg_rechazados=rechazados,
            )
        )
    aprovechados = compostados = otros = aceptados_total = rechazados_total = Decimal(0)
    for cifra in gremios.values():
        aceptados_total += cifra.kg_aceptados
        rechazados_total += cifra.kg_rechazados
        if cifra.tipo == _TIPO_RECICLABLES:
            aprovechados += cifra.kg_aceptados
        elif cifra.tipo == _TIPO_ORGANICOS:
            compostados += cifra.kg_aceptados
        else:
            otros += cifra.kg_aceptados
    tasa_pct, tasa_ratio = _tasa(aceptados_total, rechazados_total)
    torres = 0
    if torre_ids:
        torres = int(
            db.execute(select(func.count(distinct(Pesaje.torre_origen_id))).where(*filtros)).scalar_one()
        )
    return _Cifras(
        conjunto_nombre=conjunto.nombre,
        conjunto_id=conjunto.id,
        mes=mes.strip(),
        etiqueta_mes=etiqueta,
        desde=desde,
        hasta=hasta,
        zona=get_settings().zona_horaria,
        corte=ahora(),
        kg_aprovechados=aprovechados,
        kg_compostados=compostados,
        kg_otros=otros,
        kg_aceptados=aceptados_total,
        kg_rechazados=rechazados_total,
        tasa_pct=tasa_pct,
        tasa_ratio=tasa_ratio,
        hogares=_hogares(db, desde, hasta, torre_ids),
        torres=torres,
        sin_pesajes=not filas,
        gremios=list(gremios.values()),
        materiales=materiales,
    )


_RECURSOS = Path(__file__).resolve().parent.parent / "recursos"

# Colores del manual de identidad EcoConecta (RGB).
_BOSQUE = (6, 59, 46)
_VERDE = (22, 138, 46)
_HOJA = (101, 169, 10)
_TURQUESA = (10, 155, 112)
_SOLAR = (246, 196, 0)
_MARIPOSA = (242, 140, 0)
_CARBON = (32, 37, 34)
_GRIS = (88, 99, 92)
_LINEA = (221, 229, 223)
_FONDO = (242, 245, 242)
_ZEBRA = (247, 250, 247)


def _logo(pdf: FPDF, nombre: str, x: float, y: float, h: float) -> float:
    """Dibuja un logo de `app/recursos` con alto `h`; devuelve el ancho usado (0 si falta el archivo)."""
    ruta = _RECURSOS / nombre
    if not ruta.exists():
        return 0.0
    info = pdf.image(str(ruta), x=x, y=y, h=h)
    return float(info.rendered_width)


def _fecha_larga(d: datetime) -> str:
    return f"{d.day} de {_MESES[d.month]} de {d.year}"


def _hora(d: datetime) -> str:
    return f"{d:%H:%M}"


class _PDF(FPDF):
    def footer(self) -> None:
        y = self.h - 21
        self.set_draw_color(*_LINEA)
        self.set_line_width(0.3)
        self.line(15, y, 195, y)
        self.set_xy(15, y + 3)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*_GRIS)
        self.cell(27, 6, _texto("Una iniciativa con"))
        x = 43.0
        x += _logo(self, "fundacion.png", x, y + 1.6, 9) + 4
        x += _logo(self, "villas.png", x, y + 2.2, 7.5) + 4
        self.set_xy(x, y + 3)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*_BOSQUE)
        self.cell(32, 6, _texto("Universidad Libre"))
        self.set_xy(15, self.h - 10)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*_GRIS)
        self.cell(150, 4, _texto(f"No sustituye el aforo de la empresa de aseo. Brota · fórmula {FORMULA}"))
        self.cell(30, 4, _texto(f"Página {self.page_no()} de {{nb}}"), align="R")


def _espacio(pdf: FPDF, alto: float) -> None:
    """Salta de página si el bloque que sigue no cabe completo."""
    if pdf.get_y() + alto > pdf.h - 28:
        pdf.add_page()


def _titulo(pdf: FPDF, texto: str) -> None:
    _espacio(pdf, 20)
    pdf.ln(3)
    y = pdf.get_y()
    pdf.set_fill_color(*_HOJA)
    pdf.ellipse(15, y + 2.1, 2.6, 2.6, style="F")
    pdf.set_xy(20, y)
    pdf.set_font("Helvetica", "B", 12.5)
    pdf.set_text_color(*_BOSQUE)
    pdf.cell(0, 7, _texto(texto), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _recortar(pdf: FPDF, texto: str, ancho: float) -> str:
    limpio = _texto(texto)
    if pdf.get_string_width(limpio) <= ancho - 3:
        return limpio
    while limpio and pdf.get_string_width(limpio + "...") > ancho - 3:
        limpio = limpio[:-1]
    return limpio + "..."


def _tabla(pdf: FPDF, encabezados: list[str], anchos: list[float], filas: list[list[str]],
           alineaciones: list[str], negrita_col: int | None = 0) -> None:
    """Tabla con encabezado verde bosque, filas cebra y líneas suaves. Cada celda es un texto propio."""
    _espacio(pdf, 8 + 7 * min(len(filas), 4))
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_fill_color(*_BOSQUE)
    pdf.set_text_color(255, 255, 255)
    pdf.set_draw_color(*_BOSQUE)
    for texto, ancho, alin in zip(encabezados, anchos, alineaciones):
        pdf.cell(ancho, 8, _texto(texto), border=0, align=alin, fill=True)
    pdf.ln(8)
    pdf.set_draw_color(*_LINEA)
    pdf.set_line_width(0.2)
    for n, fila in enumerate(filas):
        _espacio(pdf, 7)
        pdf.set_fill_color(*(_ZEBRA if n % 2 else (255, 255, 255)))
        for i, (texto, ancho, alin) in enumerate(zip(fila, anchos, alineaciones)):
            pdf.set_font("Helvetica", "B" if i == negrita_col else "", 9)
            pdf.set_text_color(*(_CARBON if i == negrita_col else _GRIS))
            pdf.cell(ancho, 7, _recortar(pdf, texto, ancho), border="B", align=alin, fill=True)
        pdf.ln(7)
    pdf.ln(2)


def _tarjeta(pdf: FPDF, x: float, y: float, w: float, h: float, color: tuple[int, int, int],
             valor: str, unidad: str, etiqueta: str) -> None:
    tinte = tuple(round(c + (255 - c) * 0.88) for c in color)
    pdf.set_fill_color(*tinte)
    pdf.set_draw_color(*tinte)
    pdf.rect(x, y, w, h, style="F", round_corners=True, corner_radius=3)
    pdf.set_fill_color(*color)
    pdf.rect(x, y, w, 1.6, style="F")
    pdf.set_xy(x + 4, y + 5)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*color)
    pdf.cell(w - 8, 8, _texto(valor))
    pdf.set_xy(x + 4, y + 13)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(w - 8, 4, _texto(unidad))
    pdf.set_xy(x + 4, y + 18)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_GRIS)
    pdf.multi_cell(w - 8, 3.8, _texto(etiqueta))


def render_pdf(cifras: _Cifras) -> bytes:
    pdf = _PDF(format="A4", unit="mm")
    pdf.set_compression(False)
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=28)
    pdf.alias_nb_pages()
    pdf.set_title(f"Certificado Verde {cifras.conjunto_nombre} {cifras.mes}")
    pdf.set_author("Brota · EcoConecta Villas de San Pablo")
    pdf.set_subject("Informe mensual de aprovechamiento de residuos")
    pdf.set_creator("Brota")
    pdf.add_page()
    zona_local = cifras.desde.tzinfo
    corte = cifras.corte.astimezone(zona_local) if zona_local else cifras.corte
    ultimo_dia = (cifras.hasta - timedelta(days=1))

    # ---------------------------------------------------------------- encabezado con marcas
    _logo(pdf, "ecoconecta.png", 15, 9, 19)
    ancho_brota = 36.0
    _logo(pdf, "brota.png", 195 - ancho_brota, 13, ancho_brota * 100 / 420)
    pdf.set_fill_color(*_BOSQUE)
    pdf.rect(0, 33, 210, 30, style="F")
    pdf.set_fill_color(*_SOLAR)
    pdf.rect(0, 63, 210, 1.6, style="F")
    pdf.set_xy(15, 38)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(120, 11, _texto("Certificado Verde"))
    pdf.set_xy(15, 50)
    pdf.set_font("Helvetica", "", 10.5)
    pdf.set_text_color(214, 236, 222)
    pdf.cell(120, 6, _texto("Informe mensual de aprovechamiento de residuos del conjunto"))
    # sello del mes
    sello = _texto(f"{cifras.etiqueta_mes}".upper())
    pdf.set_font("Helvetica", "B", 10)
    ancho_sello = pdf.get_string_width(sello) + 12
    pdf.set_fill_color(*_SOLAR)
    pdf.rect(195 - ancho_sello, 42, ancho_sello, 11, style="F", round_corners=True, corner_radius=5.5)
    pdf.set_xy(195 - ancho_sello, 42)
    pdf.set_text_color(*_BOSQUE)
    pdf.cell(ancho_sello, 11, sello, align="C")
    pdf.set_y(70)

    # ---------------------------------------------------------------- datos del certificado
    _titulo(pdf, "Datos del certificado")
    datos = [
        ("Conjunto", cifras.conjunto_nombre),
        ("Período", f"1 al {ultimo_dia.day} de {cifras.etiqueta_mes} ({cifras.mes})"),
        ("Zona horaria", cifras.zona),
        ("Corte de datos", f"{_fecha_larga(corte)}, {_hora(corte)} (hora local)"),
    ]
    y0 = pdf.get_y()
    pdf.set_fill_color(*_FONDO)
    pdf.rect(15, y0, 180, 7 * len(datos) + 4, style="F", round_corners=True, corner_radius=3)
    pdf.set_y(y0 + 2)
    for etiqueta, valor in datos:
        pdf.set_x(20)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_GRIS)
        pdf.cell(38, 7, _texto(etiqueta))
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(*_CARBON)
        pdf.cell(130, 7, _recortar(pdf, valor, 130), new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(y0 + 7 * len(datos) + 8)

    # ---------------------------------------------------------------- indicadores
    _titulo(pdf, "Indicadores del mes")
    y = pdf.get_y()
    ancho = (180 - 3 * 4) / 4
    tarjetas = [
        (_VERDE, _fmt_kg(cifras.kg_aprovechados), "kg", "Reciclables aprovechados"),
        (_HOJA, _fmt_kg(cifras.kg_compostados), "kg", "Orgánicos compostados"),
        (_TURQUESA, str(cifras.hogares), "con entrega válida", "Hogares participantes"),
        (_MARIPOSA, cifras.tasa_pct, "del peso", "Tasa de rechazo"),
    ]
    for i, (color, valor, unidad, etiqueta) in enumerate(tarjetas):
        _tarjeta(pdf, 15 + i * (ancho + 4), y, ancho, 28, color, valor, unidad, etiqueta)
    pdf.set_y(y + 33)

    # ---------------------------------------------------------------- resumen
    _titulo(pdf, "Resumen del período")
    filas = [
        ["Kilos aprovechados (reciclables)", f"{_fmt_kg(cifras.kg_aprovechados)} kg"],
        ["Kilos compostados (orgánicos)", f"{_fmt_kg(cifras.kg_compostados)} kg"],
    ]
    if cifras.kg_otros:
        filas.append(["Kilos aceptados de otro aprovechamiento", f"{_fmt_kg(cifras.kg_otros)} kg"])
    filas += [
        ["Kilos aceptados en total", f"{_fmt_kg(cifras.kg_aceptados)} kg"],
        ["Kilos rechazados", f"{_fmt_kg(cifras.kg_rechazados)} kg"],
        ["Tasa de rechazo por peso", cifras.tasa_pct],
        ["Hogares participantes", str(cifras.hogares)],
        ["Torres con pesaje confirmado", str(cifras.torres)],
    ]
    _tabla(pdf, ["Indicador", "Valor"], [130, 50], filas, ["L", "R"])

    # ---------------------------------------------------------------- detalle por colectivo
    _titulo(pdf, "Detalle por colectivo")
    if cifras.sin_pesajes:
        _espacio(pdf, 16)
        y = pdf.get_y()
        pdf.set_fill_color(*_FONDO)
        pdf.rect(15, y, 180, 14, style="F", round_corners=True, corner_radius=3)
        pdf.set_xy(20, y + 2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*_CARBON)
        pdf.cell(170, 5, _texto("Sin pesajes confirmados en este período."), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(20)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*_GRIS)
        pdf.cell(170, 5, _texto("Los kilos aparecen cuando la coordinación confirma un pesaje con torre de origen."))
        pdf.set_y(y + 18)
    else:
        filas_g = []
        for g in cifras.gremios:
            tasa, _ = _tasa(g.kg_aceptados, g.kg_rechazados)
            filas_g.append([g.nombre, g.codigo, _ETIQUETA_TIPO[g.tipo].capitalize(),
                            _fmt_kg(g.kg_aceptados), _fmt_kg(g.kg_rechazados), tasa])
        _tabla(pdf, ["Colectivo", "Código", "Tipo", "Aceptados (kg)", "Rechazados (kg)", "Rechazo"],
               [52, 30, 24, 28, 28, 18], filas_g, ["L", "L", "L", "R", "R", "R"])

        _titulo(pdf, "Detalle por material")
        filas_m = [[m.nombre, m.codigo, m.gremio_codigo, _fmt_kg(m.kg_aceptados), _fmt_kg(m.kg_rechazados)]
                   for m in cifras.materiales]
        _tabla(pdf, ["Material", "Código", "Colectivo", "Aceptados (kg)", "Rechazados (kg)"],
               [60, 34, 30, 28, 28], filas_m, ["L", "L", "L", "R", "R"])

    # ---------------------------------------------------------------- advertencia
    _espacio(pdf, 22)
    pdf.ln(2)
    y = pdf.get_y()
    pdf.set_fill_color(255, 246, 214)
    pdf.rect(15, y, 180, 17, style="F", round_corners=True, corner_radius=3)
    pdf.set_fill_color(*_MARIPOSA)
    pdf.rect(15, y, 2.2, 17, style="F")
    pdf.set_xy(21, y + 2.5)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_text_color(110, 60, 0)
    pdf.cell(170, 5, _texto("Este certificado es apoyo documental para la tarifa multiusuario."),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(21)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(170, 5, _texto("No determina la tarifa ni sustituye el aforo de la empresa de aseo."))
    pdf.set_y(y + 21)

    # ---------------------------------------------------------------- metodología
    _titulo(pdf, "Cómo se calcula")
    puntos = [
        "Origen: pesajes confirmados con torre de origen de este conjunto.",
        "Los kilos salen de las líneas de esos pesajes, según el colectivo (gremio) del material.",
        "Reciclables: servicio RECICLABLES. Compostados: servicio ORGANICOS.",
        "Hogares: recogidas cerradas o entregas directas con pesaje confirmado.",
        "No entran borradores, pesajes anulados ni pendientes de sincronizar.",
    ]
    for punto in puntos:
        _espacio(pdf, 6)
        y = pdf.get_y()
        pdf.set_fill_color(*_VERDE)
        pdf.ellipse(17, y + 1.9, 1.6, 1.6, style="F")
        pdf.set_xy(21, y)
        pdf.set_font("Helvetica", "", 8.8)
        pdf.set_text_color(*_GRIS)
        pdf.multi_cell(174, 5, _texto(punto), new_x="LMARGIN", new_y="NEXT")

    # ---------------------------------------------------------------- emisión
    _espacio(pdf, 24)
    pdf.ln(4)
    y = pdf.get_y()
    pdf.set_draw_color(*_LINEA)
    pdf.set_line_width(0.3)
    pdf.rect(15, y, 180, 20, style="D", round_corners=True, corner_radius=3)
    pdf.set_xy(20, y + 3)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_text_color(*_BOSQUE)
    pdf.cell(170, 5, _texto("Emitido por la plataforma Brota · Programa EcoConecta Villas de San Pablo"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(20)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*_GRIS)
    pdf.cell(170, 5, _texto(f"Fecha de emisión: {_fecha_larga(corte)}, {_hora(corte)}. Fórmula {FORMULA}."),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(20)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.cell(170, 5, _texto(f"Identificador del conjunto: {cifras.conjunto_id}"))

    raw = pdf.output()
    return raw.encode("latin-1") if isinstance(raw, str) else bytes(raw)


def generar_certificado(db: Session, conjunto_id: uuid.UUID, mes: str) -> tuple[bytes, str]:
    cifras = _cifras(db, conjunto_id, mes)
    nombre = f"certificado-verde-{slug_conjunto(cifras.conjunto_nombre, cifras.conjunto_id)}-{cifras.mes}.pdf"
    return render_pdf(cifras), nombre
