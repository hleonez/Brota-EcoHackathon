"""Habilitación explícita del piloto por participante y unidad."""
import uuid
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.seguridad import Actor, actor_admin
from app.core.tipos import Entrada, Salida, Instante, InstanteEntrada, ahora
from app.core.idempotencia import escritura
from app.core.paginacion import Paginacion, paginacion, paginar
from app.core.errores import AppError, invalido
from app.db import get_db
from app.models import HabilitacionPiloto, Participante
from app.modulos.comun import obtener, unidades_vigentes, verificar_version, registrar_evento

router = APIRouter(tags=["piloto"])

class HabilitacionIn(Entrada):
    participante_id: uuid.UUID
    unidad_id: uuid.UUID
    vigente_desde: InstanteEntrada | None = None
    vigente_hasta: InstanteEntrada | None = None

class HabilitacionPatch(Entrada):
    version_esperada: int
    activo: bool
    vigente_hasta: InstanteEntrada | None = None

class HabilitacionOut(Salida):
    id: uuid.UUID
    participante_id: uuid.UUID
    unidad_id: uuid.UUID
    activo: bool
    version: int
    vigente_desde: Instante
    vigente_hasta: Instante | None
    revocada_at: Instante | None = None
    created_at: Instante

@router.get("/piloto/habilitaciones")
def listar(actor: Actor = Depends(actor_admin), db: Session = Depends(get_db), pag: Paginacion = Depends(paginacion)):
    return paginar(db, select(HabilitacionPiloto).order_by(HabilitacionPiloto.created_at, HabilitacionPiloto.id), pag,
                   lambda h: HabilitacionOut.model_validate(h).model_dump(mode="json"))

@router.post("/piloto/habilitaciones", status_code=201)
def habilitar(datos: HabilitacionIn, request: Request, actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)):
    def ejecutar():
        p = obtener(db, Participante, datos.participante_id, "participante", bloquear=True)
        if p.estado == "eliminado" or datos.unidad_id not in {u.id for u in unidades_vigentes(db, p.id)}:
            raise invalido({"unidad_id": "El participante debe tener un vínculo vigente con la unidad"})
        existente = db.execute(select(HabilitacionPiloto).where(
            HabilitacionPiloto.participante_id == p.id, HabilitacionPiloto.unidad_id == datos.unidad_id)).scalar_one_or_none()
        if existente:
            raise AppError(409, "DUPLICATE", "La habilitación ya existe; actualiza su estado.")
        valores = datos.model_dump()
        valores["vigente_desde"] = datos.vigente_desde or ahora()
        if datos.vigente_hasta is not None and datos.vigente_hasta <= valores["vigente_desde"]:
            raise invalido({"vigente_hasta": "Debe ser posterior al inicio"})
        h = HabilitacionPiloto(**valores, habilitada_por=actor.cuenta_id)
        db.add(h)
        db.flush()
        registrar_evento(db, "piloto_habilitado", actor, datos={"habilitacion_id": str(h.id)})
        return HabilitacionOut.model_validate(h)
    return escritura(request, db, actor, datos, ejecutar, status=201)

@router.patch("/piloto/habilitaciones/{id}")
def actualizar(id: uuid.UUID, datos: HabilitacionPatch, request: Request, actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)):
    def ejecutar():
        h = obtener(db, HabilitacionPiloto, id, "habilitación", bloquear=True)
        verificar_version(datos.version_esperada, h.version)
        if datos.activo and h.unidad_id not in {u.id for u in unidades_vigentes(db, h.participante_id)}:
            raise invalido({"activo": "El vínculo con la unidad ya no está vigente"})
        if "vigente_hasta" in datos.model_fields_set:
            if datos.vigente_hasta is not None and datos.vigente_hasta <= h.vigente_desde:
                raise invalido({"vigente_hasta": "Debe ser posterior al inicio"})
            h.vigente_hasta = datos.vigente_hasta
        if datos.activo:
            h.revocada_at = None
        elif h.revocada_at is None:
            h.revocada_at = ahora()
        h.activo = datos.activo
        h.version += 1
        registrar_evento(db, "piloto_actualizado", actor, datos={"habilitacion_id": str(h.id), "activo": h.activo})
        db.flush()
        return HabilitacionOut.model_validate(h)
    return escritura(request, db, actor, datos, ejecutar)
