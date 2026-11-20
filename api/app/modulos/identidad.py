"""M01 · Identidad, registro, consentimiento y cuentas operadoras."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errores import AppError, invalido, prohibido
from app.core.idempotencia import escritura
from app.core.paginacion import Paginacion, paginacion, paginar
from app.core.seguridad import (
    Actor,
    actor_admin,
    actor_operador,
    actor_participante,
    get_actor,
    hash_pin,
    normalizar_celular,
)
from app.core.tipos import Entrada, Instante, Salida, ahora
from app.db import get_db
from app.models import (
    Consentimiento,
    CuentaOperadora,
    Gremio,
    HabilitacionPiloto,
    Recolector,
    Participante,
    PermisoOperador,
    SolicitudEliminacion,
    Unidad,
    VinculoUnidad,
)
from app.modulos.comun import (
    consentimiento_vigente,
    etiqueta_unidad,
    obtener,
    referencia_activa,
    registrar_evento,
    unidades_vigentes,
    verificar_version,
)

router = APIRouter(tags=["identidad"])

# --------------------------------------------------------------------------- esquemas


class ConsentimientoIn(Entrada):
    version_politica: str = Field(min_length=1, max_length=30)
    decision: Literal["aceptado", "retirado"]


class RegistroIn(Entrada):
    nombre: str = Field(min_length=1, max_length=120)
    unidad_id: uuid.UUID
    consentimiento: ConsentimientoIn


class RegistroAsistidoIn(Entrada):
    nombre: str = Field(min_length=1, max_length=120)
    unidad_id: uuid.UUID | None = None
    celular: str | None = Field(default=None, max_length=20)
    consentimiento: ConsentimientoIn | None = None


class UnidadResumen(Salida):
    id: uuid.UUID
    tipo: str
    referencia_local: str
    etiqueta: str
    torre_id: uuid.UUID | None
    torre_codigo: str | None = None
    conjunto_id: uuid.UUID | None = None


class ConsentimientoOut(Salida):
    version_politica: str
    decision: str
    canal: str
    registrado_at: Instante


class RegistroOut(Salida):
    participante_id: uuid.UUID
    nombre: str
    estado_registro: Literal["completo", "incompleto"]
    unidad: UnidadResumen | None
    consentimiento: ConsentimientoOut | None


class PermisoOut(Salida):
    rol: str
    gremio_id: uuid.UUID | None


class HabilitacionResumen(Salida):
    id: uuid.UUID
    unidad_id: uuid.UUID
    activo: bool
    vigente_desde: Instante
    vigente_hasta: Instante | None
    revocada_at: Instante | None = None


class MeOut(Salida):
    trabajador_id: uuid.UUID | None = None
    tipo_actor: str
    registrado: bool
    participante_id: uuid.UUID | None = None
    cuenta_operadora_id: uuid.UUID | None = None
    nombre: str | None = None
    unidades: list[UnidadResumen] = []
    consentimiento_vigente: ConsentimientoOut | None = None
    politica_datos_version: str
    permisos: list[PermisoOut] = []
    capacidades: list[str] = []
    habilitaciones: list[HabilitacionResumen] = []


class SolicitudEliminacionIn(Entrada):
    observacion: str | None = Field(default=None, max_length=500)


class SolicitudEliminacionOut(Salida):
    id: uuid.UUID
    estado: str
    created_at: Instante


class PermisoIn(Entrada):
    rol: Literal["coordinacion", "fundacion", "admin", "reciclador", "huertero"]
    gremio_id: uuid.UUID | None = None


class CuentaIn(Entrada):
    trabajador_id: uuid.UUID | None = None
    nombre: str = Field(min_length=1, max_length=120)
    usuario: str = Field(min_length=3, max_length=60, pattern=r"^[a-zA-Z0-9._-]+$")
    pin: str = Field(min_length=4, max_length=12, pattern=r"^\d+$")
    permisos: list[PermisoIn] = Field(min_length=1)
    celular: str | None = Field(default=None, max_length=20, description="Para operar desde WhatsApp con Brisa")


class CuentaPatch(Entrada):
    version_esperada: int
    activo: bool | None = None
    pin: str | None = Field(default=None, min_length=4, max_length=12, pattern=r"^\d+$")
    permisos: list[PermisoIn] | None = None
    celular: str | None = Field(default=None, max_length=20, description="null lo quita")


class CuentaOut(Salida):
    trabajador_id: uuid.UUID | None = None
    id: uuid.UUID
    nombre: str
    usuario: str
    celular: str | None
    activo: bool
    version: int
    permisos: list[PermisoOut]
    created_at: Instante


class UnidadVinculadaOut(Salida):
    id: uuid.UUID
    tipo: str
    etiqueta: str


class ParticipanteListaOut(Salida):
    id: uuid.UUID
    nombre: str
    unidades: list[UnidadVinculadaOut]


# --------------------------------------------------------------------------- servicio


def unidad_resumen(u: Unidad) -> UnidadResumen:
    return UnidadResumen(
        id=u.id,
        tipo=u.tipo,
        referencia_local=u.referencia_local,
        etiqueta=etiqueta_unidad(u),
        torre_id=u.torre_id,
        torre_codigo=u.torre.codigo if u.torre else None,
        conjunto_id=u.torre.conjunto_id if u.torre else None,
    )


def _tipo_vinculo(u: Unidad) -> str:
    return "residente" if u.tipo == "hogar" else "contacto_negocio"


def _crear_participante(
    db: Session,
    nombre: str,
    celular: str | None,
    unidad: Unidad | None,
    consentimiento: ConsentimientoIn | None,
    canal: str,
) -> RegistroOut:
    if consentimiento is not None and consentimiento.version_politica != get_settings().politica_datos_version:
        raise invalido(
            {"consentimiento.version_politica": f"La política vigente es {get_settings().politica_datos_version}"}
        )
    completo = unidad is not None and consentimiento is not None and consentimiento.decision == "aceptado"
    p = Participante(nombre=nombre.strip(), celular_normalizado=celular, estado="activo" if completo else "incompleto")
    db.add(p)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "CONTACT_ALREADY_REGISTERED", "Este celular ya está registrado.") from None
    if unidad is not None:
        db.add(VinculoUnidad(participante_id=p.id, unidad_id=unidad.id, tipo_vinculo=_tipo_vinculo(unidad)))
    c = None
    if consentimiento is not None:
        c = Consentimiento(
            participante_id=p.id,
            version_politica=consentimiento.version_politica,
            decision=consentimiento.decision,
            canal=canal,
        )
        db.add(c)
    db.flush()
    return RegistroOut(
        participante_id=p.id,
        nombre=p.nombre,
        estado_registro="completo" if completo else "incompleto",
        unidad=unidad_resumen(unidad) if unidad else None,
        consentimiento=ConsentimientoOut.model_validate(c) if c else None,
    )


def registrar_por_canal(db: Session, actor: Actor, datos: RegistroIn) -> RegistroOut:
    if actor.tipo == "participante":
        raise AppError(409, "CONTACT_ALREADY_REGISTERED", "Este celular ya está registrado.")
    if actor.tipo != "no_registrado" or not actor.celular:
        raise prohibido("El registro se hace desde el canal verificado (envía X-Canal-Celular).")
    if datos.consentimiento.decision != "aceptado":
        raise AppError(422, "CONSENT_REQUIRED", "Para registrarte necesitamos tu autorización de datos.")
    unidad = referencia_activa(db, Unidad, datos.unidad_id, "unidad_id", "Unidad")
    out = _crear_participante(db, datos.nombre, actor.celular, unidad, datos.consentimiento, actor.canal)
    registrar_evento(db, "participante_registrado", actor, datos={"participante_id": str(out.participante_id)})
    return out


def registrar_asistido(db: Session, actor: Actor, datos: RegistroAsistidoIn) -> RegistroOut:
    if not (actor.gremios_coordinados or actor.es_admin):
        raise prohibido("El registro asistido es para coordinación o administración.")
    celular = normalizar_celular(datos.celular) if datos.celular else None
    unidad = referencia_activa(db, Unidad, datos.unidad_id, "unidad_id", "Unidad") if datos.unidad_id else None
    out = _crear_participante(db, datos.nombre, celular, unidad, datos.consentimiento, "asistido")
    registrar_evento(db, "participante_registrado_asistido", actor, datos={"participante_id": str(out.participante_id)})
    return out


def capacidades_de(actor: Actor) -> list[str]:
    if actor.tipo == "participante":
        return ["solicitar", "consultar_solicitudes", "consultar_puntos", "liga"]
    if actor.tipo == "no_registrado":
        return ["registrarse", "consultar_territorio"]
    if actor.tipo == "servicio_bot":
        return ["avisos"]
    caps: set[str] = set()
    if actor.trabajador_id is not None:
        caps |= {"mis_asignaciones", "resultado"}
    if actor.gremios_coordinados:
        caps |= {"bandeja", "asignar", "resultado", "pesajes", "entregas_directas", "recolectores", "registro_asistido", "sync"}
    if actor.es_fundacion:
        caps |= {"reportes", "liga"}
    if actor.es_admin:
        caps |= {"configuracion", "cuentas", "catalogos", "reportes", "registro_asistido"}
    return sorted(caps)


def me(db: Session, actor: Actor) -> MeOut:
    politica = get_settings().politica_datos_version
    base = MeOut(
        tipo_actor=actor.tipo_publico,
        registrado=actor.tipo in ("participante", "operador"),
        politica_datos_version=politica,
        capacidades=capacidades_de(actor),
    )
    if actor.tipo == "participante" and actor.participante_id:
        c = consentimiento_vigente(db, actor.participante_id)
        base.participante_id = actor.participante_id
        base.nombre = actor.nombre
        base.unidades = [unidad_resumen(u) for u in unidades_vigentes(db, actor.participante_id)]
        base.consentimiento_vigente = ConsentimientoOut.model_validate(c) if c else None
        vigentes = db.execute(
            select(HabilitacionPiloto).where(
                HabilitacionPiloto.participante_id == actor.participante_id,
                HabilitacionPiloto.activo.is_(True),
                HabilitacionPiloto.vigente_desde <= ahora(),
                or_(HabilitacionPiloto.vigente_hasta.is_(None), HabilitacionPiloto.vigente_hasta > ahora()),
            )
        ).scalars()
        base.habilitaciones = [HabilitacionResumen.model_validate(h) for h in vigentes]
    elif actor.es_operador:
        base.cuenta_operadora_id = actor.cuenta_id
        base.trabajador_id = actor.trabajador_id
        base.nombre = actor.nombre
        base.permisos = [PermisoOut(rol=r, gremio_id=g) for r, g in actor.permisos]
    return base


def _validar_permisos(db: Session, permisos: list[PermisoIn]) -> None:
    for i, p in enumerate(permisos):
        if p.rol in ("coordinacion", "reciclador", "huertero"):
            referencia_activa(db, Gremio, p.gremio_id, f"permisos.{i}.gremio_id", "Gremio")
        elif p.gremio_id is not None:
            raise invalido({f"permisos.{i}.gremio_id": "Solo coordinación lleva gremio"})


def _cuenta_out(c: CuentaOperadora) -> CuentaOut:
    return CuentaOut(
        id=c.id,
        trabajador_id=c.trabajador_id,
        nombre=c.nombre,
        usuario=c.usuario,
        celular=c.celular_normalizado,
        activo=c.activo,
        version=c.version,
        permisos=[PermisoOut(rol=p.rol, gremio_id=p.gremio_id) for p in c.permisos],
        created_at=c.created_at,
    )


# --------------------------------------------------------------------------- rutas


@router.get("/me")
def get_me(actor: Actor = Depends(get_actor), db: Session = Depends(get_db)) -> dict:
    return {"data": me(db, actor).model_dump(mode="json")}


@router.post("/registros", status_code=201)
def post_registro(
    datos: RegistroIn, request: Request, actor: Actor = Depends(get_actor), db: Session = Depends(get_db)
):
    return escritura(request, db, actor, datos, lambda: registrar_por_canal(db, actor, datos), status=201)


@router.post("/registros/asistidos", status_code=201)
def post_registro_asistido(
    datos: RegistroAsistidoIn,
    request: Request,
    actor: Actor = Depends(actor_operador),
    db: Session = Depends(get_db),
):
    return escritura(request, db, actor, datos, lambda: registrar_asistido(db, actor, datos), status=201)


@router.post("/me/consentimientos", status_code=201)
def post_consentimiento(
    datos: ConsentimientoIn,
    request: Request,
    actor: Actor = Depends(actor_participante),
    db: Session = Depends(get_db),
):
    def _fn() -> ConsentimientoOut:
        if datos.version_politica != get_settings().politica_datos_version:
            raise invalido({"version_politica": f"La política vigente es {get_settings().politica_datos_version}"})
        c = Consentimiento(
            participante_id=actor.participante_id,
            version_politica=datos.version_politica,
            decision=datos.decision,
            canal=actor.canal,
        )
        db.add(c)
        p = db.get(Participante, actor.participante_id)
        if p is not None and datos.decision == "aceptado" and unidades_vigentes(db, p.id):
            p.estado = "activo"
        db.flush()
        db.refresh(c)
        return ConsentimientoOut.model_validate(c)

    return escritura(request, db, actor, datos, _fn, status=201)


@router.post("/me/solicitudes-eliminacion", status_code=202)
def post_solicitud_eliminacion(
    datos: SolicitudEliminacionIn,
    request: Request,
    actor: Actor = Depends(actor_participante),
    db: Session = Depends(get_db),
):
    def _fn() -> SolicitudEliminacionOut:
        s = SolicitudEliminacion(participante_id=actor.participante_id, observacion=datos.observacion)
        db.add(s)
        db.flush()
        db.refresh(s)
        registrar_evento(db, "solicitud_eliminacion", actor, datos={"solicitud_eliminacion_id": str(s.id)})
        return SolicitudEliminacionOut.model_validate(s)

    return escritura(request, db, actor, datos, _fn, status=202)


@router.get("/me/solicitudes-eliminacion")
def get_solicitudes_eliminacion(
    actor: Actor = Depends(actor_participante),
    pag: Paginacion = Depends(paginacion),
    db: Session = Depends(get_db),
):
    stmt = (
        select(SolicitudEliminacion)
        .where(SolicitudEliminacion.participante_id == actor.participante_id)
        .order_by(SolicitudEliminacion.created_at.desc(), SolicitudEliminacion.id.desc())
    )
    return paginar(db, stmt, pag, lambda s: SolicitudEliminacionOut.model_validate(s).model_dump(mode="json"))


def _participante_lista(db: Session, participante: Participante) -> dict:
    unidades = [
        UnidadVinculadaOut(id=u.id, tipo=u.tipo, etiqueta=etiqueta_unidad(u))
        for u in unidades_vigentes(db, participante.id)
    ]
    return ParticipanteListaOut(
        id=participante.id, nombre=participante.nombre, unidades=unidades
    ).model_dump(mode="json")


@router.get("/participantes")
def get_participantes(
    actor: Actor = Depends(actor_admin), pag: Paginacion = Depends(paginacion), db: Session = Depends(get_db)
):
    """Personas vigentes, con o sin habilitación. La habilitación sigue en /v1/piloto/habilitaciones."""
    stmt = (
        select(Participante)
        .where(Participante.estado != "eliminado")
        .order_by(Participante.created_at.desc(), Participante.id.desc())
    )
    return paginar(db, stmt, pag, lambda p: _participante_lista(db, p))


@router.get("/cuentas-operadoras")
def get_cuentas(
    actor: Actor = Depends(actor_admin), pag: Paginacion = Depends(paginacion), db: Session = Depends(get_db)
):
    stmt = select(CuentaOperadora).order_by(CuentaOperadora.created_at.desc(), CuentaOperadora.id.desc())
    return paginar(db, stmt, pag, lambda c: _cuenta_out(c).model_dump(mode="json"))


@router.post("/cuentas-operadoras", status_code=201)
def post_cuenta(
    datos: CuentaIn, request: Request, actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)
):
    def _fn() -> CuentaOut:
        _validar_permisos(db, datos.permisos)
        _validar_trabajador(db, datos.trabajador_id, datos.permisos)
        c = CuentaOperadora(
            trabajador_id=datos.trabajador_id,
            nombre=datos.nombre,
            usuario=datos.usuario.lower(),
            pin_hash=hash_pin(datos.pin),
            celular_normalizado=normalizar_celular(datos.celular) if datos.celular else None,
        )
        c.permisos = [PermisoOperador(rol=p.rol, gremio_id=p.gremio_id) for p in datos.permisos]
        db.add(c)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise AppError(409, "DUPLICATE", "Ya existe una cuenta con ese usuario o celular.") from None
        db.refresh(c)
        registrar_evento(db, "cuenta_creada", actor, datos={"cuenta_id": str(c.id), "usuario": c.usuario})
        return _cuenta_out(c)

    # El PIN queda fuera de la huella de idempotencia para no guardar un derivado débil del PIN.
    return escritura(request, db, actor, datos.model_dump(mode="json", exclude={"pin"}), _fn, status=201)


@router.patch("/cuentas-operadoras/{cuenta_id}")
def patch_cuenta(
    cuenta_id: uuid.UUID,
    datos: CuentaPatch,
    request: Request,
    actor: Actor = Depends(actor_admin),
    db: Session = Depends(get_db),
):
    def _fn() -> CuentaOut:
        c = obtener(db, CuentaOperadora, cuenta_id, "cuenta", bloquear=True)
        verificar_version(datos.version_esperada, c.version)
        if datos.activo is not None:
            c.activo = datos.activo
        if datos.pin is not None:
            c.pin_hash = hash_pin(datos.pin)
        if datos.permisos is not None:
            _validar_permisos(db, datos.permisos)
            _validar_trabajador(db, c.trabajador_id, datos.permisos)
            c.permisos = [PermisoOperador(rol=p.rol, gremio_id=p.gremio_id) for p in datos.permisos]
        if "celular" in datos.model_fields_set:
            c.celular_normalizado = normalizar_celular(datos.celular) if datos.celular else None
        c.version += 1
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise AppError(409, "DUPLICATE", "Ese celular ya pertenece a otra cuenta.") from None
        registrar_evento(db, "cuenta_actualizada", actor, datos={"cuenta_id": str(c.id)})
        return _cuenta_out(c)

    return escritura(request, db, actor, datos.model_dump(mode="json", exclude={"pin"}), _fn)


def _validar_trabajador(db, trabajador_id, permisos):
    roles = [p for p in permisos if p.rol in ("reciclador", "huertero")]
    if trabajador_id is None:
        if roles:
            raise invalido({"trabajador_id": "Este perfil requiere un trabajador vinculado"})
        return
    trabajador = referencia_activa(db, Recolector, trabajador_id, "trabajador_id", "Trabajador")
    if len(permisos) != 1 or len(roles) != 1 or roles[0].rol != trabajador.tipo or roles[0].gremio_id != trabajador.gremio_id:
        raise invalido({"permisos": "Debe coincidir el perfil y gremio del trabajador, sin permisos adicionales"})
