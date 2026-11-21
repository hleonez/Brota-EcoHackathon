"""M02 · Territorio, catálogos y recolectores."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errores import AppError, invalido, prohibido
from app.core.idempotencia import escritura
from app.core.paginacion import Paginacion, paginacion, paginar
from app.core.seguridad import Actor, actor_admin, actor_operador, get_actor
from app.core.tipos import Entrada, Instante, KgSalida, Salida, ahora
from app.db import get_db
from app.models import (
    CapacidadTorre,
    Conjunto,
    Gremio,
    Huerta,
    Material,
    MotivoRechazo,
    PuntoRecepcion,
    Recolector,
    TipoServicio,
    Torre,
    Unidad,
    VersionEquivalencia,
)
from app.modulos.comun import (
    obtener,
    referencia_activa,
    registrar_evento,
    verificar_version,
)
from app.modulos.identidad import UnidadResumen, unidad_resumen

router = APIRouter(tags=["territorio y catálogos"])

# --------------------------------------------------------------------------- esquemas


class ConjuntoOut(Salida):
    id: uuid.UUID
    nombre: str
    etapa: str | None
    activo: bool


class TorreOut(Salida):
    id: uuid.UUID
    conjunto_id: uuid.UUID
    codigo: str
    nombre: str | None
    activo: bool
    numero_viviendas: int | None = None


class UnidadIn(Entrada):
    tipo: Literal["hogar", "negocio"]
    torre_id: uuid.UUID | None = None
    referencia_local: str = Field(min_length=1, max_length=60)
    direccion_referencia: str | None = Field(default=None, max_length=200)


class CatalogoItem(Salida):
    id: uuid.UUID
    codigo: str
    nombre: str
    activo: bool


class CatalogoGremioItem(CatalogoItem):
    gremio_id: uuid.UUID


class MotivoItem(CatalogoItem):
    gremio_id: uuid.UUID | None


class EquivalenciaItem(Salida):
    id: uuid.UUID
    gremio_id: uuid.UUID
    punto_recepcion_id: uuid.UUID | None
    recipiente: str
    kg_por_unidad: KgSalida
    vigente_desde: Instante
    vigente_hasta: Instante | None


class RecolectorIn(Entrada):
    huerta_id: uuid.UUID | None = None
    tipo: Literal["reciclador", "huertero"] = "reciclador"
    gremio_id: uuid.UUID
    nombre: str = Field(min_length=1, max_length=120)
    telefono_contacto: str | None = Field(default=None, max_length=30)


class RecolectorPatch(Entrada):
    huerta_id: uuid.UUID | None = None
    version_esperada: int
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    telefono_contacto: str | None = Field(default=None, max_length=30)
    activo: bool | None = None


class RecolectorOut(Salida):
    huerta_id: uuid.UUID | None = None
    tipo: Literal["reciclador", "huertero"]
    id: uuid.UUID
    gremio_id: uuid.UUID
    nombre: str
    telefono_contacto: str | None
    activo: bool
    version: int
    created_at: Instante


# --------------------------------------------------------------------------- territorio


def _capacidad_vigente(db: Session, torre_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    t = ahora()
    filas = db.execute(
        select(CapacidadTorre.torre_id, CapacidadTorre.numero_viviendas).where(
            CapacidadTorre.torre_id.in_(torre_ids),
            CapacidadTorre.vigente_desde <= t,
            or_(CapacidadTorre.vigente_hasta.is_(None), CapacidadTorre.vigente_hasta > t),
        )
    ).all()
    return {tid: n for tid, n in filas}


@router.get("/conjuntos")
def get_conjuntos(
    actor: Actor = Depends(get_actor), pag: Paginacion = Depends(paginacion), db: Session = Depends(get_db)
):
    stmt = select(Conjunto).where(Conjunto.activo.is_(True)).order_by(Conjunto.nombre, Conjunto.id)
    return paginar(db, stmt, pag, lambda c: ConjuntoOut.model_validate(c).model_dump(mode="json"))


@router.get("/conjuntos/{conjunto_id}/torres")
def get_torres(
    conjunto_id: uuid.UUID,
    actor: Actor = Depends(get_actor),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
):
    obtener(db, Conjunto, conjunto_id, "conjunto")
    stmt = (
        select(Torre)
        .where(Torre.conjunto_id == conjunto_id, Torre.activo.is_(True))
        .order_by(func.length(Torre.codigo), Torre.codigo, Torre.id)
    )
    res = paginar(db, stmt, pag, lambda t: t)
    caps = _capacidad_vigente(db, [t.id for t in res["data"]])
    res["data"] = [
        TorreOut.model_validate(t).model_copy(update={"numero_viviendas": caps.get(t.id)}).model_dump(mode="json")
        for t in res["data"]
    ]
    return res


@router.get("/unidades/gestion")
def get_unidades_gestion(
    tipo: Literal["hogar", "negocio"] | None = Query(None),
    _actor: Actor = Depends(actor_admin),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
):
    """Listado para administración. No reemplaza el directorio de coordinación."""
    stmt = select(Unidad).where(Unidad.activo.is_(True))
    if tipo is not None:
        stmt = stmt.where(Unidad.tipo == tipo)
    stmt = stmt.order_by(Unidad.torre_id, func.length(Unidad.referencia_local), Unidad.referencia_local, Unidad.id)
    return paginar(db, stmt, pag, lambda u: unidad_resumen(u).model_dump(mode="json"))


@router.get("/unidades")
def get_unidades(
    torre_id: uuid.UUID | None = Query(None),
    tipo: Literal["hogar", "negocio"] | None = Query(None),
    referencia: str | None = Query(None, max_length=60),
    actor: Actor = Depends(get_actor),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
):
    """Operadores: búsqueda con filtros. Bot/residente: solo coincidencia exacta torre + referencia."""
    stmt = select(Unidad).where(Unidad.activo.is_(True))
    if actor.trabajador_id is not None:
        raise prohibido("Consulta la ubicación desde tus asignaciones.")
    if actor.es_operador and not actor.gremios_coordinados:
        raise prohibido("El directorio de unidades es para la coordinación.")
    if not actor.es_operador:
        if (torre_id is None and tipo != "negocio") or not referencia:
            raise AppError(
                400,
                "BAD_REQUEST",
                "Indica torre_id y referencia exacta (o tipo=negocio y referencia).",
                {"referencia": "Obligatoria para el canal"},
            )
        stmt = stmt.where(func.lower(Unidad.referencia_local) == referencia.strip().lower())
        if torre_id is not None:
            stmt = stmt.where(Unidad.torre_id == torre_id)
        else:
            stmt = stmt.where(Unidad.tipo == "negocio")
        pag = Paginacion(limit=5, offset=0)
    else:
        if torre_id is not None:
            stmt = stmt.where(Unidad.torre_id == torre_id)
        if referencia:
            stmt = stmt.where(Unidad.referencia_local.ilike(f"%{referencia.strip()}%"))
    if tipo is not None:
        stmt = stmt.where(Unidad.tipo == tipo)
    stmt = stmt.order_by(Unidad.torre_id, func.length(Unidad.referencia_local), Unidad.referencia_local, Unidad.id)
    return paginar(db, stmt, pag, lambda u: unidad_resumen(u).model_dump(mode="json"))


@router.post("/unidades", status_code=201)
def post_unidad(
    datos: UnidadIn, request: Request, actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)
):
    def _fn() -> UnidadResumen:
        if datos.tipo == "hogar" and datos.torre_id is None:
            raise invalido({"torre_id": "Un hogar requiere torre"})
        if datos.torre_id is not None:
            referencia_activa(db, Torre, datos.torre_id, "torre_id", "Torre")
        u = Unidad(**datos.model_dump())
        db.add(u)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise AppError(409, "DUPLICATE", "Ya existe esa unidad en la torre.") from None
        db.refresh(u)
        return unidad_resumen(u)

    return escritura(request, db, actor, datos, _fn, status=201)


# --------------------------------------------------------------------------- catálogos


@router.get("/catalogos")
def get_catalogos(
    gremio_id: uuid.UUID | None = Query(None), actor: Actor = Depends(get_actor), db: Session = Depends(get_db)
):
    def activos(modelo, con_gremio: bool = True):
        stmt = select(modelo).where(modelo.activo.is_(True))
        if gremio_id is not None and con_gremio:
            stmt = stmt.where(or_(modelo.gremio_id == gremio_id, modelo.gremio_id.is_(None)))
        return db.execute(stmt.order_by(modelo.nombre)).scalars().all()

    gremios = db.execute(select(Gremio).where(Gremio.activo.is_(True)).order_by(Gremio.nombre)).scalars().all()
    t = ahora()
    eq_stmt = select(VersionEquivalencia).where(
        VersionEquivalencia.vigente_desde <= t,
        or_(VersionEquivalencia.vigente_hasta.is_(None), VersionEquivalencia.vigente_hasta > t),
    )
    if gremio_id is not None:
        eq_stmt = eq_stmt.where(VersionEquivalencia.gremio_id == gremio_id)
    return {
        "data": {
            "gremios": [CatalogoItem.model_validate(g).model_dump(mode="json") for g in gremios],
            "tipos_servicio": [
                CatalogoGremioItem.model_validate(x).model_dump(mode="json") for x in activos(TipoServicio)
            ],
            "materiales": [CatalogoGremioItem.model_validate(x).model_dump(mode="json") for x in activos(Material)],
            "motivos_rechazo": [MotivoItem.model_validate(x).model_dump(mode="json") for x in activos(MotivoRechazo)],
            "puntos_recepcion": [
                CatalogoGremioItem.model_validate(x).model_dump(mode="json") for x in activos(PuntoRecepcion)
            ],
            "equivalencias": [
                EquivalenciaItem.model_validate(x).model_dump(mode="json") for x in db.execute(eq_stmt).scalars()
            ],
        }
    }


# --------------------------------------------------------------------------- recolectores


def _exigir_gestion(actor: Actor, gremio_id: uuid.UUID) -> None:
    if not (actor.es_admin or actor.coordina(gremio_id)):
        raise prohibido("Solo coordinación del gremio o administración gestiona recicladores y huerteros.")


@router.get("/recicladores")
@router.get("/huerteros")
@router.get("/recolectores", deprecated=True)
def get_recolectores(
    request: Request,
    gremio_id: uuid.UUID | None = Query(None),
    activo: bool | None = Query(None),
    actor: Actor = Depends(actor_operador),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
):
    stmt = select(Recolector)
    if request.url.path.endswith("/huerteros"):
        stmt = stmt.where(Recolector.tipo == "huertero")
    elif request.url.path.endswith("/recicladores"):
        stmt = stmt.where(Recolector.tipo == "reciclador")
    if not actor.es_admin:
        alcance = actor.gremios_coordinados
        if gremio_id is not None and gremio_id not in alcance:
            raise prohibido("Fuera de tu gremio.")
        stmt = stmt.where(Recolector.gremio_id.in_([gremio_id] if gremio_id else alcance))
    elif gremio_id is not None:
        stmt = stmt.where(Recolector.gremio_id == gremio_id)
    if activo is not None:
        stmt = stmt.where(Recolector.activo.is_(activo))
    stmt = stmt.order_by(Recolector.nombre, Recolector.id)
    return paginar(db, stmt, pag, lambda r: RecolectorOut.model_validate(r).model_dump(mode="json"))


@router.post("/recicladores", status_code=201)
@router.post("/huerteros", status_code=201)
@router.post("/recolectores", status_code=201, deprecated=True)
def post_recolector(
    datos: RecolectorIn, request: Request, actor: Actor = Depends(actor_operador), db: Session = Depends(get_db)
):
    def _fn() -> RecolectorOut:
        _exigir_gestion(actor, datos.gremio_id)
        referencia_activa(db, Gremio, datos.gremio_id, "gremio_id", "Gremio")
        valores = datos.model_dump()
        if request.url.path.endswith("/huerteros"):
            valores["tipo"] = "huertero"
        elif request.url.path.endswith("/recicladores"):
            valores["tipo"] = "reciclador"
        if valores["huerta_id"] is not None:
            huerta = referencia_activa(db, Huerta, valores["huerta_id"], "huerta_id", "Huerta")
            if valores["tipo"] != "huertero" or huerta.gremio_id != datos.gremio_id:
                raise invalido({"huerta_id": "La huerta debe pertenecer al gremio del huertero"})
        elif valores["tipo"] == "huertero":
            raise invalido({"huerta_id": "Selecciona la huerta del huertero"})
        r = Recolector(**valores)
        db.add(r)
        db.flush()
        db.refresh(r)
        registrar_evento(db, "recolector_creado", actor, datos={"recolector_id": str(r.id)})
        return RecolectorOut.model_validate(r)

    return escritura(request, db, actor, datos, _fn, status=201)


@router.patch("/recicladores/{recolector_id}")
@router.patch("/huerteros/{recolector_id}")
@router.patch("/recolectores/{recolector_id}", deprecated=True)
def patch_recolector(
    recolector_id: uuid.UUID,
    datos: RecolectorPatch,
    request: Request,
    actor: Actor = Depends(actor_operador),
    db: Session = Depends(get_db),
):
    def _fn() -> RecolectorOut:
        r = obtener(db, Recolector, recolector_id, "recolector", bloquear=True)
        _exigir_gestion(actor, r.gremio_id)
        verificar_version(datos.version_esperada, r.version)
        if "huerta_id" in datos.model_fields_set:
            h = referencia_activa(db, Huerta, datos.huerta_id, "huerta_id", "Huerta")
            if r.tipo != "huertero" or h.gremio_id != r.gremio_id:
                raise invalido({"huerta_id": "La huerta debe corresponder al gremio del huertero"})
            r.huerta_id = h.id
        for campo in ("nombre", "telefono_contacto", "activo"):
            if campo in datos.model_fields_set:
                valor = getattr(datos, campo)
                if valor is None and campo != "telefono_contacto":
                    raise invalido({campo: "No admite null"})
                setattr(r, campo, valor)
        r.version += 1
        db.flush()
        return RecolectorOut.model_validate(r)

    return escritura(request, db, actor, datos, _fn)




class HuertaIn(Entrada):
    nombre: str = Field(min_length=1, max_length=120)
    ubicacion: str = Field(min_length=1, max_length=200)
    gremio_id: uuid.UUID

class HuertaOut(Salida):
    id: uuid.UUID
    nombre: str
    ubicacion: str
    gremio_id: uuid.UUID
    activo: bool
    version: int

class HuertaPatch(Entrada):
    version_esperada: int
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    ubicacion: str | None = Field(default=None, min_length=1, max_length=200)
    activo: bool | None = None

@router.get("/huertas")
def listar_huertas(actor: Actor = Depends(actor_operador), db: Session = Depends(get_db), pag: Paginacion = Depends(paginacion)):
    stmt = select(Huerta)
    if not actor.es_admin:
        stmt = stmt.where(Huerta.gremio_id.in_(actor.gremios_coordinados))
    return paginar(db, stmt.order_by(Huerta.nombre, Huerta.id), pag, lambda h: HuertaOut.model_validate(h).model_dump(mode="json"))

@router.post("/huertas", status_code=201)
def crear_huerta(datos: HuertaIn, request: Request, actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)):
    def ejecutar():
        referencia_activa(db, Gremio, datos.gremio_id, "gremio_id", "Gremio")
        h = Huerta(**datos.model_dump())
        db.add(h)
        db.flush()
        return HuertaOut.model_validate(h)
    return escritura(request, db, actor, datos, ejecutar, status=201)

@router.patch("/huertas/{id}")
def actualizar_huerta(id: uuid.UUID, datos: HuertaPatch, request: Request, actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)):
    def ejecutar():
        h = obtener(db, Huerta, id, "huerta", bloquear=True)
        verificar_version(datos.version_esperada, h.version)
        for campo in ("nombre", "ubicacion", "activo"):
            if campo in datos.model_fields_set:
                valor = getattr(datos, campo)
                if valor is None:
                    raise invalido({campo: "No admite null"})
                setattr(h, campo, valor)
        h.version += 1
        db.flush()
        return HuertaOut.model_validate(h)
    return escritura(request, db, actor, datos, ejecutar)
