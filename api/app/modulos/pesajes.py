"""M05 · Pesajes, baldes y entregas directas.

borrador → confirmado → anulado (por corrección)

- Todo origen pasa por confirmación explícita; solo los confirmados cuentan en reportes.
- Vincular órdenes a un lote NO reparte kilos por hogar.
- `torre_origen_id` y `unidad_medida_id` exigen procedencia coherente con las órdenes enlazadas.
- Baldes: se conserva la cantidad original y la equivalencia aplicada; los kg se marcan como estimación.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Union

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errores import (
    invalido,
    no_encontrado,
    prohibido,
    transicion_invalida,
)
from app.core.idempotencia import escritura
from app.core.paginacion import Paginacion, paginacion, paginar
from app.core.seguridad import Actor, actor_operador
from app.core.tipos import (
    Entrada,
    Instante,
    InstanteEntrada,
    KgEntrada,
    KgSalida,
    PrecioSalida,
    Salida,
    ahora,
    redondear_kg,
)
from app.db import get_db
from app.models import (
    Asignacion,
    EntregaDirecta,
    Gremio,
    LineaPesaje,
    Material,
    MotivoRechazo,
    Orden,
    Participante,
    Pesaje,
    PesajeOrden,
    PuntoRecepcion,
    Recolector,
    Solicitud,
    Torre,
    Unidad,
    VersionEquivalencia,
    VersionPrecioMaterial,
    VinculoUnidad,
    pesaje_codigo_seq,
)
from app.modulos import puntos as puntos_srv
from app.modulos.comun import (
    encolar_aviso,
    referencia_activa,
    registrar_evento,
    verificar_version,
)

router = APIRouter(tags=["pesajes"])

# --------------------------------------------------------------------------- esquemas


class LineaBascula(Entrada):
    material_id: uuid.UUID
    metodo_medicion: Literal["bascula"]
    kg_aceptados: KgEntrada
    kg_rechazados: KgEntrada
    motivo_rechazo_id: uuid.UUID | None = None


class LineaBalde(Entrada):
    material_id: uuid.UUID
    metodo_medicion: Literal["conversion_balde"]
    cantidad_aceptada: KgEntrada
    cantidad_rechazada: KgEntrada
    version_equivalencia_id: uuid.UUID
    motivo_rechazo_id: uuid.UUID | None = None


LineaIn = Annotated[Union[LineaBascula, LineaBalde], Field(discriminator="metodo_medicion")]


class _CamposPesaje(Entrada):
    gremio_id: uuid.UUID
    fecha_medicion: InstanteEntrada
    origen_captura: Literal["manual", "baldes"]
    recolector_id: uuid.UUID | None = None
    lineas: list[LineaIn] = Field(min_length=1, max_length=30)
    proveedor_referencia: str | None = Field(default=None, max_length=120)
    numero_tiquete: str | None = Field(default=None, max_length=40)
    emisor_tiquete: str | None = Field(default=None, max_length=120)
    observacion: str | None = Field(default=None, max_length=500)


class PesajeIn(_CamposPesaje):
    orden_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    torre_origen_id: uuid.UUID | None = None
    unidad_medida_id: uuid.UUID | None = None


class PesajePatch(Entrada):
    version_esperada: int
    fecha_medicion: InstanteEntrada | None = None
    recolector_id: uuid.UUID | None = None
    orden_ids: list[uuid.UUID] | None = Field(default=None, max_length=200)
    lineas: list[LineaIn] | None = Field(default=None, min_length=1, max_length=30)
    proveedor_referencia: str | None = Field(default=None, max_length=120)
    numero_tiquete: str | None = Field(default=None, max_length=40)
    emisor_tiquete: str | None = Field(default=None, max_length=120)
    torre_origen_id: uuid.UUID | None = None
    unidad_medida_id: uuid.UUID | None = None
    observacion: str | None = Field(default=None, max_length=500)


class ConfirmacionIn(Entrada):
    version_esperada: int


class CorreccionIn(Entrada):
    version_esperada: int
    motivo: str = Field(min_length=3, max_length=500)
    pesaje_reemplazo: PesajeIn


class PesajeEntregaIn(_CamposPesaje):
    pass


class EntregaDirectaIn(Entrada):
    punto_recepcion_id: uuid.UUID
    unidad_id: uuid.UUID | None = None
    participante_id: uuid.UUID | None = None
    pesaje: PesajeEntregaIn


class LineaOut(Salida):
    id: uuid.UUID
    material_id: uuid.UUID
    material_nombre: str
    metodo_medicion: str
    estimacion: bool
    kg_aceptados: KgSalida
    kg_rechazados: KgSalida
    motivo_rechazo_id: uuid.UUID | None
    cantidad_aceptada: KgSalida | None = None
    cantidad_rechazada: KgSalida | None = None
    version_equivalencia_id: uuid.UUID | None = None
    kg_por_unidad: KgSalida | None = None
    precio_kg_aplicado: PrecioSalida | None = None
    valor_estimado: PrecioSalida | None = None


class TotalesOut(Salida):
    kg_aceptados: KgSalida
    kg_rechazados: KgSalida
    valor_estimado: PrecioSalida | None
    kg_sin_precio: KgSalida


class PesajeOut(Salida):
    id: uuid.UUID
    codigo: str
    created_at: Instante
    version: int
    estado: str
    gremio_id: uuid.UUID
    recolector_id: uuid.UUID | None
    recolector_nombre: str | None
    fecha_medicion: Instante
    origen_captura: str
    orden_ids: list[uuid.UUID]
    torre_origen_id: uuid.UUID | None
    unidad_medida_id: uuid.UUID | None
    proveedor_referencia: str | None
    numero_tiquete: str | None
    emisor_tiquete: str | None
    observacion: str | None
    confirmado_at: Instante | None
    sustituye_pesaje_id: uuid.UUID | None
    motivo_correccion: str | None
    entrega_directa_id: uuid.UUID | None = None
    lineas: list[LineaOut]
    totales: TotalesOut
    advertencias: list[str] = []
    evaluacion_puntos: str | None = None


# --------------------------------------------------------------------------- validación


@dataclass
class DatosPesaje:
    gremio_id: uuid.UUID
    fecha_medicion: datetime
    origen_captura: str
    recolector_id: uuid.UUID | None
    lineas: list[LineaBascula | LineaBalde]
    orden_ids: list[uuid.UUID] = field(default_factory=list)
    torre_origen_id: uuid.UUID | None = None
    unidad_medida_id: uuid.UUID | None = None
    proveedor_referencia: str | None = None
    numero_tiquete: str | None = None
    emisor_tiquete: str | None = None
    observacion: str | None = None

    @classmethod
    def de_entrada(cls, d: _CamposPesaje) -> DatosPesaje:
        extra = {}
        if isinstance(d, PesajeIn):
            extra = dict(orden_ids=d.orden_ids, torre_origen_id=d.torre_origen_id, unidad_medida_id=d.unidad_medida_id)
        return cls(
            gremio_id=d.gremio_id,
            fecha_medicion=d.fecha_medicion,
            origen_captura=d.origen_captura,
            recolector_id=d.recolector_id,
            lineas=list(d.lineas),
            proveedor_referencia=d.proveedor_referencia,
            numero_tiquete=d.numero_tiquete,
            emisor_tiquete=d.emisor_tiquete,
            observacion=d.observacion,
            **extra,
        )

    @classmethod
    def de_pesaje(cls, p: Pesaje) -> DatosPesaje:
        lineas: list[LineaBascula | LineaBalde] = []
        for l in p.lineas:
            if l.metodo_medicion == "bascula":
                lineas.append(
                    LineaBascula.model_construct(
                        material_id=l.material_id, metodo_medicion="bascula", kg_aceptados=l.kg_aceptados,
                        kg_rechazados=l.kg_rechazados, motivo_rechazo_id=l.motivo_rechazo_id,
                    )
                )
            else:
                lineas.append(
                    LineaBalde.model_construct(
                        material_id=l.material_id, metodo_medicion="conversion_balde",
                        cantidad_aceptada=l.cantidad_aceptada, cantidad_rechazada=l.cantidad_rechazada,
                        version_equivalencia_id=l.version_equivalencia_id, motivo_rechazo_id=l.motivo_rechazo_id,
                    )
                )
        return cls(
            gremio_id=p.gremio_id,
            fecha_medicion=p.fecha_medicion,
            origen_captura=p.origen_captura,
            recolector_id=p.recolector_id,
            lineas=lineas,
            orden_ids=[po.orden_id for po in p.ordenes],
            torre_origen_id=p.torre_origen_id,
            unidad_medida_id=p.unidad_medida_id,
            proveedor_referencia=p.proveedor_referencia,
            numero_tiquete=p.numero_tiquete,
            emisor_tiquete=p.emisor_tiquete,
            observacion=p.observacion,
        )


@dataclass
class LineaCalculada:
    material_id: uuid.UUID
    metodo_medicion: str
    kg_aceptados: Decimal
    kg_rechazados: Decimal
    motivo_rechazo_id: uuid.UUID | None
    cantidad_aceptada: Decimal | None = None
    cantidad_rechazada: Decimal | None = None
    version_equivalencia_id: uuid.UUID | None = None
    precio_kg_aplicado: Decimal | None = None
    version_precio_id: uuid.UUID | None = None


def _vigente(modelo, en: datetime):
    return (modelo.vigente_desde <= en) & or_(modelo.vigente_hasta.is_(None), modelo.vigente_hasta > en)


def validar(
    db: Session,
    actor: Actor,
    d: DatosPesaje,
    *,
    recolector_obligatorio: bool,
    excluir_pesaje_id: uuid.UUID | None = None,
) -> tuple[list[LineaCalculada], list[str], DatosPesaje]:
    errores: dict[str, str] = {}
    referencia_activa(db, Gremio, d.gremio_id, "gremio_id", "Gremio")
    actor.exigir_coordinacion(d.gremio_id)
    if d.fecha_medicion > ahora() + timedelta(minutes=5):
        errores["fecha_medicion"] = "No puede estar en el futuro"

    # Recolector
    if d.recolector_id is None:
        if recolector_obligatorio or d.orden_ids:
            errores["recolector_id"] = "Indica el recolector del lote"
    else:
        r = db.get(Recolector, d.recolector_id)
        if r is None or not r.activo:
            errores["recolector_id"] = "Recolector inexistente o inactivo"
        elif r.gremio_id != d.gremio_id:
            errores["recolector_id"] = "El recolector no pertenece al gremio"

    # Órdenes de procedencia
    if len(set(d.orden_ids)) != len(d.orden_ids):
        errores["orden_ids"] = "Órdenes repetidas"
    unidades_ordenes: set[uuid.UUID] = set()
    torres_ordenes: set[uuid.UUID | None] = set()
    if d.orden_ids and "orden_ids" not in errores:
        filas = db.execute(
            select(Orden, Unidad)
            .join(Solicitud, Solicitud.id == Orden.solicitud_id)
            .join(Unidad, Unidad.id == Solicitud.unidad_id)
            .where(Orden.id.in_(d.orden_ids))
        ).all()
        if len(filas) != len(d.orden_ids):
            errores["orden_ids"] = "Alguna orden no existe"
        for o, u in filas:
            unidades_ordenes.add(u.id)
            torres_ordenes.add(u.torre_id)
            if o.gremio_id != d.gremio_id:
                errores["orden_ids"] = "Hay órdenes de otro gremio"
            elif o.estado != "recogida":
                errores["orden_ids"] = "Solo se vinculan órdenes en estado recogida"
            else:
                rec = db.execute(
                    select(Asignacion.recolector_id).where(
                        Asignacion.orden_id == o.id, Asignacion.vigente_hasta.is_(None)
                    )
                ).scalar_one_or_none()
                if d.recolector_id is not None and rec != d.recolector_id:
                    errores["orden_ids"] = "Hay órdenes asignadas a otro recolector"

    # Procedencia territorial
    if d.unidad_medida_id is not None:
        u = db.get(Unidad, d.unidad_medida_id)
        if u is None:
            errores["unidad_medida_id"] = "Unidad inexistente"
        else:
            if unidades_ordenes and unidades_ordenes != {u.id}:
                errores["unidad_medida_id"] = "Las órdenes enlazadas deben ser de esa unidad (no se admite para lotes)"
            if d.torre_origen_id is not None and d.torre_origen_id != u.torre_id:
                errores["torre_origen_id"] = "No coincide con la torre de la unidad medida"
            elif d.torre_origen_id is None and u.torre_id is not None:
                d.torre_origen_id = u.torre_id
    if d.torre_origen_id is not None and "torre_origen_id" not in errores:
        if db.get(Torre, d.torre_origen_id) is None:
            errores["torre_origen_id"] = "Torre inexistente"
        elif torres_ordenes and torres_ordenes != {d.torre_origen_id}:
            errores["torre_origen_id"] = "Las órdenes enlazadas no son todas de esa torre; omite la torre"

    # Líneas
    calculadas: list[LineaCalculada] = []
    vistos: set[uuid.UUID] = set()
    for i, l in enumerate(d.lineas):
        k = f"lineas.{i}"
        if l.material_id in vistos:
            errores[f"{k}.material_id"] = "Material repetido"
            continue
        vistos.add(l.material_id)
        m = db.get(Material, l.material_id)
        if m is None or not m.activo:
            errores[f"{k}.material_id"] = "Material inexistente o inactivo"
            continue
        if m.gremio_id != d.gremio_id:
            errores[f"{k}.material_id"] = "Material de otro gremio"
            continue
        if isinstance(l, LineaBalde):
            eq = db.execute(
                select(VersionEquivalencia).where(
                    VersionEquivalencia.id == l.version_equivalencia_id, _vigente(VersionEquivalencia, d.fecha_medicion)
                )
            ).scalar_one_or_none()
            if eq is None or eq.gremio_id != d.gremio_id:
                errores[f"{k}.version_equivalencia_id"] = "Equivalencia inexistente, de otro gremio o no vigente en la fecha"
                continue
            acept = redondear_kg(l.cantidad_aceptada * eq.kg_por_unidad)
            rech = redondear_kg(l.cantidad_rechazada * eq.kg_por_unidad)
            cant = (l.cantidad_aceptada, l.cantidad_rechazada, eq.id)
        else:
            acept, rech = l.kg_aceptados, l.kg_rechazados
            cant = (None, None, None)
        if acept + rech <= 0:
            errores[k] = "La línea necesita algún peso mayor que cero"
            continue
        if rech > 0:
            if l.motivo_rechazo_id is None:
                errores[f"{k}.motivo_rechazo_id"] = "Indica el motivo del rechazo"
                continue
            mot = db.get(MotivoRechazo, l.motivo_rechazo_id)
            if mot is None or not mot.activo or (mot.gremio_id not in (None, d.gremio_id)):
                errores[f"{k}.motivo_rechazo_id"] = "Motivo inexistente, inactivo o de otro gremio"
                continue
        elif l.motivo_rechazo_id is not None:
            errores[f"{k}.motivo_rechazo_id"] = "Solo indica motivo si hay kilos rechazados"
            continue
        precio = db.execute(
            select(VersionPrecioMaterial)
            .where(VersionPrecioMaterial.material_id == m.id, _vigente(VersionPrecioMaterial, d.fecha_medicion))
            .order_by(VersionPrecioMaterial.vigente_desde.desc())
            .limit(1)
        ).scalar_one_or_none()
        calculadas.append(
            LineaCalculada(
                material_id=m.id,
                metodo_medicion=l.metodo_medicion,
                kg_aceptados=acept,
                kg_rechazados=rech,
                motivo_rechazo_id=l.motivo_rechazo_id,
                cantidad_aceptada=cant[0],
                cantidad_rechazada=cant[1],
                version_equivalencia_id=cant[2],
                precio_kg_aplicado=precio.precio_kg if precio else None,
                version_precio_id=precio.id if precio else None,
            )
        )
    if errores:
        raise invalido(errores)

    advertencias: list[str] = []
    if d.numero_tiquete:
        dup = db.execute(
            select(Pesaje.codigo).where(
                Pesaje.numero_tiquete == d.numero_tiquete,
                Pesaje.estado != "anulado",
                Pesaje.gremio_id == d.gremio_id,
                (Pesaje.emisor_tiquete == d.emisor_tiquete) if d.emisor_tiquete else Pesaje.emisor_tiquete.is_(None),
                Pesaje.id != (excluir_pesaje_id or uuid.uuid4()),
            )
        ).scalars().first()
        if dup:
            advertencias.append(f"El tiquete {d.numero_tiquete} ya aparece en {dup}; revisa que no sea un duplicado.")
    return calculadas, advertencias, d


def _escribir(db: Session, p: Pesaje, d: DatosPesaje, lineas: list[LineaCalculada]) -> None:
    p.fecha_medicion = d.fecha_medicion
    p.recolector_id = d.recolector_id
    p.proveedor_referencia = d.proveedor_referencia
    p.numero_tiquete = d.numero_tiquete
    p.emisor_tiquete = d.emisor_tiquete
    p.torre_origen_id = d.torre_origen_id
    p.unidad_medida_id = d.unidad_medida_id
    p.observacion = d.observacion
    # Vaciar y escribir antes de insertar: evita chocar con UQ(pesaje_id, material_id).
    p.lineas.clear()
    p.ordenes.clear()
    db.flush()
    p.lineas = [LineaPesaje(**vars(l)) for l in lineas]
    p.ordenes = [PesajeOrden(orden_id=o) for o in d.orden_ids]


def _nuevo_pesaje(db: Session, actor: Actor, d: DatosPesaje, lineas: list[LineaCalculada]) -> Pesaje:
    n = db.execute(select(pesaje_codigo_seq.next_value())).scalar_one()
    p = Pesaje(
        codigo=f"PS-{n:05d}",
        gremio_id=d.gremio_id,
        origen_captura=d.origen_captura,
        estado="borrador",
        creado_por=actor.cuenta_id,
        fecha_medicion=d.fecha_medicion,
    )
    db.add(p)
    _escribir(db, p, d, lineas)
    db.flush()
    return p


def cargar(db: Session, pesaje_id: uuid.UUID, bloquear: bool = False) -> Pesaje:
    stmt = (
        select(Pesaje)
        .where(Pesaje.id == pesaje_id)
        .options(selectinload(Pesaje.lineas), selectinload(Pesaje.ordenes))
        .execution_options(populate_existing=True)
    )
    if bloquear:
        stmt = stmt.with_for_update(of=Pesaje)
    p = db.execute(stmt).scalar_one_or_none()
    if p is None:
        raise no_encontrado("pesaje")
    return p


def pesaje_de_coordinacion(db: Session, actor: Actor, pesaje_id: uuid.UUID, bloquear: bool = False) -> Pesaje:
    p = cargar(db, pesaje_id, bloquear)
    if not actor.coordina(p.gremio_id):
        raise no_encontrado("pesaje")
    return p


def pesaje_out(db: Session, p: Pesaje, advertencias: list[str] | None = None, evaluacion: str | None = None) -> PesajeOut:
    lineas: list[LineaOut] = []
    tot_a = tot_r = sin_precio = Decimal(0)
    valor: Decimal | None = None
    for l in p.lineas:
        m = db.get(Material, l.material_id)
        eq = db.get(VersionEquivalencia, l.version_equivalencia_id) if l.version_equivalencia_id else None
        v = l.kg_aceptados * l.precio_kg_aplicado if l.precio_kg_aplicado is not None else None
        if v is not None:
            valor = (valor or Decimal(0)) + v
        else:
            sin_precio += l.kg_aceptados
        tot_a += l.kg_aceptados
        tot_r += l.kg_rechazados
        lineas.append(
            LineaOut(
                id=l.id,
                material_id=l.material_id,
                material_nombre=m.nombre if m else "",
                metodo_medicion=l.metodo_medicion,
                estimacion=l.metodo_medicion == "conversion_balde",
                kg_aceptados=l.kg_aceptados,
                kg_rechazados=l.kg_rechazados,
                motivo_rechazo_id=l.motivo_rechazo_id,
                cantidad_aceptada=l.cantidad_aceptada,
                cantidad_rechazada=l.cantidad_rechazada,
                version_equivalencia_id=l.version_equivalencia_id,
                kg_por_unidad=eq.kg_por_unidad if eq else None,
                precio_kg_aplicado=l.precio_kg_aplicado,
                valor_estimado=v,
            )
        )
    rec = db.get(Recolector, p.recolector_id) if p.recolector_id else None
    entrega_id = db.execute(select(EntregaDirecta.id).where(EntregaDirecta.pesaje_id == p.id)).scalar_one_or_none()
    return PesajeOut(
        id=p.id,
        codigo=p.codigo,
        created_at=p.created_at,
        version=p.version,
        estado=p.estado,
        gremio_id=p.gremio_id,
        recolector_id=p.recolector_id,
        recolector_nombre=rec.nombre if rec else None,
        fecha_medicion=p.fecha_medicion,
        origen_captura=p.origen_captura,
        orden_ids=[po.orden_id for po in p.ordenes],
        torre_origen_id=p.torre_origen_id,
        unidad_medida_id=p.unidad_medida_id,
        proveedor_referencia=p.proveedor_referencia,
        numero_tiquete=p.numero_tiquete,
        emisor_tiquete=p.emisor_tiquete,
        observacion=p.observacion,
        confirmado_at=p.confirmado_at,
        sustituye_pesaje_id=p.sustituye_pesaje_id,
        motivo_correccion=p.motivo_correccion,
        entrega_directa_id=entrega_id,
        lineas=lineas,
        totales=TotalesOut(kg_aceptados=tot_a, kg_rechazados=tot_r, valor_estimado=valor, kg_sin_precio=sin_precio),
        advertencias=advertencias or [],
        evaluacion_puntos=evaluacion,
    )


# --------------------------------------------------------------------------- casos de uso


def crear_pesaje(db: Session, actor: Actor, datos: PesajeIn) -> PesajeOut:
    d = DatosPesaje.de_entrada(datos)
    lineas, adv, d = validar(db, actor, d, recolector_obligatorio=True)
    p = _nuevo_pesaje(db, actor, d, lineas)
    registrar_evento(db, "pesaje_borrador_creado", actor, pesaje_id=p.id, datos={"origen": d.origen_captura})
    return pesaje_out(db, cargar(db, p.id), adv)


def actualizar_borrador(db: Session, actor: Actor, pesaje_id: uuid.UUID, datos: PesajePatch) -> PesajeOut:
    p = pesaje_de_coordinacion(db, actor, pesaje_id, bloquear=True)
    verificar_version(datos.version_esperada, p.version)
    if p.estado != "borrador":
        raise transicion_invalida("Solo se edita un borrador. Usa una corrección para un pesaje confirmado.")
    d = DatosPesaje.de_pesaje(p)
    es_entrega = db.execute(select(EntregaDirecta.id).where(EntregaDirecta.pesaje_id == p.id)).first() is not None
    for campo in datos.model_fields_set - {"version_esperada"}:
        valor = getattr(datos, campo)
        if campo in ("fecha_medicion", "lineas", "orden_ids") and valor is None:
            raise invalido({campo: "No admite null"})
        if es_entrega and campo in ("orden_ids", "unidad_medida_id", "torre_origen_id"):
            raise invalido({campo: "La procedencia de una entrega directa la fija su unidad"})
        setattr(d, campo, list(valor) if isinstance(valor, list) else valor)
    lineas, adv, d = validar(db, actor, d, recolector_obligatorio=not es_entrega, excluir_pesaje_id=p.id)
    _escribir(db, p, d, lineas)
    p.version += 1
    db.flush()
    registrar_evento(db, "pesaje_borrador_actualizado", actor, pesaje_id=p.id)
    return pesaje_out(db, cargar(db, p.id), adv)


def _acreditar_entrega(db: Session, p: Pesaje) -> str | None:
    e = db.execute(select(EntregaDirecta).where(EntregaDirecta.pesaje_id == p.id)).scalar_one_or_none()
    if e is None:
        return None
    unidad = db.get(Unidad, e.unidad_id) if e.unidad_id else None
    torre = db.get(Torre, unidad.torre_id) if unidad and unidad.torre_id else None
    acr = puntos_srv.acreditar(
        db,
        modalidad="entrega_directa",
        clave=f"entrega_directa:{e.id}",
        participante_id=e.participante_id,
        unidad_id=e.unidad_id,
        torre_id=unidad.torre_id if unidad else None,
        gremio_id=p.gremio_id,
        conjunto_id=torre.conjunto_id if torre else None,
        ocurrido_at=p.fecha_medicion,
        entrega_directa_id=e.id,
        pesaje_id=p.id,
    )
    if acr.nuevo and e.participante_id is not None:
        s = puntos_srv.saldo(db, e.participante_id)
        encolar_aviso(
            db,
            "entrega_directa_confirmada",
            e.participante_id,
            {
                "pesaje_codigo": p.codigo,
                "puntos_otorgados": str(acr.puntos),
                "saldo": str(s),
                "texto_sugerido": f"🌱 ¡Gracias por tu entrega! +{acr.puntos.normalize():f} puntos · Tienes {s.normalize():f}.",  # type: ignore[union-attr]
            },
        )
    return acr.evaluacion


def confirmar(db: Session, actor: Actor, pesaje_id: uuid.UUID, datos: ConfirmacionIn) -> PesajeOut:
    p = pesaje_de_coordinacion(db, actor, pesaje_id, bloquear=True)
    verificar_version(datos.version_esperada, p.version)
    if p.estado != "borrador":
        raise transicion_invalida(f"El pesaje ya está {p.estado}.")
    es_entrega = db.execute(select(EntregaDirecta.id).where(EntregaDirecta.pesaje_id == p.id)).first() is not None
    d = DatosPesaje.de_pesaje(p)
    lineas, adv, d = validar(db, actor, d, recolector_obligatorio=not es_entrega, excluir_pesaje_id=p.id)
    _escribir(db, p, d, lineas)  # vuelve a aplicar precios/equivalencias vigentes
    p.estado = "confirmado"
    p.confirmado_por = actor.cuenta_id
    p.confirmado_at = ahora()
    p.version += 1
    db.flush()
    registrar_evento(db, "pesaje_confirmado", actor, pesaje_id=p.id)
    evaluacion = _acreditar_entrega(db, p)
    db.flush()
    return pesaje_out(db, cargar(db, p.id), adv, evaluacion)


def corregir(db: Session, actor: Actor, pesaje_id: uuid.UUID, datos: CorreccionIn) -> PesajeOut:
    original = pesaje_de_coordinacion(db, actor, pesaje_id, bloquear=True)
    verificar_version(datos.version_esperada, original.version)
    if original.estado != "confirmado":
        raise transicion_invalida("Solo se corrige un pesaje confirmado; un borrador se edita.")
    if datos.pesaje_reemplazo.gremio_id != original.gremio_id:
        raise invalido({"pesaje_reemplazo.gremio_id": "El reemplazo debe ser del mismo gremio"})
    entrega = db.execute(select(EntregaDirecta).where(EntregaDirecta.pesaje_id == original.id)).scalar_one_or_none()
    d = DatosPesaje.de_entrada(datos.pesaje_reemplazo)
    if entrega is not None and (d.orden_ids or d.unidad_medida_id not in (None, entrega.unidad_id)):
        raise invalido({"pesaje_reemplazo": "Una entrega directa conserva su unidad y no lleva órdenes"})
    if entrega is not None:
        d.unidad_medida_id = entrega.unidad_id
    original.estado = "anulado"
    original.version += 1
    db.flush()
    lineas, adv, d = validar(
        db, actor, d, recolector_obligatorio=entrega is None, excluir_pesaje_id=original.id
    )
    nuevo = _nuevo_pesaje(db, actor, d, lineas)
    nuevo.estado = "confirmado"
    nuevo.confirmado_por = actor.cuenta_id
    nuevo.confirmado_at = ahora()
    nuevo.sustituye_pesaje_id = original.id
    nuevo.motivo_correccion = datos.motivo
    if entrega is not None:
        entrega.pesaje_id = nuevo.id  # el abono por entrega se conserva: su clave es la entrega
    db.flush()
    registrar_evento(db, "pesaje_anulado", actor, pesaje_id=original.id, datos={"reemplazo": str(nuevo.id)})
    registrar_evento(db, "pesaje_corregido", actor, pesaje_id=nuevo.id, datos={"motivo": datos.motivo})
    return pesaje_out(db, cargar(db, nuevo.id), adv)


def registrar_entrega_directa(db: Session, actor: Actor, datos: EntregaDirectaIn) -> PesajeOut:
    punto = referencia_activa(db, PuntoRecepcion, datos.punto_recepcion_id, "punto_recepcion_id", "Punto de recepción")
    if punto.gremio_id != datos.pesaje.gremio_id:
        raise invalido({"punto_recepcion_id": "El punto no pertenece al gremio del pesaje"})
    unidad_id = datos.unidad_id
    if datos.participante_id is not None:
        part = db.get(Participante, datos.participante_id)
        if part is None or part.estado == "eliminado":
            raise invalido({"participante_id": "Participante inexistente"})
        vigentes = db.execute(
            select(VinculoUnidad.unidad_id).where(
                VinculoUnidad.participante_id == part.id, VinculoUnidad.vigente_hasta.is_(None)
            )
        ).scalars().all()
        if unidad_id is None:
            if len(vigentes) != 1:
                raise invalido({"unidad_id": "Indica la unidad del participante"})
            unidad_id = vigentes[0]
        elif unidad_id not in vigentes:
            raise invalido({"participante_id": "El participante no está vinculado a esa unidad"})
    if unidad_id is not None:
        referencia_activa(db, Unidad, unidad_id, "unidad_id", "Unidad")
    d = DatosPesaje.de_entrada(datos.pesaje)
    d.unidad_medida_id = unidad_id
    lineas, adv, d = validar(db, actor, d, recolector_obligatorio=False)
    p = _nuevo_pesaje(db, actor, d, lineas)
    db.add(
        EntregaDirecta(
            pesaje_id=p.id,
            punto_recepcion_id=punto.id,
            unidad_id=unidad_id,
            participante_id=datos.participante_id,
            recibida_por=actor.cuenta_id,
        )
    )
    db.flush()
    registrar_evento(db, "entrega_directa_registrada", actor, pesaje_id=p.id, datos={"punto": punto.codigo})
    return pesaje_out(db, cargar(db, p.id), adv)


# --------------------------------------------------------------------------- rutas


@router.post("/pesajes", status_code=201)
def post_pesaje(datos: PesajeIn, request: Request, actor: Actor = Depends(actor_operador), db: Session = Depends(get_db)):
    return escritura(request, db, actor, datos, lambda: crear_pesaje(db, actor, datos), status=201)


@router.get("/pesajes")
def get_pesajes(
    gremio_id: uuid.UUID | None = Query(None),
    recolector_id: uuid.UUID | None = Query(None),
    estado: Literal["borrador", "confirmado", "anulado"] | None = Query(None),
    desde: InstanteEntrada | None = Query(None),
    hasta: InstanteEntrada | None = Query(None),
    actor: Actor = Depends(actor_operador),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
):
    alcance = actor.gremios_coordinados
    if not alcance:
        raise prohibido("Los pesajes detallados son para coordinación.")
    if gremio_id is not None and gremio_id not in alcance:
        raise prohibido("Fuera de tu gremio.")
    stmt = select(Pesaje.id).where(Pesaje.gremio_id.in_([gremio_id] if gremio_id else alcance))
    if recolector_id:
        stmt = stmt.where(Pesaje.recolector_id == recolector_id)
    if estado:
        stmt = stmt.where(Pesaje.estado == estado)
    if desde:
        stmt = stmt.where(Pesaje.fecha_medicion >= desde)
    if hasta:
        stmt = stmt.where(Pesaje.fecha_medicion < hasta)
    stmt = stmt.order_by(Pesaje.created_at.desc(), Pesaje.id.desc())
    return paginar(db, stmt, pag, lambda pid: pesaje_out(db, cargar(db, pid)).model_dump(mode="json"))


@router.get("/pesajes/{pesaje_id}")
def get_pesaje(pesaje_id: uuid.UUID, actor: Actor = Depends(actor_operador), db: Session = Depends(get_db)):
    return {"data": pesaje_out(db, pesaje_de_coordinacion(db, actor, pesaje_id)).model_dump(mode="json")}


@router.patch("/pesajes/{pesaje_id}")
def patch_pesaje(
    pesaje_id: uuid.UUID, datos: PesajePatch, request: Request,
    actor: Actor = Depends(actor_operador), db: Session = Depends(get_db),
):
    return escritura(request, db, actor, datos, lambda: actualizar_borrador(db, actor, pesaje_id, datos))


@router.post("/pesajes/{pesaje_id}/confirmacion")
def post_confirmacion(
    pesaje_id: uuid.UUID, datos: ConfirmacionIn, request: Request,
    actor: Actor = Depends(actor_operador), db: Session = Depends(get_db),
):
    return escritura(request, db, actor, datos, lambda: confirmar(db, actor, pesaje_id, datos))


@router.post("/pesajes/{pesaje_id}/correcciones", status_code=201)
def post_correccion(
    pesaje_id: uuid.UUID, datos: CorreccionIn, request: Request,
    actor: Actor = Depends(actor_operador), db: Session = Depends(get_db),
):
    return escritura(request, db, actor, datos, lambda: corregir(db, actor, pesaje_id, datos), status=201)


@router.post("/entregas-directas", status_code=201)
def post_entrega_directa(
    datos: EntregaDirectaIn, request: Request, actor: Actor = Depends(actor_operador), db: Session = Depends(get_db)
):
    return escritura(request, db, actor, datos, lambda: registrar_entrega_directa(db, actor, datos), status=201)


