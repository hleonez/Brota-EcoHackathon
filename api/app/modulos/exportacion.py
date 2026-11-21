"""Excel institucional del periodo. Misma cohorte que GET /reportes/resumen.

Hojas agregadas, sin identificadores de contacto: ni celular, ni teléfono,
ni apartamento, ni nombre de quien pidió la recolección.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errores import invalido, prohibido
from app.core.seguridad import Actor
from app.core.tipos import InstanteEntrada, zona

_INSTANTE = TypeAdapter(InstanteEntrada)
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def media_type() -> str:
    return _XLSX


def leer_instante(valor: str, campo: str) -> datetime:
    """El mismo tipo que el resumen (instante con zona). Un valor mal formado es 422."""
    try:
        return _INSTANTE.validate_python(valor)
    except ValidationError:
        raise invalido({campo: "Usa un instante con zona, por ejemplo 2026-11-01T00:00:00-05:00"}) from None


def exigir_exportacion(actor: Actor) -> None:
    if actor.es_fundacion or actor.es_admin:
        return
    raise prohibido("El Excel es el informe institucional. Lo descarga la Fundación o la administración.")


def _fecha_local(dt: datetime) -> str:
    return dt.astimezone(zona(get_settings().zona_horaria)).date().isoformat()


def generar_exportacion(
    db: Session,
    actor: Actor,
    desde_raw: str,
    hasta_raw: str,
    conjunto_id: uuid.UUID | None,
) -> tuple[bytes, str]:
    exigir_exportacion(actor)
    desde = leer_instante(desde_raw, "desde")
    hasta = leer_instante(hasta_raw, "hasta")
    # Import perezoso: reportes importa este módulo al atender la ruta.
    from app.modulos.reportes import _contar_hogares, _filas_material, _kg, _ordenes_por_estado, _periodo, _torres_filtro

    _periodo(desde, hasta)
    torres = _torres_filtro(db, conjunto_id, None)
    ordenes = _ordenes_por_estado(db, desde, hasta, None, torres)
    filas = _filas_material(db, desde, hasta, None, torres)
    hogares = _contar_hogares(db, desde, hasta, torres, None)

    libro = Workbook()
    libro.properties.creator = "Brota"
    libro.properties.title = "Reporte del periodo"
    hoja_ordenes = libro.active
    hoja_ordenes.title = "Ordenes"
    hoja_ordenes.append(["Estado", "Cantidad"])
    for estado, cantidad in ordenes.items():
        hoja_ordenes.append([estado, cantidad])

    hoja_materiales = libro.create_sheet("Materiales")
    hoja_materiales.append(["Codigo", "Material", "Kg aceptados", "Kg rechazados"])
    for _mid, codigo, nombre, _gid, aceptados, rechazados, *_resto in filas:
        hoja_materiales.append([codigo, nombre, _kg(aceptados), _kg(rechazados)])

    hoja_hogares = libro.create_sheet("Hogares")
    hoja_hogares.append(["Indicador", "Cantidad"])
    hoja_hogares.append(["Hogares participantes", hogares])

    salida = BytesIO()
    libro.save(salida)
    nombre = f"reporte-{_fecha_local(desde)}-{_fecha_local(hasta)}.xlsx"
    return salida.getvalue(), nombre
