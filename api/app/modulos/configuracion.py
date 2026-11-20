"""M10 · Administración y configuración versionada.

Nunca se edita una versión aplicada: crear una versión nueva cierra la vigente del mismo
concepto y ámbito en la misma transacción. Cambiar configuración no recalcula hechos pasados.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errores import AppError, invalido
from app.core.idempotencia import escritura
from app.core.paginacion import Paginacion, paginacion, paginar
from app.core.seguridad import Actor, actor_admin
from app.core.tipos import (
    DecimalEntrada,
    Entrada,
    Instante,
    InstanteEntrada,
    KgEntrada,
    KgSalida,
    PrecioSalida,
    Salida,
    ahora,
)
from app.db import get_db
from app.models import (
    CapacidadTorre,
    Conjunto,
    ContenidoEducativo,
    ContenidoMaterial,
    ContenidoMotivo,
    Gremio,
    Material,
    MotivoRechazo,
    PuntoRecepcion,
    Torre,
    VersionEquivalencia,
    VersionPrecioMaterial,
    VersionReglaIncentivo,
)
from app.modulos.comun import (
    obtener,
    referencia_activa,
    registrar_evento,
    verificar_version,
)

router = APIRouter(tags=["configuración"])


class Vigencia(Entrada):
    vigente_desde: InstanteEntrada | None = Field(default=None, description="Por defecto, ahora")
    vigente_hasta: InstanteEntrada | None = None

    @model_validator(mode="after")
    def _orden(self):
        if self.vigente_desde and self.vigente_hasta and self.vigente_hasta <= self.vigente_desde:
            raise ValueError("vigente_hasta debe ser posterior a vigente_desde")
        return self


def _cerrar_y_crear(db: Session, modelo, filtros: list, nueva) -> None:
    """Cierra la versión abierta del mismo concepto y rechaza solapamientos con versiones cerradas."""
    desde: datetime = nueva.vigente_desde
    hasta: datetime | None = nueva.vigente_hasta
    existentes = db.execute(select(modelo).where(*filtros).with_for_update()).scalars().all()
    for v in existentes:
        if v.vigente_hasta is None and v.vigente_desde < desde:
            v.vigente_hasta = desde
            continue
        fin_v = v.vigente_hasta
        solapa = (hasta is None or v.vigente_desde < hasta) and (fin_v is None or desde < fin_v)
        if solapa:
            raise AppError(409, "VIGENCIA_SOLAPADA", "Ya existe una versión vigente en ese intervalo.")
    db.add(nueva)
    db.flush()


# --------------------------------------------------------------------------- catálogos


class MaterialIn(Entrada):
    codigo: str = Field(min_length=1, max_length=40, pattern=r"^[A-Z0-9_]+$")
    nombre: str = Field(min_length=1, max_length=120)
    gremio_id: uuid.UUID


class MaterialPatch(Entrada):
    version_esperada: int
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    activo: bool | None = None


class MaterialOut(Salida):
    id: uuid.UUID
    codigo: str
    nombre: str
    gremio_id: uuid.UUID
    activo: bool
    version: int


class MotivoIn(Entrada):
    codigo: str = Field(min_length=1, max_length=40, pattern=r"^[A-Z0-9_]+$")
    nombre: str = Field(min_length=1, max_length=120)
    gremio_id: uuid.UUID | None = None


class MotivoOut(Salida):
    id: uuid.UUID
    codigo: str
    nombre: str
    gremio_id: uuid.UUID | None
    activo: bool


class ContenidoIn(Entrada):
    tema: Literal["separacion", "huerta", "horarios_rutas", "servicio"] = "separacion"
    publicado: bool = True
    titulo: str = Field(min_length=1, max_length=160)
    tipo: Literal["video", "imagen", "texto"]
    recurso: str | None = Field(default=None, max_length=500, pattern=r"^https://")
    texto: str | None = Field(default=None, max_length=2000)
    general: bool = False
    material_ids: list[uuid.UUID] = []
    motivo_rechazo_ids: list[uuid.UUID] = []


class ContenidoOut(Salida):
    tema: str
    publicado: bool
    activo: bool
    version: int
    id: uuid.UUID
    titulo: str
    tipo: str
    recurso: str | None
    texto: str | None
    general: bool
    gremio_id: uuid.UUID | None = None
    vigente_desde: Instante | None = None
    vigente_hasta: Instante | None = None


def _crear_catalogo(db: Session, obj) -> None:
    db.add(obj)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "DUPLICATE", "Ya existe un registro con ese código.") from None
    db.refresh(obj)


@router.get("/materiales")
def get_materiales(
    _actor: Actor = Depends(actor_admin),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
):
    """Catálogo completo para administración, incluidos los inactivos y su versión."""
    stmt = select(Material).order_by(Material.activo.desc(), Material.nombre, Material.id)
    return paginar(db, stmt, pag, lambda m: MaterialOut.model_validate(m).model_dump(mode="json"))


@router.post("/materiales", status_code=201)
def post_material(datos: MaterialIn, request: Request, actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)):
    def _fn():
        referencia_activa(db, Gremio, datos.gremio_id, "gremio_id", "Gremio")
        m = Material(**datos.model_dump())
        _crear_catalogo(db, m)
        registrar_evento(db, "material_creado", actor, datos={"material_id": str(m.id)})
        return MaterialOut.model_validate(m)

    return escritura(request, db, actor, datos, _fn, status=201)


@router.patch("/materiales/{material_id}")
def patch_material(
    material_id: uuid.UUID, datos: MaterialPatch, request: Request,
    actor: Actor = Depends(actor_admin), db: Session = Depends(get_db),
):
    def _fn():
        m = obtener(db, Material, material_id, "material", bloquear=True)
        verificar_version(datos.version_esperada, m.version)
        if datos.nombre is not None:
            m.nombre = datos.nombre
        if datos.activo is not None:
            m.activo = datos.activo
        m.version += 1
        db.flush()
        return MaterialOut.model_validate(m)

    return escritura(request, db, actor, datos, _fn)


@router.post("/motivos-rechazo", status_code=201)
def post_motivo(datos: MotivoIn, request: Request, actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)):
    def _fn():
        if datos.gremio_id:
            referencia_activa(db, Gremio, datos.gremio_id, "gremio_id", "Gremio")
        m = MotivoRechazo(**datos.model_dump())
        _crear_catalogo(db, m)
        return MotivoOut.model_validate(m)

    return escritura(request, db, actor, datos, _fn, status=201)


@router.post("/contenidos-educativos", status_code=201)
def post_contenido(datos: ContenidoIn, request: Request, actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)):
    def _fn():
        if datos.tipo != "texto" and not datos.recurso:
            raise invalido({"recurso": "Video o imagen requieren URL https"})
        for i, mid in enumerate(datos.material_ids):
            referencia_activa(db, Material, mid, f"material_ids.{i}", "Material")
        for i, mid in enumerate(datos.motivo_rechazo_ids):
            referencia_activa(db, MotivoRechazo, mid, f"motivo_rechazo_ids.{i}", "Motivo")
        c = ContenidoEducativo(
            tema=datos.tema, publicado=datos.publicado,
            titulo=datos.titulo, tipo=datos.tipo, recurso=datos.recurso, texto=datos.texto, general=datos.general
        )
        db.add(c)
        db.flush()
        for mid in set(datos.material_ids):
            db.add(ContenidoMaterial(contenido_id=c.id, material_id=mid))
        for mid in set(datos.motivo_rechazo_ids):
            db.add(ContenidoMotivo(contenido_id=c.id, motivo_rechazo_id=mid))
        db.flush()
        db.refresh(c)
        return ContenidoOut.model_validate(c)

    return escritura(request, db, actor, datos, _fn, status=201)


# --------------------------------------------------------------------------- versiones con vigencia


class PrecioIn(Vigencia):
    material_id: uuid.UUID
    precio_kg: DecimalEntrada
    moneda: str = Field(default="COP", pattern=r"^[A-Z]{3}$")


class PrecioOut(Salida):
    id: uuid.UUID
    material_id: uuid.UUID
    precio_kg: PrecioSalida
    moneda: str
    vigente_desde: Instante
    vigente_hasta: Instante | None


class EquivalenciaIn(Vigencia):
    gremio_id: uuid.UUID
    punto_recepcion_id: uuid.UUID | None = None
    recipiente: str = Field(min_length=1, max_length=40)
    kg_por_unidad: KgEntrada


class EquivalenciaOut(Salida):
    id: uuid.UUID
    gremio_id: uuid.UUID
    punto_recepcion_id: uuid.UUID | None
    recipiente: str
    kg_por_unidad: KgSalida
    vigente_desde: Instante
    vigente_hasta: Instante | None


class Ambito(Entrada):
    tipo: Literal["global", "gremio", "conjunto"]
    id: uuid.UUID | None = None


class ReglaIn(Vigencia):
    codigo: str = Field(min_length=1, max_length=60)
    modalidad: Literal["entrega_valida", "entrega_directa"]
    ambito: Ambito
    parametros: dict[str, Any]
    aprobada_por: str | None = Field(default=None, max_length=120)


class ReglaOut(Salida):
    id: uuid.UUID
    codigo: str
    modalidad: str
    ambito_tipo: str
    ambito_id: uuid.UUID | None
    parametros: dict[str, Any]
    vigente_desde: Instante
    vigente_hasta: Instante | None


class CapacidadIn(Vigencia):
    numero_viviendas: int = Field(gt=0, le=10000)


class CapacidadOut(Salida):
    id: uuid.UUID
    torre_id: uuid.UUID
    numero_viviendas: int
    vigente_desde: Instante
    vigente_hasta: Instante | None


def _desde(v: Vigencia) -> datetime:
    return v.vigente_desde or ahora()


@router.post("/precios-material", status_code=201)
def post_precio(datos: PrecioIn, request: Request, actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)):
    def _fn():
        referencia_activa(db, Material, datos.material_id, "material_id", "Material")
        v = VersionPrecioMaterial(
            material_id=datos.material_id, precio_kg=datos.precio_kg, moneda=datos.moneda,
            vigente_desde=_desde(datos), vigente_hasta=datos.vigente_hasta,
        )
        _cerrar_y_crear(db, VersionPrecioMaterial, [VersionPrecioMaterial.material_id == datos.material_id], v)
        registrar_evento(db, "precio_versionado", actor, datos={"material_id": str(datos.material_id)})
        return PrecioOut.model_validate(v)

    return escritura(request, db, actor, datos, _fn, status=201)


@router.post("/equivalencias", status_code=201)
def post_equivalencia(
    datos: EquivalenciaIn, request: Request, actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)
):
    def _fn():
        referencia_activa(db, Gremio, datos.gremio_id, "gremio_id", "Gremio")
        if datos.punto_recepcion_id:
            pr = referencia_activa(db, PuntoRecepcion, datos.punto_recepcion_id, "punto_recepcion_id", "Punto")
            if pr.gremio_id != datos.gremio_id:
                raise invalido({"punto_recepcion_id": "El punto es de otro gremio"})
        v = VersionEquivalencia(
            gremio_id=datos.gremio_id, punto_recepcion_id=datos.punto_recepcion_id, recipiente=datos.recipiente,
            kg_por_unidad=datos.kg_por_unidad, vigente_desde=_desde(datos), vigente_hasta=datos.vigente_hasta,
        )
        filtros = [
            VersionEquivalencia.gremio_id == datos.gremio_id,
            VersionEquivalencia.recipiente == datos.recipiente,
            VersionEquivalencia.punto_recepcion_id == datos.punto_recepcion_id
            if datos.punto_recepcion_id else VersionEquivalencia.punto_recepcion_id.is_(None),
        ]
        _cerrar_y_crear(db, VersionEquivalencia, filtros, v)
        return EquivalenciaOut.model_validate(v)

    return escritura(request, db, actor, datos, _fn, status=201)


@router.post("/reglas-incentivo", status_code=201)
def post_regla(datos: ReglaIn, request: Request, actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)):
    def _fn():
        a = datos.ambito
        if (a.tipo == "global") != (a.id is None):
            raise invalido({"ambito.id": "Obligatorio salvo ámbito global"})
        if a.tipo == "gremio":
            referencia_activa(db, Gremio, a.id, "ambito.id", "Gremio")
        if a.tipo == "conjunto":
            referencia_activa(db, Conjunto, a.id, "ambito.id", "Conjunto")
        p = datos.parametros
        if set(p) != {"puntos"} or not isinstance(p["puntos"], str):
            raise invalido({"parametros": 'Esquema v1: {"puntos": "10"} (string decimal)'})
        try:
            from decimal import Decimal

            if Decimal(p["puntos"]) <= 0:
                raise ValueError
        except Exception:
            raise invalido({"parametros.puntos": "Decimal positivo"}) from None
        v = VersionReglaIncentivo(
            codigo=datos.codigo, modalidad=datos.modalidad, ambito_tipo=a.tipo, ambito_id=a.id,
            parametros=p, vigente_desde=_desde(datos), vigente_hasta=datos.vigente_hasta,
            aprobada_por=datos.aprobada_por,
        )
        filtros = [
            VersionReglaIncentivo.modalidad == datos.modalidad,
            VersionReglaIncentivo.ambito_tipo == a.tipo,
            VersionReglaIncentivo.ambito_id == a.id if a.id else VersionReglaIncentivo.ambito_id.is_(None),
        ]
        _cerrar_y_crear(db, VersionReglaIncentivo, filtros, v)
        registrar_evento(db, "regla_incentivo_versionada", actor, datos={"codigo": datos.codigo})
        return ReglaOut.model_validate(v)

    return escritura(request, db, actor, datos, _fn, status=201)


@router.post("/torres/{torre_id}/capacidades", status_code=201)
def post_capacidad(
    torre_id: uuid.UUID, datos: CapacidadIn, request: Request,
    actor: Actor = Depends(actor_admin), db: Session = Depends(get_db),
):
    def _fn():
        obtener(db, Torre, torre_id, "torre")
        v = CapacidadTorre(
            torre_id=torre_id, numero_viviendas=datos.numero_viviendas,
            vigente_desde=_desde(datos), vigente_hasta=datos.vigente_hasta,
        )
        _cerrar_y_crear(db, CapacidadTorre, [CapacidadTorre.torre_id == torre_id], v)
        return CapacidadOut.model_validate(v)

    return escritura(request, db, actor, datos, _fn, status=201)


@router.get("/configuracion")
def get_configuracion(
    tipo: Literal["precios", "equivalencias", "reglas_incentivo", "capacidades"] = Query(...),
    fecha: InstanteEntrada | None = Query(None, description="Versiones vigentes en esa fecha; por defecto todas"),
    actor: Actor = Depends(actor_admin),
    db: Session = Depends(get_db),
):
    modelo, salida = {
        "precios": (VersionPrecioMaterial, PrecioOut),
        "equivalencias": (VersionEquivalencia, EquivalenciaOut),
        "reglas_incentivo": (VersionReglaIncentivo, ReglaOut),
        "capacidades": (CapacidadTorre, CapacidadOut),
    }[tipo]
    stmt = select(modelo).order_by(modelo.vigente_desde.desc())
    if fecha is not None:
        stmt = stmt.where(modelo.vigente_desde <= fecha, or_(modelo.vigente_hasta.is_(None), modelo.vigente_hasta > fecha))
    return {"data": [salida.model_validate(v).model_dump(mode="json") for v in db.execute(stmt).scalars()]}


class PublicacionIn(Entrada):
    version_esperada: int
    publicado: bool


class ContenidoPatch(Entrada):
    version_esperada: int
    titulo: str | None = Field(default=None, min_length=1, max_length=160)
    texto: str | None = Field(default=None, max_length=2000)
    tema: Literal["separacion", "huerta", "horarios_rutas", "servicio"] | None = None
    publicado: bool | None = None
    activo: bool | None = None
    gremio_id: uuid.UUID | None = None
    vigente_desde: InstanteEntrada | None = None
    vigente_hasta: InstanteEntrada | None = None


@router.patch("/contenidos-educativos/{contenido_id}")
def editar_contenido(contenido_id: uuid.UUID, datos: ContenidoPatch, request: Request,
    actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)):
    def ejecutar():
        c = obtener(db, ContenidoEducativo, contenido_id, "contenido", bloquear=True)
        verificar_version(datos.version_esperada, c.version)
        if datos.titulo is not None:
            c.titulo = datos.titulo
        if datos.texto is not None:
            c.texto = datos.texto
        if datos.tema is not None:
            c.tema = datos.tema
        if "gremio_id" in datos.model_fields_set:
            if datos.gremio_id is not None:
                referencia_activa(db, Gremio, datos.gremio_id, "gremio_id", "Gremio")
            c.gremio_id = datos.gremio_id
        if "vigente_desde" in datos.model_fields_set:
            c.vigente_desde = datos.vigente_desde
        if "vigente_hasta" in datos.model_fields_set:
            c.vigente_hasta = datos.vigente_hasta
        if datos.activo is False:
            c.activo = False
            c.publicado = False
        else:
            if datos.activo is True:
                c.activo = True
            if datos.publicado is True and not c.activo:
                raise invalido({"publicado": "Un contenido retirado no se publica"})
            if datos.publicado is not None:
                c.publicado = datos.publicado
        if c.vigente_desde is None and c.vigente_hasta is not None:
            raise invalido({"vigente_hasta": "Indica vigente_desde"})
        if c.vigente_desde is not None and c.vigente_hasta is not None and c.vigente_hasta <= c.vigente_desde:
            raise invalido({"vigente_hasta": "Debe ser posterior al inicio"})
        c.version += 1
        db.flush()
        return ContenidoOut.model_validate(c)
    return escritura(request, db, actor, datos, ejecutar)


@router.patch("/contenidos-educativos/{contenido_id}/publicacion")
def publicar_contenido(contenido_id: uuid.UUID, datos: PublicacionIn, request: Request,
    actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)):
    def ejecutar():
        c = obtener(db, ContenidoEducativo, contenido_id, "contenido", bloquear=True)
        verificar_version(datos.version_esperada, c.version)
        c.publicado = datos.publicado
        c.version += 1
        db.flush()
        return ContenidoOut.model_validate(c)
    return escritura(request, db, actor, datos, ejecutar)
