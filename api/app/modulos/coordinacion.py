"""M04 · Coordinación: bandeja, asignación y resultado humano.

nueva → asignada → recogida
                 ↘ rechazada
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field, model_validator
from sqlalchemy import exists, select
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
from app.core.tipos import Entrada, InstanteEntrada, PuntosSalida, ahora
from app.db import get_db
from app.models import (
    Asignacion,
    ContenidoEducativo,
    ContenidoMotivo,
    Gremio,
    Huerta,
    MotivoRechazo,
    Material,
    Orden,
    Recolector,
    ResultadoMaterial,
    ResultadoOrden,
    Solicitud,
    Torre,
)
from app.modulos import puntos as puntos_srv
from app.modulos.comun import (
    encolar_aviso,
    franja_texto,
    referencia_activa,
    registrar_evento,
    verificar_version,
)
from app.modulos.solicitudes import OrdenBandejaOut, orden_out

router = APIRouter(tags=["coordinación"])

# --------------------------------------------------------------------------- esquemas


class AsignacionIn(Entrada):
    version_esperada: int
    recolector_id: uuid.UUID
    inicio: InstanteEntrada | None = None
    fin: InstanteEntrada | None = None
    forma_aviso: Literal["llamada", "recado"]
    acuerdo_canal: Literal["whatsapp", "llamada", "presencial"] | None = None
    acuerdo_observacion: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _horario(self) -> AsignacionIn:
        if (self.inicio is None) != (self.fin is None):
            raise ValueError("Envía inicio y fin juntos, o ninguno")
        if self.inicio is not None and self.fin is not None and self.fin <= self.inicio:
            raise ValueError("fin debe ser posterior a inicio")
        if self.inicio is not None and self.acuerdo_canal is None:
            raise ValueError("Registra cómo se acordó el horario")
        return self


class ResultadoIn(Entrada):
    materiales_confirmados: list[uuid.UUID] = Field(max_length=50)
    version_esperada: int
    resultado: Literal["recogida", "rechazada"]
    ocurrido_at: InstanteEntrada
    motivo_rechazo_id: uuid.UUID | None = None
    observacion: str | None = Field(default=None, max_length=500)


class OrdenResultadoOut(OrdenBandejaOut):
    evaluacion_puntos: Literal["acreditada", "no_aplica", "pendiente", "requiere_revision"]
    puntos_otorgados: PuntosSalida | None = None


# --------------------------------------------------------------------------- servicio


def _cargar_orden(db: Session, orden_id: uuid.UUID, bloquear: bool = False) -> Orden:
    stmt = (
        select(Orden)
        .where(Orden.id == orden_id)
        .options(
            selectinload(Orden.asignaciones).selectinload(Asignacion.recolector),
            selectinload(Orden.resultado).selectinload(ResultadoOrden.materiales),
            selectinload(Orden.solicitud).selectinload(Solicitud.servicios),
            selectinload(Orden.solicitud).selectinload(Solicitud.unidad),
        )
        .execution_options(populate_existing=True)
    )
    if bloquear:
        stmt = stmt.with_for_update(of=Orden)
    o = db.execute(stmt).scalar_one_or_none()
    if o is None:
        raise no_encontrado("orden")
    return o


def orden_de_coordinacion(db: Session, actor: Actor, orden_id: uuid.UUID, bloquear: bool = False) -> Orden:
    o = _cargar_orden(db, orden_id, bloquear)
    propia = actor.trabajador_id is not None and any(
        a.vigente_hasta is None and a.recolector_id == actor.trabajador_id for a in o.asignaciones)
    if not actor.coordina(o.gremio_id) and not propia:
        raise no_encontrado("orden")
    return o


def asignar(db: Session, actor: Actor, orden_id: uuid.UUID, datos: AsignacionIn) -> OrdenBandejaOut:
    o = orden_de_coordinacion(db, actor, orden_id, bloquear=True)
    actor.exigir_coordinacion(o.gremio_id)
    verificar_version(datos.version_esperada, o.version)
    if o.estado not in ("nueva", "asignada", "programada"):
        raise transicion_invalida(f"La orden está {o.estado}; ya no se puede asignar.")
    r = referencia_activa(db, Recolector, datos.recolector_id, "recolector_id", "Recolector")
    if r.tipo == "huertero":
        if r.huerta_id is None:
            raise invalido({"recolector_id": "Vincula el huertero a su huerta antes de asignar"})
        referencia_activa(db, Huerta, r.huerta_id, "huerta_id", "Huerta")
    if r.gremio_id != o.gremio_id:
        raise invalido({"recolector_id": "El recolector no pertenece al gremio de la orden"})
    t = ahora()
    anterior = next((a for a in o.asignaciones if a.vigente_hasta is None), None)
    if anterior is not None:
        anterior.vigente_hasta = t
        db.flush()
    cambio_persona = anterior is not None and anterior.recolector_id != r.id
    con_horario = datos.inicio is not None
    db.add(
        Asignacion(
            orden_id=o.id,
            recolector_id=r.id,
            inicio=datos.inicio,
            fin=datos.fin,
            forma_aviso=datos.forma_aviso,
            registrada_por=actor.cuenta_id,
            acuerdo_canal=datos.acuerdo_canal if con_horario else None,
            acuerdo_observacion=datos.acuerdo_observacion if con_horario else None,
            programada_por=actor.cuenta_id if con_horario else None,
            vigente_desde=t,
        )
    )
    o.estado = "programada" if con_horario else "asignada"
    o.version += 1
    detalle = {
        "recolector_id": str(r.id),
        "forma_aviso": datos.forma_aviso,
        "acuerdo_canal": datos.acuerdo_canal if con_horario else None,
        "inicio": datos.inicio.isoformat() if datos.inicio else None,
        "fin": datos.fin.isoformat() if datos.fin else None,
    }
    if anterior is None:
        registrar_evento(db, "orden_asignada", actor, solicitud_id=o.solicitud_id, orden_id=o.id, datos=detalle)
    elif cambio_persona:
        registrar_evento(db, "orden_reasignada", actor, solicitud_id=o.solicitud_id, orden_id=o.id, datos=detalle)
    if con_horario:
        ya_habia_horario = anterior is not None and anterior.recolector_id == r.id and anterior.inicio is not None
        registrar_evento(
            db,
            "orden_reprogramada" if ya_habia_horario else "orden_programada",
            actor,
            solicitud_id=o.solicitud_id,
            orden_id=o.id,
            datos=detalle,
        )
    gremio = db.get(Gremio, o.gremio_id)
    franja = franja_texto(datos.inicio, datos.fin)
    # franja termina en "p. m." / "a. m.": no repetir el punto.
    texto = f"🚲 {r.nombre} pasa {franja} Ten la bolsa lista en la puerta." if franja else (
        f"🚲 {r.nombre} va a pasar por tu recolección. Te avisamos cualquier novedad."
    )
    encolar_aviso(
        db,
        "asignacion",
        o.solicitud.participante_id,
        {
            "codigo_pasaporte": o.solicitud.codigo_pasaporte,
            "gremio": gremio.nombre if gremio else None,
            "recolector_nombre": r.nombre,
            "inicio": datos.inicio.isoformat() if datos.inicio else None,
            "fin": datos.fin.isoformat() if datos.fin else None,
            "franja_texto": franja,
            "reasignacion": cambio_persona,
            "texto_sugerido": texto,
        },
        solicitud_id=o.solicitud_id,
        orden_id=o.id,
    )
    db.flush()
    return orden_out(db, _cargar_orden(db, o.id), bandeja=True)  # type: ignore[return-value]


def _contenido_para(db: Session, motivo_id: uuid.UUID) -> ContenidoEducativo | None:
    c = db.execute(
        select(ContenidoEducativo)
        .join(ContenidoMotivo, ContenidoMotivo.contenido_id == ContenidoEducativo.id)
        .where(ContenidoMotivo.motivo_rechazo_id == motivo_id, ContenidoEducativo.activo.is_(True), ContenidoEducativo.publicado.is_(True))
        .order_by(ContenidoEducativo.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if c is None:
        c = db.execute(
            select(ContenidoEducativo)
            .where(ContenidoEducativo.general.is_(True), ContenidoEducativo.activo.is_(True), ContenidoEducativo.publicado.is_(True))
            .order_by(ContenidoEducativo.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
    return c


def registrar_resultado(db: Session, actor: Actor, orden_id: uuid.UUID, datos: ResultadoIn) -> OrdenResultadoOut:
    o = orden_de_coordinacion(db, actor, orden_id, bloquear=True)
    verificar_version(datos.version_esperada, o.version)
    if o.estado != "programada":
        raise transicion_invalida(
            "Programa la visita antes de registrar el resultado."
            if o.estado in ("nueva", "asignada")
            else f"La orden ya está {o.estado}."
        )
    if datos.ocurrido_at > ahora() + timedelta(minutes=5):
        raise invalido({"ocurrido_at": "No puede estar en el futuro"})
    motivo = None
    if datos.resultado == "rechazada":
        if datos.motivo_rechazo_id is None:
            raise invalido({"motivo_rechazo_id": "El rechazo requiere motivo"})
        motivo = referencia_activa(db, MotivoRechazo, datos.motivo_rechazo_id, "motivo_rechazo_id", "Motivo")
        if motivo.gremio_id is not None and motivo.gremio_id != o.gremio_id:
            raise invalido({"motivo_rechazo_id": "Motivo de otro gremio"})
    elif datos.motivo_rechazo_id is not None:
        raise invalido({"motivo_rechazo_id": "Una recogida no lleva motivo de rechazo"})

    if datos.materiales_confirmados is not None:
        if len(set(datos.materiales_confirmados)) != len(datos.materiales_confirmados):
            raise invalido({"materiales_confirmados": "Materiales repetidos"})
        if datos.resultado == "recogida" and not datos.materiales_confirmados:
            raise invalido({"materiales_confirmados": "Confirma al menos un material"})
        if datos.resultado == "rechazada" and datos.materiales_confirmados:
            raise invalido({"materiales_confirmados": "Un rechazo no confirma materiales aceptados"})
        for mid in datos.materiales_confirmados:
            material = referencia_activa(db, Material, mid, "materiales_confirmados", "Material")
            if material.gremio_id != o.gremio_id:
                raise invalido({"materiales_confirmados": "Material de otro gremio"})

    res = ResultadoOrden(
        trabajador_id=next(a.recolector_id for a in o.asignaciones if a.vigente_hasta is None),
        asignacion_id=next(a.id for a in o.asignaciones if a.vigente_hasta is None),
        materiales_confirmados=None,
        orden_id=o.id,
        resultado=datos.resultado,
        motivo_rechazo_id=datos.motivo_rechazo_id,
        observacion=datos.observacion,
        confirmado_por=actor.cuenta_id,
        ocurrido_at=datos.ocurrido_at,
    )
    db.add(res)
    db.flush()
    for mid in datos.materiales_confirmados:
        db.add(ResultadoMaterial(resultado_orden_id=res.id, material_id=mid))
    o.estado = datos.resultado
    o.version += 1
    db.flush()
    registrar_evento(
        db, f"orden_{datos.resultado}", actor, solicitud_id=o.solicitud_id, orden_id=o.id,
        datos={"motivo_rechazo_id": str(datos.motivo_rechazo_id) if datos.motivo_rechazo_id else None},
    )

    s = o.solicitud
    unidad = s.unidad
    torre = db.get(Torre, unidad.torre_id) if unidad.torre_id else None
    evaluacion = "no_aplica"
    otorgados = None
    if datos.resultado == "recogida":
        acr = puntos_srv.acreditar(
            db,
            modalidad="entrega_valida",
            clave=f"entrega_valida:orden:{o.id}",
            participante_id=s.participante_id,
            unidad_id=unidad.id,
            torre_id=unidad.torre_id,
            gremio_id=o.gremio_id,
            conjunto_id=torre.conjunto_id if torre else None,
            ocurrido_at=datos.ocurrido_at,
            resultado_orden_id=res.id,
        )
        evaluacion = acr.evaluacion
        otorgados = acr.puntos
        if s.participante_id is not None:
            saldo = puntos_srv.saldo(db, s.participante_id)
            pts = f"+{otorgados.normalize():f} puntos · Tienes {saldo.normalize():f}." if otorgados else ""
            encolar_aviso(
                db,
                "recoleccion_confirmada",
                s.participante_id,
                {
                    "codigo_pasaporte": s.codigo_pasaporte,
                    "puntos_otorgados": str(otorgados) if otorgados is not None else None,
                    "saldo": str(saldo),
                    "evaluacion_puntos": evaluacion,
                    "texto_sugerido": f"💚 ¡Gracias! Tu material llegó bien separado. {pts}".strip(),
                },
                solicitud_id=s.id,
                orden_id=o.id,
            )
    else:
        assert motivo is not None
        contenido = _contenido_para(db, motivo.id)
        encolar_aviso(
            db,
            "rechazo_educativo",
            s.participante_id,
            {
                "codigo_pasaporte": s.codigo_pasaporte,
                "motivo_codigo": motivo.codigo,
                "motivo": motivo.nombre,
                "contenido": (
                    {"titulo": contenido.titulo, "tipo": contenido.tipo, "recurso": contenido.recurso, "texto": contenido.texto}
                    if contenido
                    else None
                ),
                "texto_sugerido": (
                    f"😕 Esta vez no se pudo llevar el material: {motivo.nombre.lower()}. "
                    "Mira este consejo para la próxima 👇"
                ),
            },
            solicitud_id=s.id,
            orden_id=o.id,
        )
    db.flush()
    base = orden_out(db, _cargar_orden(db, o.id), bandeja=True)
    return OrdenResultadoOut(**base.model_dump(), evaluacion_puntos=evaluacion, puntos_otorgados=otorgados)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- rutas


@router.get("/ordenes")
def get_ordenes(
    gremio_id: uuid.UUID | None = Query(None),
    estado: Literal["nueva", "asignada", "programada", "recogida", "rechazada", "cancelada"] | None = Query(None),
    recolector_id: uuid.UUID | None = Query(None),
    desde: InstanteEntrada | None = Query(None),
    hasta: InstanteEntrada | None = Query(None),
    actor: Actor = Depends(actor_operador),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
):
    alcance = actor.gremios_coordinados
    if not alcance and actor.trabajador_id is None:
        raise prohibido("La bandeja es para coordinación.")
    if gremio_id is not None and gremio_id not in alcance and not any(g == gremio_id and r in ("huertero", "reciclador") for r, g in actor.permisos):
        raise prohibido("Fuera de tu gremio.")
    stmt = select(Orden.id)
    if actor.trabajador_id is not None:
        stmt = stmt.where(exists().where(Asignacion.orden_id == Orden.id,
            Asignacion.recolector_id == actor.trabajador_id, Asignacion.vigente_hasta.is_(None)))
    else:
        stmt = stmt.where(Orden.gremio_id.in_([gremio_id] if gremio_id else alcance))
    if estado:
        stmt = stmt.where(Orden.estado == estado)
    if recolector_id:
        stmt = stmt.where(
            exists().where(
                Asignacion.orden_id == Orden.id,
                Asignacion.recolector_id == recolector_id,
                Asignacion.vigente_hasta.is_(None),
            )
        )
    if desde:
        stmt = stmt.where(Orden.created_at >= desde)
    if hasta:
        stmt = stmt.where(Orden.created_at < hasta)
    stmt = stmt.order_by(Orden.created_at.desc(), Orden.id.desc())
    gremios = {g.id: g.nombre for g in db.execute(select(Gremio)).scalars()}
    return paginar(
        db, stmt, pag, lambda oid: orden_out(db, _cargar_orden(db, oid), gremios, bandeja=True).model_dump(mode="json")
    )


@router.get("/ordenes/{orden_id}")
def get_orden(orden_id: uuid.UUID, actor: Actor = Depends(actor_operador), db: Session = Depends(get_db)):
    o = orden_de_coordinacion(db, actor, orden_id)
    return {"data": orden_out(db, o, bandeja=True).model_dump(mode="json")}


@router.post("/ordenes/{orden_id}/asignacion")
def post_asignacion(
    orden_id: uuid.UUID,
    datos: AsignacionIn,
    request: Request,
    actor: Actor = Depends(actor_operador),
    db: Session = Depends(get_db),
):
    return escritura(request, db, actor, datos, lambda: asignar(db, actor, orden_id, datos))


@router.post("/ordenes/{orden_id}/resultado")
def post_resultado(
    orden_id: uuid.UUID,
    datos: ResultadoIn,
    request: Request,
    actor: Actor = Depends(actor_operador),
    db: Session = Depends(get_db),
):
    return escritura(request, db, actor, datos, lambda: registrar_resultado(db, actor, orden_id, datos))




class ProgramacionIn(Entrada):
    acuerdo_canal: Literal["whatsapp", "llamada", "presencial"]
    acuerdo_observacion: str | None = Field(default=None, max_length=300)
    version_esperada: int
    inicio: InstanteEntrada
    fin: InstanteEntrada

    @model_validator(mode="after")
    def validar_franja(self):
        if self.fin <= self.inicio:
            raise ValueError("fin debe ser posterior a inicio")
        return self


def programar(db, actor, orden_id, datos):
    o = orden_de_coordinacion(db, actor, orden_id, bloquear=True)
    actor.exigir_coordinacion(o.gremio_id)
    verificar_version(datos.version_esperada, o.version)
    vigente = next((a for a in o.asignaciones if a.vigente_hasta is None), None)
    if vigente is None or o.estado not in ("asignada", "programada"):
        raise transicion_invalida("Asigna un responsable antes de programar.")
    return asignar(db, actor, orden_id, AsignacionIn(
        version_esperada=datos.version_esperada, recolector_id=vigente.recolector_id,
        inicio=datos.inicio, fin=datos.fin, forma_aviso=vigente.forma_aviso,
        acuerdo_canal=datos.acuerdo_canal, acuerdo_observacion=datos.acuerdo_observacion))


@router.post("/ordenes/{orden_id}/programacion")
def post_programacion(orden_id: uuid.UUID, datos: ProgramacionIn, request: Request,
    actor: Actor = Depends(actor_operador), db: Session = Depends(get_db)):
    return escritura(request, db, actor, datos, lambda: programar(db, actor, orden_id, datos))
