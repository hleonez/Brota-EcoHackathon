"""M09 · Liga de Torres, resumen, serie y cierre (certificado, hoja de ruta, Excel).

Reglas de cálculo:
- Solo pesajes confirmados (no borradores ni anulados); cada línea se suma una vez.
- Kilos de báscula y estimados por baldes se informan por separado.
- Kilos por torre solo con procedencia comprobada (`torre_origen_id`); el resto se informa sin torre.
- Tasas sin denominador = null (no 0 %).
- Valor estimado = kg aceptados × precio aplicado; no es un pago certificado.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import and_, case, distinct, func, or_, select, union
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errores import AppError, prohibido
from app.core.seguridad import Actor, get_actor
from app.core.tipos import InstanteEntrada, ahora
from app.db import get_db
from app.models import (
    CapacidadTorre,
    Conjunto,
    EntregaDirecta,
    LineaPesaje,
    Material,
    Orden,
    Pesaje,
    ResultadoOrden,
    Solicitud,
    Torre,
    Unidad,
)
from app.modulos.certificado import generar_certificado
from app.modulos.comun import obtener

router = APIRouter(tags=["liga y reportes"])

ESTADOS = ("nueva", "asignada", "programada", "recogida", "rechazada", "cancelada")
FORMULA_LIGA = "participacion_hogares_v1"


def _kg(d: Decimal | None) -> str:
    return f"{Decimal(d or 0):.3f}"


def _dinero(d: Decimal | None) -> str | None:
    return None if d is None else f"{Decimal(d):.2f}"


def _periodo(desde: datetime, hasta: datetime) -> dict:
    if desde >= hasta:
        raise AppError(400, "BAD_REQUEST", "desde debe ser anterior a hasta.", {"desde": "desde < hasta"})
    return {"desde": desde.isoformat(), "hasta": hasta.isoformat()}


def _alcance_gremios(actor: Actor, gremio_id: uuid.UUID | None) -> list[uuid.UUID] | None:
    """None = sin restricción (Fundación/administración). Coordinación queda en sus gremios."""
    if actor.es_fundacion or actor.es_admin:
        return [gremio_id] if gremio_id else None
    if actor.gremios_coordinados:
        if gremio_id is not None and gremio_id not in actor.gremios_coordinados:
            raise prohibido("Fuera de tu gremio.")
        return [gremio_id] if gremio_id else list(actor.gremios_coordinados)
    raise prohibido("Los reportes son para coordinación, Fundación o administración.")


def _hogares_participantes(
    db: Session, desde: datetime, hasta: datetime, torre_ids: list[uuid.UUID] | None = None,
    gremios: list[uuid.UUID] | None = None,
):
    """Unidades tipo hogar con entrega válida en el periodo: recogida confirmada o entrega directa confirmada."""
    q1 = (
        select(Unidad.id.label("unidad_id"), Unidad.torre_id.label("torre_id"))
        .join(Solicitud, Solicitud.unidad_id == Unidad.id)
        .join(Orden, Orden.solicitud_id == Solicitud.id)
        .join(ResultadoOrden, ResultadoOrden.orden_id == Orden.id)
        .where(
            ResultadoOrden.resultado == "recogida",
            ResultadoOrden.ocurrido_at >= desde,
            ResultadoOrden.ocurrido_at < hasta,
            Unidad.tipo == "hogar",
        )
    )
    q2 = (
        select(Unidad.id.label("unidad_id"), Unidad.torre_id.label("torre_id"))
        .join(EntregaDirecta, EntregaDirecta.unidad_id == Unidad.id)
        .join(Pesaje, Pesaje.id == EntregaDirecta.pesaje_id)
        .where(
            Pesaje.estado == "confirmado",
            Pesaje.fecha_medicion >= desde,
            Pesaje.fecha_medicion < hasta,
            Unidad.tipo == "hogar",
        )
    )
    if gremios is not None:
        q1 = q1.where(Orden.gremio_id.in_(gremios))
        q2 = q2.where(Pesaje.gremio_id.in_(gremios))
    if torre_ids is not None:
        q1 = q1.where(Unidad.torre_id.in_(torre_ids))
        q2 = q2.where(Unidad.torre_id.in_(torre_ids))
    return union(q1, q2).subquery()


def _torres_filtro(
    db: Session, conjunto_id: uuid.UUID | None, torre_id: uuid.UUID | None,
) -> list[uuid.UUID] | None:
    """None = sin filtro territorial. Lista (aunque vacía) = torres del conjunto o la torre pedida."""
    if torre_id is not None:
        return [torre_id]
    if conjunto_id is not None:
        return list(db.execute(select(Torre.id).where(Torre.conjunto_id == conjunto_id)).scalars())
    return None


def _ordenes_por_estado(
    db: Session,
    desde: datetime,
    hasta: datetime,
    gremios: list[uuid.UUID] | None,
    torres_filtro: list[uuid.UUID] | None,
) -> dict[str, int]:
    """Cohorte por fecha de creación. Incluye cada estado, también en cero."""
    q = select(Orden.estado, func.count()).join(Solicitud, Solicitud.id == Orden.solicitud_id).join(
        Unidad, Unidad.id == Solicitud.unidad_id
    ).where(Orden.created_at >= desde, Orden.created_at < hasta)
    if gremios is not None:
        q = q.where(Orden.gremio_id.in_(gremios))
    if torres_filtro is not None:
        q = q.where(Unidad.torre_id.in_(torres_filtro))
    conteos = dict(db.execute(q.group_by(Orden.estado)).all())
    return {e: int(conteos.get(e, 0)) for e in ESTADOS}


def _filas_material(
    db: Session,
    desde: datetime,
    hasta: datetime,
    gremios: list[uuid.UUID] | None,
    torres_filtro: list[uuid.UUID] | None,
    material_id: uuid.UUID | None = None,
    recolector_id: uuid.UUID | None = None,
):
    """Líneas de pesajes confirmados, agrupadas por material. Misma cohorte que el resumen."""
    filtros = [Pesaje.estado == "confirmado", Pesaje.fecha_medicion >= desde, Pesaje.fecha_medicion < hasta]
    if gremios is not None:
        filtros.append(Pesaje.gremio_id.in_(gremios))
    if torres_filtro is not None:
        filtros.append(Pesaje.torre_origen_id.in_(torres_filtro))
    if material_id is not None:
        filtros.append(LineaPesaje.material_id == material_id)
    if recolector_id is not None:
        filtros.append(Pesaje.recolector_id == recolector_id)
    es_bascula = LineaPesaje.metodo_medicion == "bascula"
    return db.execute(
        select(
            Material.id,
            Material.codigo,
            Material.nombre,
            Material.gremio_id,
            func.sum(LineaPesaje.kg_aceptados),
            func.sum(LineaPesaje.kg_rechazados),
            func.sum(case((es_bascula, LineaPesaje.kg_aceptados + LineaPesaje.kg_rechazados), else_=0)),
            func.sum(case((es_bascula, 0), else_=LineaPesaje.kg_aceptados + LineaPesaje.kg_rechazados)),
            func.sum(LineaPesaje.kg_aceptados * LineaPesaje.precio_kg_aplicado),
            func.sum(case((LineaPesaje.precio_kg_aplicado.is_(None), LineaPesaje.kg_aceptados), else_=0)),
            func.sum(case((Pesaje.torre_origen_id.is_(None), LineaPesaje.kg_aceptados), else_=0)),
        )
        .join(Pesaje, Pesaje.id == LineaPesaje.pesaje_id)
        .join(Material, Material.id == LineaPesaje.material_id)
        .where(*filtros)
        .group_by(Material.id, Material.codigo, Material.nombre, Material.gremio_id)
        .order_by(Material.nombre)
    ).all()


def _contar_hogares(
    db: Session,
    desde: datetime,
    hasta: datetime,
    torres_filtro: list[uuid.UUID] | None,
    gremios: list[uuid.UUID] | None,
) -> int:
    hp = _hogares_participantes(db, desde, hasta, torres_filtro, gremios)
    return int(db.execute(select(func.count(distinct(hp.c.unidad_id)))).scalar_one())


@router.get("/reportes/resumen")
def get_resumen(
    desde: InstanteEntrada = Query(...),
    hasta: InstanteEntrada = Query(...),
    gremio_id: uuid.UUID | None = Query(None),
    conjunto_id: uuid.UUID | None = Query(None),
    torre_id: uuid.UUID | None = Query(None),
    material_id: uuid.UUID | None = Query(None),
    recolector_id: uuid.UUID | None = Query(None),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    periodo = _periodo(desde, hasta)
    gremios = _alcance_gremios(actor, gremio_id)
    torres_filtro = _torres_filtro(db, conjunto_id, torre_id)
    ordenes_por_estado = _ordenes_por_estado(db, desde, hasta, gremios, torres_filtro)

    # Resultados (cohorte por fecha en que ocurrió)
    q = (
        select(ResultadoOrden.resultado, func.count())
        .join(Orden, Orden.id == ResultadoOrden.orden_id)
        .join(Solicitud, Solicitud.id == Orden.solicitud_id)
        .join(Unidad, Unidad.id == Solicitud.unidad_id)
        .where(ResultadoOrden.ocurrido_at >= desde, ResultadoOrden.ocurrido_at < hasta)
    )
    if gremios is not None:
        q = q.where(Orden.gremio_id.in_(gremios))
    if torres_filtro is not None:
        q = q.where(Unidad.torre_id.in_(torres_filtro))
    res = dict(db.execute(q.group_by(ResultadoOrden.resultado)).all())
    recogidas, rechazadas = int(res.get("recogida", 0)), int(res.get("rechazada", 0))
    tasa_ordenes = None if recogidas + rechazadas == 0 else round(rechazadas / (recogidas + rechazadas), 4)

    # Material (cohorte por fecha de medición; solo confirmados)
    filas = _filas_material(db, desde, hasta, gremios, torres_filtro, material_id, recolector_id)
    materiales = []
    tot_a = tot_r = tot_sin_torre = Decimal(0)
    valor_total: Decimal | None = None
    for mid, cod, nom, gid, a, r, kb, ke, valor, sin_precio, sin_torre in filas:
        tot_a += a or 0
        tot_r += r or 0
        tot_sin_torre += sin_torre or 0
        if valor is not None:
            valor_total = (valor_total or Decimal(0)) + valor
        materiales.append(
            {
                "material_id": str(mid),
                "codigo": cod,
                "nombre": nom,
                "gremio_id": str(gid),
                "kg_aceptados": _kg(a),
                "kg_rechazados": _kg(r),
                "kg_bascula": _kg(kb),
                "kg_estimados": _kg(ke),
                "kg_sin_precio": _kg(sin_precio),
                "valor_estimado": _dinero(valor),
            }
        )
    total_kg = tot_a + tot_r
    tasa_peso = None if total_kg == 0 else round(float(tot_r / total_kg), 4)

    hogares = _contar_hogares(db, desde, hasta, torres_filtro, gremios)

    return {
        "data": {
            "periodo": periodo,
            "corte_datos": ahora().isoformat(),
            "ordenes_por_estado": ordenes_por_estado,
            "resultados": {"recogidas": recogidas, "rechazadas": rechazadas},
            "tasa_rechazo_ordenes": tasa_ordenes,
            "materiales": materiales,
            "kg_aceptados": _kg(tot_a),
            "kg_rechazados": _kg(tot_r),
            "kg_sin_torre_identificada": _kg(tot_sin_torre) if torres_filtro is None else None,
            "tasa_rechazo_peso": tasa_peso,
            "valor_estimado": _dinero(valor_total),
            "hogares_participantes": int(hogares),
            "cobertura": {
                "ordenes": "creadas en el periodo",
                "resultados": "ocurridos en el periodo",
                "pesajes": "confirmados no anulados, por fecha de medición",
                "territorio": (
                    "solo pesajes con torre de origen comprobada" if torres_filtro is not None
                    else "todos los pesajes; los kg sin torre se informan aparte"
                ),
                "valor_estimado": "kg aceptados × precio aplicado; no es un pago certificado",
                "alcance": "gremios propios" if not (actor.es_fundacion or actor.es_admin) else "institucional",
            },
        }
    }


@router.get("/reportes/serie")
def get_serie(
    desde: InstanteEntrada = Query(...),
    hasta: InstanteEntrada = Query(...),
    agrupacion: Literal["dia", "semana", "mes"] = Query("mes"),
    gremio_id: uuid.UUID | None = Query(None),
    material_id: uuid.UUID | None = Query(None),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    """Kilos por periodo local (America/Bogota) para gráficas del panel."""
    periodo = _periodo(desde, hasta)
    gremios = _alcance_gremios(actor, gremio_id)
    tz = get_settings().zona_horaria
    trunc = {"dia": "day", "semana": "week", "mes": "month"}[agrupacion]
    local = func.timezone(tz, Pesaje.fecha_medicion)
    bucket = func.date_trunc(trunc, local).label("inicio")
    q = (
        select(bucket, func.sum(LineaPesaje.kg_aceptados), func.sum(LineaPesaje.kg_rechazados))
        .join(Pesaje, Pesaje.id == LineaPesaje.pesaje_id)
        .where(Pesaje.estado == "confirmado", Pesaje.fecha_medicion >= desde, Pesaje.fecha_medicion < hasta)
        .group_by(bucket)
        .order_by(bucket)
    )
    if gremios is not None:
        q = q.where(Pesaje.gremio_id.in_(gremios))
    if material_id is not None:
        q = q.where(LineaPesaje.material_id == material_id)
    puntos = [
        {"inicio_local": inicio.date().isoformat(), "kg_aceptados": _kg(a), "kg_rechazados": _kg(r)}
        for inicio, a, r in db.execute(q).all()
    ]
    return {"data": {"periodo": periodo, "agrupacion": agrupacion, "zona_horaria": tz, "serie": puntos}}


@router.get("/liga")
def get_liga(
    conjunto_id: uuid.UUID = Query(...),
    desde: InstanteEntrada = Query(...),
    hasta: InstanteEntrada = Query(...),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
):
    """Ranking por % de hogares que participan (sin nombres, celulares ni apartamentos).

    Denominador: viviendas vigentes de cada torre al cierre del periodo (`hasta`).
    """
    periodo = _periodo(desde, hasta)
    obtener(db, Conjunto, conjunto_id, "conjunto")
    corte = min(hasta, ahora())
    torres = db.execute(
        select(Torre.id, Torre.codigo, Torre.nombre, CapacidadTorre.numero_viviendas)
        .outerjoin(
            CapacidadTorre,
            and_(
                CapacidadTorre.torre_id == Torre.id,
                CapacidadTorre.vigente_desde <= corte,
                or_(CapacidadTorre.vigente_hasta.is_(None), CapacidadTorre.vigente_hasta > corte),
            ),
        )
        .where(Torre.conjunto_id == conjunto_id, Torre.activo.is_(True))
    ).all()
    con_base = [t for t in torres if t.numero_viviendas]
    if not con_base:
        raise AppError(
            409, "LIGA_NOT_CONFIGURED", "La Liga necesita el número de viviendas de cada torre antes de publicarse."
        )
    ids = [t.id for t in con_base]
    hp = _hogares_participantes(db, desde, hasta, ids)
    participantes = dict(
        db.execute(select(hp.c.torre_id, func.count(distinct(hp.c.unidad_id))).group_by(hp.c.torre_id)).all()
    )
    kg = dict(
        db.execute(
            select(Pesaje.torre_origen_id, func.sum(LineaPesaje.kg_aceptados))
            .join(LineaPesaje, LineaPesaje.pesaje_id == Pesaje.id)
            .where(
                Pesaje.estado == "confirmado",
                Pesaje.fecha_medicion >= desde,
                Pesaje.fecha_medicion < hasta,
                Pesaje.torre_origen_id.in_(ids),
            )
            .group_by(Pesaje.torre_origen_id)
        ).all()
    )
    filas = []
    for t in con_base:
        n = int(participantes.get(t.id, 0))
        pct = Decimal(n * 100) / Decimal(t.numero_viviendas)
        filas.append(
            {
                "torre_id": str(t.id),
                "torre_codigo": t.codigo,
                "torre_nombre": t.nombre or f"Torre {t.codigo}",
                "hogares_participantes": n,
                "viviendas_base": t.numero_viviendas,
                "porcentaje_participacion": f"{pct:.2f}",
                "kg_aceptados_atribuidos": _kg(kg.get(t.id)),
                "_orden": (-pct, -(kg.get(t.id) or 0), t.codigo),
            }
        )
    filas.sort(key=lambda f: f.pop("_orden"))
    for i, f in enumerate(filas, start=1):
        f["posicion"] = i
    return {
        "data": {
            "conjunto_id": str(conjunto_id),
            "periodo": periodo,
            "formula": FORMULA_LIGA,
            "descripcion_formula": "hogares distintos con entrega válida / viviendas vigentes × 100; desempate por kg atribuidos",
            "calculado_at": ahora().isoformat(),
            "torres": filas,
            "torres_sin_base": [
                {"torre_id": str(t.id), "torre_codigo": t.codigo} for t in torres if not t.numero_viviendas
            ],
            "cobertura": "kg solo de pesajes con torre de origen comprobada",
        }
    }


@router.get(
    "/reportes/certificado",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "PDF del Certificado Verde"}},
)
def get_certificado(
    conjunto_id: uuid.UUID = Query(...),
    mes: str = Query(..., description="Mes calendario AAAA-MM"),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
) -> Response:
    """PDF mensual por conjunto. Apoyo documental: no determina la tarifa ni sustituye el aforo.

    Solo Fundación o administración. La coordinación no ve el cruce de gremios de este informe.
    """
    if not (actor.es_fundacion or actor.es_admin):
        raise prohibido(
            "El Certificado Verde reúne todos los gremios del conjunto. Lo emite la Fundación o la administración."
        )
    contenido, nombre = generar_certificado(db, conjunto_id, mes)
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get(
    "/reportes/hoja-ruta",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "PDF de la hoja de ruta del día"}},
)
def get_hoja_ruta(
    gremio_id: uuid.UUID = Query(...),
    fecha: str = Query(..., description="Día AAAA-MM-DD en America/Bogota"),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
) -> Response:
    """Paradas programadas de ese gremio. Coordinación del gremio o administración."""
    from app.modulos.hoja_ruta import generar_hoja_ruta

    contenido, nombre = generar_hoja_ruta(db, actor, gremio_id, fecha)
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get(
    "/reportes/exportacion",
    response_class=Response,
    responses={
        200: {
            "content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}},
            "description": "Excel del periodo",
        }
    },
)
def get_exportacion(
    desde: str = Query(..., description="InstanteEntrada inclusive, con zona"),
    hasta: str = Query(..., description="InstanteEntrada exclusivo, con zona"),
    conjunto_id: uuid.UUID | None = Query(None),
    actor: Actor = Depends(get_actor),
    db: Session = Depends(get_db),
) -> Response:
    """Informe institucional del periodo. Fundación o administración. Sin datos de contacto."""
    from app.modulos.exportacion import generar_exportacion, media_type

    contenido, nombre = generar_exportacion(db, actor, desde, hasta, conjunto_id)
    return Response(
        content=contenido,
        media_type=media_type(),
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


