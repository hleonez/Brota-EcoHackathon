"""Canjes de Moneda Verde.

El premio colectivo de la torre no es un ítem: no se crea, no se lista y no se debita aquí.
La semilla de ejemplo (aliado Huerta Ecorazón, bolsa de abono, plántula y descuento del corredor)
está en ``app.seed`` y se puede volver a correr sin duplicar filas.

Reservar bloquea a la persona y luego el ítem, en ese orden, dentro de la misma transacción
que inserta el canje y el débito. Así dos canjes no gastan el mismo saldo ni la última unidad.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errores import AppError, invalido, no_encontrado, prohibido, transicion_invalida
from app.core.idempotencia import escritura
from app.core.paginacion import Paginacion, paginacion, paginar
from app.core.seguridad import Actor, actor_admin, get_actor
from app.core.tipos import DecimalEntrada, Entrada, Instante, PuntosSalida, Salida, ahora
from app.db import get_db
from app.models import Aliado, Canje, Gremio, ItemCanje, MovimientoPuntos, Participante
from app.modulos.comun import obtener, referencia_activa, registrar_evento, verificar_version
from app.modulos.puntos import saldo

router = APIRouter(tags=["canjes"])

_CENTAVO = Decimal("0.01")


class CanjeIn(Entrada):
    item_id: uuid.UUID
    cantidad: int = Field(default=1, ge=1, le=100)
    participante_id: uuid.UUID | None = None


class AliadoIn(Entrada):
    nombre: str = Field(min_length=1, max_length=120)
    gremio_id: uuid.UUID


class AliadoPatch(Entrada):
    version_esperada: int
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    activo: bool | None = None


class AliadoOut(Salida):
    id: uuid.UUID
    nombre: str
    gremio_id: uuid.UUID
    activo: bool
    version: int


class ItemIn(Entrada):
    aliado_id: uuid.UUID
    nombre: str = Field(min_length=1, max_length=120)
    costo_puntos: DecimalEntrada
    existencias: int | None = None

    @field_validator("costo_puntos")
    @classmethod
    def _costo(cls, valor: Decimal) -> Decimal:
        if valor <= 0:
            raise ValueError("El costo debe ser positivo")
        return valor

    @field_validator("existencias")
    @classmethod
    def _stock(cls, valor: int | None) -> int | None:
        if valor is not None and valor < 0:
            raise ValueError("Las existencias no pueden ser negativas")
        return valor


class ItemPatch(Entrada):
    version_esperada: int
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    costo_puntos: DecimalEntrada | None = None
    existencias: int | None = None
    activo: bool | None = None

    @field_validator("costo_puntos")
    @classmethod
    def _costo(cls, valor: Decimal | None) -> Decimal | None:
        if valor is not None and valor <= 0:
            raise ValueError("El costo debe ser positivo")
        return valor

    @field_validator("existencias")
    @classmethod
    def _stock(cls, valor: int | None) -> int | None:
        if valor is not None and valor < 0:
            raise ValueError("Las existencias no pueden ser negativas")
        return valor


class ItemOut(Salida):
    id: uuid.UUID
    aliado_id: uuid.UUID
    aliado_nombre: str
    gremio_id: uuid.UUID
    nombre: str
    costo_puntos: PuntosSalida
    existencias: int | None
    activo: bool
    version: int


class CanjeOut(Salida):
    id: uuid.UUID
    estado: str
    participante_id: uuid.UUID
    participante_nombre: str
    item_id: uuid.UUID
    item_nombre: str
    aliado_id: uuid.UUID
    aliado_nombre: str
    gremio_id: uuid.UUID
    cantidad: int
    costo_unitario_aplicado: PuntosSalida
    total_puntos: PuntosSalida
    created_at: Instante
    entregado_at: Instante | None = None


def _resolver_participante(actor: Actor, participante_id: uuid.UUID | None, gremio_id: uuid.UUID) -> uuid.UUID:
    if actor.tipo == "participante":
        if actor.participante_id is None:
            raise prohibido("Esta acción es para residentes o negocios registrados.")
        if participante_id is not None and participante_id != actor.participante_id:
            raise prohibido("Solo puedes canjear con tus propios puntos.")
        return actor.participante_id
    if actor.coordina(gremio_id):
        if participante_id is None:
            raise invalido({"participante_id": "Indica la persona que canjea"})
        return participante_id
    raise prohibido("Solo la persona o la coordinación de este gremio puede canjear.")


def _bloquear_participante(db: Session, participante_id: uuid.UUID) -> Participante:
    persona = db.execute(
        select(Participante).where(Participante.id == participante_id).with_for_update()
    ).scalar_one_or_none()
    if persona is None or persona.estado == "eliminado":
        raise invalido({"participante_id": "Persona inexistente o inactiva"})
    return persona


def _bloquear_item(db: Session, item_id: uuid.UUID) -> ItemCanje:
    item = db.execute(select(ItemCanje).where(ItemCanje.id == item_id).with_for_update()).scalar_one_or_none()
    if item is None:
        raise no_encontrado("ítem de canje")
    return item


def _salida(canje: Canje, item: ItemCanje, aliado: Aliado, persona: Participante) -> CanjeOut:
    return CanjeOut(
        id=canje.id,
        estado=canje.estado,
        participante_id=persona.id,
        participante_nombre=persona.nombre,
        item_id=item.id,
        item_nombre=item.nombre,
        aliado_id=aliado.id,
        aliado_nombre=aliado.nombre,
        gremio_id=aliado.gremio_id,
        cantidad=canje.cantidad,
        costo_unitario_aplicado=canje.costo_unitario_aplicado,
        total_puntos=canje.total_puntos,
        created_at=canje.created_at,
        entregado_at=canje.entregado_at,
    )


def _piezas(db: Session, canje: Canje) -> tuple[ItemCanje, Aliado, Participante]:
    item = db.get(ItemCanje, canje.item_id)
    aliado = db.get(Aliado, item.aliado_id) if item is not None else None
    persona = db.get(Participante, canje.participante_id)
    if item is None or aliado is None or persona is None:
        raise no_encontrado("canje")
    return item, aliado, persona


def reservar_canje(
    db: Session,
    actor: Actor,
    *,
    item_id: uuid.UUID,
    participante_id: uuid.UUID | None,
    cantidad: int,
) -> CanjeOut:
    """Debita el saldo y reserva el ítem. No hace commit: lo hace la idempotencia."""
    if cantidad < 1:
        raise invalido({"cantidad": "La cantidad debe ser al menos 1"})
    previo = db.get(ItemCanje, item_id)
    if previo is None:
        raise no_encontrado("ítem de canje")
    aliado_previo = db.get(Aliado, previo.aliado_id)
    if aliado_previo is None:
        raise no_encontrado("aliado")
    pid = _resolver_participante(actor, participante_id, aliado_previo.gremio_id)
    # Primero la persona, después el ítem: el mismo orden en la cancelación evita el bloqueo cruzado.
    persona = _bloquear_participante(db, pid)
    item = _bloquear_item(db, item_id)
    aliado = db.get(Aliado, item.aliado_id)
    if aliado is None or not item.activo or not aliado.activo:
        raise invalido({"item_id": "Este premio no está disponible"})
    if not (actor.tipo == "participante" or actor.coordina(aliado.gremio_id)):
        raise prohibido("Solo la persona o la coordinación de este gremio puede canjear.")
    total = (item.costo_puntos * cantidad).quantize(_CENTAVO)
    if item.costo_puntos <= 0 or total <= 0:
        raise invalido({"item_id": "El premio no tiene un costo válido"})
    if saldo(db, pid) < total:
        raise AppError(409, "SALDO_INSUFICIENTE", "No te alcanzan los puntos para este canje.")
    if item.existencias is not None:
        if item.existencias < cantidad:
            raise AppError(409, "SIN_EXISTENCIAS", "Ya no quedan unidades de este premio.")
        item.existencias -= cantidad
    canje = Canje(
        id=uuid.uuid4(),
        participante_id=pid,
        item_id=item.id,
        cantidad=cantidad,
        costo_unitario_aplicado=item.costo_puntos,
        total_puntos=total,
        estado="reservado",
        registrado_por=actor.cuenta_id if actor.es_operador else None,
    )
    db.add(canje)
    db.add(
        MovimientoPuntos(
            participante_id=pid,
            delta=-total,
            tipo="debito_canje",
            canje_id=canje.id,
            clave_aplicacion=f"canje:{canje.id}",
            ocurrido_at=ahora(),
            detalle_calculo={
                "nota": f"Canjeaste {item.nombre}.",
                "item_id": str(item.id),
                "cantidad": str(cantidad),
                "total": str(total),
            },
        )
    )
    db.flush()
    db.refresh(canje)
    registrar_evento(db, "canje_reservado", actor, datos={"canje_id": str(canje.id), "item_id": str(item.id)})
    return _salida(canje, item, aliado, persona)


def entregar_canje(db: Session, actor: Actor, canje_id: uuid.UUID) -> CanjeOut:
    canje = db.execute(select(Canje).where(Canje.id == canje_id).with_for_update()).scalar_one_or_none()
    if canje is None:
        raise no_encontrado("canje")
    item, aliado, persona = _piezas(db, canje)
    if not actor.coordina(aliado.gremio_id):
        raise prohibido("Solo la coordinación de este gremio puede entregar el canje.")
    if canje.estado != "reservado":
        raise transicion_invalida("Solo un canje reservado se puede marcar como entregado.")
    canje.estado = "entregado"
    canje.entregado_at = ahora()
    canje.entregado_por = actor.cuenta_id
    db.flush()
    registrar_evento(db, "canje_entregado", actor, datos={"canje_id": str(canje.id)})
    return _salida(canje, item, aliado, persona)


def cancelar_canje(db: Session, actor: Actor, canje_id: uuid.UUID) -> CanjeOut:
    canje = db.execute(select(Canje).where(Canje.id == canje_id).with_for_update()).scalar_one_or_none()
    if canje is None:
        raise no_encontrado("canje")
    item, aliado, persona = _piezas(db, canje)
    propio = actor.tipo == "participante" and actor.participante_id == canje.participante_id
    if not (propio or actor.coordina(aliado.gremio_id)):
        raise prohibido("Solo la persona o la coordinación de este gremio puede cancelar el canje.")
    if canje.estado == "entregado":
        raise transicion_invalida("Un canje entregado no se revierte.")
    if canje.estado != "reservado":
        raise transicion_invalida("Este canje ya no está reservado.")
    _bloquear_participante(db, canje.participante_id)
    item = _bloquear_item(db, canje.item_id)
    if item.existencias is not None:
        item.existencias += canje.cantidad
    debito = db.execute(
        select(MovimientoPuntos).where(MovimientoPuntos.clave_aplicacion == f"canje:{canje.id}")
    ).scalar_one()
    canje.estado = "cancelado"
    canje.cancelado_at = ahora()
    db.add(
        MovimientoPuntos(
            participante_id=canje.participante_id,
            delta=canje.total_puntos,
            tipo="reintegro",
            canje_id=canje.id,
            revierte_movimiento_id=debito.id,
            clave_aplicacion=f"reintegro:canje:{canje.id}",
            ocurrido_at=ahora(),
            detalle_calculo={"nota": f"Te devolvimos los puntos de {item.nombre}.", "total": str(canje.total_puntos)},
        )
    )
    db.flush()
    registrar_evento(db, "canje_cancelado", actor, datos={"canje_id": str(canje.id)})
    return _salida(canje, item, aliado, persona)


def _puede_ver_catalogo(actor: Actor) -> None:
    if actor.tipo == "participante" or actor.es_admin or actor.gremios_coordinados:
        return
    raise prohibido("No tienes acceso al catálogo de canjes.")


def _consulta_canjes(actor: Actor):
    stmt = (
        select(Canje, ItemCanje, Aliado, Participante)
        .join(ItemCanje, ItemCanje.id == Canje.item_id)
        .join(Aliado, Aliado.id == ItemCanje.aliado_id)
        .join(Participante, Participante.id == Canje.participante_id)
    )
    if actor.tipo == "participante":
        return stmt.where(Canje.participante_id == actor.participante_id)
    if actor.es_admin:
        return stmt
    if actor.gremios_coordinados:
        return stmt.where(Aliado.gremio_id.in_(actor.gremios_coordinados))
    raise prohibido("No tienes acceso a los canjes.")


# --------------------------------------------------------------------------- rutas


@router.get("/catalogo-canjes")
def get_catalogo(
    actor: Actor = Depends(get_actor), pag: Paginacion = Depends(paginacion), db: Session = Depends(get_db)
):
    _puede_ver_catalogo(actor)
    stmt = (
        select(ItemCanje, Aliado)
        .join(Aliado, Aliado.id == ItemCanje.aliado_id)
        .where(ItemCanje.activo.is_(True), Aliado.activo.is_(True))
        .order_by(ItemCanje.nombre, ItemCanje.id)
    )

    def conv(fila) -> dict:
        item, aliado = fila
        return ItemOut(
            id=item.id,
            aliado_id=aliado.id,
            aliado_nombre=aliado.nombre,
            gremio_id=aliado.gremio_id,
            nombre=item.nombre,
            costo_puntos=item.costo_puntos,
            existencias=item.existencias,
            activo=item.activo,
            version=item.version,
        ).model_dump(mode="json")

    return paginar(db, stmt, pag, conv, escalar=False)


@router.get("/canjes")
def get_canjes(
    estado: str | None = Query(default=None),
    actor: Actor = Depends(get_actor),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
):
    if estado is not None and estado not in ("reservado", "entregado", "cancelado"):
        raise invalido({"estado": "Estado desconocido"})
    stmt = _consulta_canjes(actor)
    if estado is not None:
        stmt = stmt.where(Canje.estado == estado)
    stmt = stmt.order_by(Canje.created_at.desc(), Canje.id.desc())

    def conv(fila) -> dict:
        canje, item, aliado, persona = fila
        return _salida(canje, item, aliado, persona).model_dump(mode="json")

    return paginar(db, stmt, pag, conv, escalar=False)


@router.post("/canjes", status_code=201)
def post_canje(datos: CanjeIn, request: Request, actor: Actor = Depends(get_actor), db: Session = Depends(get_db)):
    def _fn() -> CanjeOut:
        return reservar_canje(
            db, actor, item_id=datos.item_id, participante_id=datos.participante_id, cantidad=datos.cantidad
        )

    return escritura(request, db, actor, datos, _fn, status=201)


@router.post("/canjes/{canje_id}/entrega")
def post_entrega(
    canje_id: uuid.UUID, request: Request, actor: Actor = Depends(get_actor), db: Session = Depends(get_db)
):
    return escritura(request, db, actor, None, lambda: entregar_canje(db, actor, canje_id))


@router.post("/canjes/{canje_id}/cancelacion")
def post_cancelacion(
    canje_id: uuid.UUID, request: Request, actor: Actor = Depends(get_actor), db: Session = Depends(get_db)
):
    return escritura(request, db, actor, None, lambda: cancelar_canje(db, actor, canje_id))


@router.get("/aliados")
def get_aliados(
    _actor: Actor = Depends(actor_admin), pag: Paginacion = Depends(paginacion), db: Session = Depends(get_db)
):
    stmt = select(Aliado).order_by(Aliado.activo.desc(), Aliado.nombre, Aliado.id)
    return paginar(db, stmt, pag, lambda a: AliadoOut.model_validate(a).model_dump(mode="json"))


@router.post("/aliados", status_code=201)
def post_aliado(datos: AliadoIn, request: Request, actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)):
    def _fn() -> AliadoOut:
        referencia_activa(db, Gremio, datos.gremio_id, "gremio_id", "Gremio")
        aliado = Aliado(nombre=datos.nombre, gremio_id=datos.gremio_id)
        db.add(aliado)
        db.flush()
        registrar_evento(db, "aliado_creado", actor, datos={"aliado_id": str(aliado.id)})
        return AliadoOut.model_validate(aliado)

    return escritura(request, db, actor, datos, _fn, status=201)


@router.patch("/aliados/{aliado_id}")
def patch_aliado(
    aliado_id: uuid.UUID,
    datos: AliadoPatch,
    request: Request,
    actor: Actor = Depends(actor_admin),
    db: Session = Depends(get_db),
):
    def _fn() -> AliadoOut:
        aliado = obtener(db, Aliado, aliado_id, "aliado", bloquear=True)
        verificar_version(datos.version_esperada, aliado.version)
        if datos.nombre is not None:
            aliado.nombre = datos.nombre
        if datos.activo is not None:
            aliado.activo = datos.activo
        aliado.version += 1
        db.flush()
        return AliadoOut.model_validate(aliado)

    return escritura(request, db, actor, datos, _fn)


def _item_out(item: ItemCanje, aliado: Aliado) -> ItemOut:
    return ItemOut(
        id=item.id,
        aliado_id=aliado.id,
        aliado_nombre=aliado.nombre,
        gremio_id=aliado.gremio_id,
        nombre=item.nombre,
        costo_puntos=item.costo_puntos,
        existencias=item.existencias,
        activo=item.activo,
        version=item.version,
    )


@router.get("/items-canje")
def get_items(
    _actor: Actor = Depends(actor_admin), pag: Paginacion = Depends(paginacion), db: Session = Depends(get_db)
):
    stmt = (
        select(ItemCanje, Aliado)
        .join(Aliado, Aliado.id == ItemCanje.aliado_id)
        .order_by(ItemCanje.activo.desc(), ItemCanje.nombre, ItemCanje.id)
    )
    return paginar(db, stmt, pag, lambda fila: _item_out(*fila).model_dump(mode="json"), escalar=False)


@router.post("/items-canje", status_code=201)
def post_item(datos: ItemIn, request: Request, actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)):
    def _fn() -> ItemOut:
        aliado = referencia_activa(db, Aliado, datos.aliado_id, "aliado_id", "Aliado")
        item = ItemCanje(
            aliado_id=aliado.id,
            nombre=datos.nombre,
            costo_puntos=datos.costo_puntos,
            existencias=datos.existencias,
        )
        db.add(item)
        db.flush()
        registrar_evento(db, "item_canje_creado", actor, datos={"item_id": str(item.id)})
        return _item_out(item, aliado)

    return escritura(request, db, actor, datos, _fn, status=201)


@router.patch("/items-canje/{item_id}")
def patch_item(
    item_id: uuid.UUID,
    datos: ItemPatch,
    request: Request,
    actor: Actor = Depends(actor_admin),
    db: Session = Depends(get_db),
):
    def _fn() -> ItemOut:
        item = obtener(db, ItemCanje, item_id, "ítem de canje", bloquear=True)
        verificar_version(datos.version_esperada, item.version)
        if datos.nombre is not None:
            item.nombre = datos.nombre
        if datos.costo_puntos is not None:
            item.costo_puntos = datos.costo_puntos
        if "existencias" in datos.model_fields_set:
            item.existencias = datos.existencias
        if datos.activo is not None:
            item.activo = datos.activo
        item.version += 1
        aliado = db.get(Aliado, item.aliado_id)
        if aliado is None:
            raise no_encontrado("aliado")
        db.flush()
        return _item_out(item, aliado)

    return escritura(request, db, actor, datos, _fn)
