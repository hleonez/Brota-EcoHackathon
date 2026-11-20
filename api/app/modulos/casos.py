"""M13 · Casos: el vecino reporta un problema o pide hablar con una persona.

El caso llega a la coordinación (alerta por WhatsApp y bandeja en el panel). Cuando la coordinación
responde, Brisa le lleva la respuesta al vecino. Si el caso nombra una solicitud (BR-…), lo ve la
coordinación de esos gremios; si no, todas las coordinaciones.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errores import no_encontrado, prohibido, transicion_invalida
from app.core.idempotencia import escritura
from app.core.paginacion import Paginacion, paginacion, paginar
from app.core.seguridad import Actor, actor_operador, actor_participante
from app.core.tipos import Entrada, Instante, Salida, ahora
from app.db import get_db
from app.models import Caso, Gremio, Orden, Participante, Solicitud, caso_codigo_seq
from app.modulos.comun import (
    encolar_aviso,
    encolar_aviso_coordinacion,
    etiqueta_unidad,
    registrar_evento,
    unidades_vigentes,
    verificar_version,
)

router = APIRouter(tags=["casos"])

TIPOS = {"queja": "⚠ Reporte", "ayuda": "🙋 Pide hablar con una persona"}


class CasoIn(Entrada):
    tipo: Literal["queja", "ayuda"]
    texto: str = Field(min_length=1, max_length=1000)
    codigo_pasaporte: str | None = Field(default=None, max_length=20, description="BR-… si es sobre una solicitud")


class AtencionIn(Entrada):
    version_esperada: int
    respuesta: str = Field(min_length=1, max_length=1000)


class CasoOut(Salida):
    id: uuid.UUID
    codigo: str
    tipo: str
    estado: str
    texto: str
    canal: str
    codigo_pasaporte: str | None
    gremio_id: uuid.UUID | None
    contacto_nombre: str | None
    ubicacion: str | None
    respuesta: str | None
    atendido_at: Instante | None
    version: int
    created_at: Instante


def caso_out(db: Session, c: Caso) -> CasoOut:
    p = db.get(Participante, c.participante_id) if c.participante_id else None
    s = db.get(Solicitud, c.solicitud_id) if c.solicitud_id else None
    ubicacion = s.ubicacion_operativa if s else None
    if ubicacion is None and p is not None:
        unidades = unidades_vigentes(db, p.id)
        ubicacion = etiqueta_unidad(unidades[0]) if unidades else None
    return CasoOut(
        id=c.id, codigo=c.codigo, tipo=c.tipo, estado=c.estado, texto=c.texto, canal=c.canal,
        codigo_pasaporte=s.codigo_pasaporte if s else None, gremio_id=c.gremio_id,
        contacto_nombre=p.nombre if p and p.estado != "eliminado" else None, ubicacion=ubicacion,
        respuesta=c.respuesta, atendido_at=c.atendido_at, version=c.version, created_at=c.created_at,
    )


def _alcance(actor: Actor) -> set[uuid.UUID] | None:
    """Gremios visibles; None = todos (administración)."""
    if actor.es_admin:
        return None
    if not actor.gremios_coordinados:
        raise prohibido("Los casos los atiende la coordinación.")
    return actor.gremios_coordinados


def crear_caso(db: Session, actor: Actor, datos: CasoIn) -> CasoOut:
    assert actor.participante_id is not None
    solicitud = None
    if datos.codigo_pasaporte:
        propias = [u.id for u in unidades_vigentes(db, actor.participante_id)]
        solicitud = db.execute(
            select(Solicitud).where(
                Solicitud.codigo_pasaporte == datos.codigo_pasaporte.strip().upper(),
                Solicitud.unidad_id.in_(propias or [uuid.uuid4()]),
            )
        ).scalar_one_or_none()
    gremios = (
        list(db.execute(select(Orden.gremio_id).where(Orden.solicitud_id == solicitud.id)).scalars())
        if solicitud else []
    )
    n = db.execute(select(caso_codigo_seq.next_value())).scalar_one()
    c = Caso(
        codigo=f"CA-{n:05d}", tipo=datos.tipo, texto=datos.texto.strip(), canal=actor.canal,
        participante_id=actor.participante_id, solicitud_id=solicitud.id if solicitud else None,
        gremio_id=gremios[0] if len(gremios) == 1 else None,
    )
    db.add(c)
    db.flush()
    registrar_evento(db, "caso_creado", actor, solicitud_id=c.solicitud_id,
                     datos={"caso_id": str(c.id), "tipo": c.tipo})
    out = caso_out(db, c)
    donde = f" ({out.ubicacion})" if out.ubicacion else ""
    sobre = f" sobre {out.codigo_pasaporte}" if out.codigo_pasaporte else ""
    texto = (f"{TIPOS[c.tipo]} {c.codigo}{sobre} de {actor.nombre or 'un vecino'}{donde}:\n«{c.texto}»\n"
             "👉 Respóndelo en el panel de coordinación (Reportes).")
    destino = gremios or list(db.execute(select(Gremio.id).where(Gremio.activo.is_(True))).scalars())
    for g in dict.fromkeys(destino):
        encolar_aviso_coordinacion(db, "nuevo_caso", g, {"caso_id": str(c.id), "codigo": c.codigo, "texto_sugerido": texto},
                                   solicitud_id=c.solicitud_id)
    return out


def atender_caso(db: Session, actor: Actor, caso_id: uuid.UUID, datos: AtencionIn) -> CasoOut:
    c = db.execute(select(Caso).where(Caso.id == caso_id).with_for_update()).scalar_one_or_none()
    alcance = _alcance(actor)
    if c is None or (alcance is not None and c.gremio_id is not None and c.gremio_id not in alcance):
        raise no_encontrado("caso")
    verificar_version(datos.version_esperada, c.version)
    if c.estado != "abierto":
        raise transicion_invalida("Este caso ya fue atendido.")
    c.estado, c.respuesta, c.atendido_por, c.atendido_at = "atendido", datos.respuesta.strip(), actor.cuenta_id, ahora()
    c.version += 1
    registrar_evento(db, "caso_atendido", actor, solicitud_id=c.solicitud_id, datos={"caso_id": str(c.id)})
    encolar_aviso(
        db, "caso_respuesta", c.participante_id,
        {"caso_id": str(c.id), "codigo": c.codigo, "respuesta": c.respuesta,
         "texto_sugerido": f"💬 Respuesta del equipo de Brota a tu reporte {c.codigo}:\n{c.respuesta}"},
        solicitud_id=c.solicitud_id,
    )
    db.flush()
    return caso_out(db, c)


@router.post("/casos", status_code=201)
def post_caso(datos: CasoIn, request: Request, actor: Actor = Depends(actor_participante), db: Session = Depends(get_db)):
    return escritura(request, db, actor, datos, lambda: crear_caso(db, actor, datos), status=201)


@router.get("/casos")
def get_casos(
    estado: Literal["abierto", "atendido"] | None = Query(None),
    actor: Actor = Depends(actor_operador),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
):
    alcance = _alcance(actor)
    stmt = select(Caso)
    if alcance is not None:
        stmt = stmt.where(or_(Caso.gremio_id.is_(None), Caso.gremio_id.in_(alcance)))
    if estado:
        stmt = stmt.where(Caso.estado == estado)
    stmt = stmt.order_by(Caso.created_at.desc(), Caso.id.desc())
    return paginar(db, stmt, pag, lambda c: caso_out(db, c).model_dump(mode="json"))


@router.post("/casos/{caso_id}/atencion")
def post_atencion(
    caso_id: uuid.UUID, datos: AtencionIn, request: Request, actor: Actor = Depends(actor_operador),
    db: Session = Depends(get_db),
):
    return escritura(request, db, actor, datos, lambda: atender_caso(db, actor, caso_id, datos))
