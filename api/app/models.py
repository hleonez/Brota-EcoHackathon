"""Modelo relacional de Brota.

Sigue `diseño de base de datos inicial - brota` (18-nov-2026). Diferencias deliberadas:
- `punto_recepcion` se materializa como catálogo (el diseño lo nombraba sin tabla).
- `cuenta_operadora` incluye `usuario` y `pin_hash` (sesión de tablet con PIN corto).
- `referencia_local` resuelve IDs temporales de la sincronización offline.
- `solicitud_eliminacion` da seguimiento al derecho de supresión.
- Se omiten por ahora canjes, archivos/IA, versiones de Liga y certificados emitidos.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    Sequence,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

KG = Numeric(12, 3)
PRECIO = Numeric(14, 4)
PUNTOS = Numeric(12, 2)

solicitud_pasaporte_seq = Sequence("solicitud_pasaporte_seq")
pesaje_codigo_seq = Sequence("pesaje_codigo_seq")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))


def _ts_now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _fk(target: str, nullable: bool = False, **kw: Any) -> Mapped[Any]:
    return mapped_column(ForeignKey(target, **kw), nullable=nullable, index=True)


# --------------------------------------------------------------------------- territorio


class Conjunto(Base):
    __tablename__ = "conjunto"
    id: Mapped[uuid.UUID] = _pk()
    nombre: Mapped[str] = mapped_column(String(120))
    etapa: Mapped[str | None] = mapped_column(String(60))
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = _ts_now()


class Torre(Base):
    __tablename__ = "torre"
    __table_args__ = (UniqueConstraint("conjunto_id", "codigo"),)
    id: Mapped[uuid.UUID] = _pk()
    conjunto_id: Mapped[uuid.UUID] = _fk("conjunto.id")
    codigo: Mapped[str] = mapped_column(String(30))
    nombre: Mapped[str | None] = mapped_column(String(120))
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = _ts_now()

    conjunto: Mapped[Conjunto] = relationship()


class CapacidadTorre(Base):
    """Denominador histórico de la Liga: número de viviendas vigente."""

    __tablename__ = "capacidad_torre"
    __table_args__ = (
        CheckConstraint("numero_viviendas > 0", name="viviendas_positivas"),
        CheckConstraint("vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="vigencia"),
    )
    id: Mapped[uuid.UUID] = _pk()
    torre_id: Mapped[uuid.UUID] = _fk("torre.id")
    numero_viviendas: Mapped[int] = mapped_column(Integer)
    vigente_desde: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts_now()


class Unidad(Base):
    """Hogar o negocio. Un hogar pertenece a una torre; un negocio del corredor puede no tenerla."""

    __tablename__ = "unidad"
    __table_args__ = (
        CheckConstraint("tipo IN ('hogar','negocio')", name="tipo"),
        CheckConstraint("tipo = 'negocio' OR torre_id IS NOT NULL", name="hogar_con_torre"),
        Index(
            "uq_unidad_torre_referencia",
            "torre_id",
            "referencia_local",
            unique=True,
            postgresql_where=text("torre_id IS NOT NULL"),
        ),
    )
    id: Mapped[uuid.UUID] = _pk()
    tipo: Mapped[str] = mapped_column(String(20))
    torre_id: Mapped[uuid.UUID | None] = _fk("torre.id", nullable=True)
    referencia_local: Mapped[str] = mapped_column(String(60))
    direccion_referencia: Mapped[str | None] = mapped_column(String(200))
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = _ts_now()

    torre: Mapped[Torre | None] = relationship()


# --------------------------------------------------------------------------- identidad


class Participante(Base):
    """Residente o contacto de negocio. Sin contraseña: el canal verificado lo identifica."""

    __tablename__ = "participante"
    __table_args__ = (
        CheckConstraint("estado IN ('activo','incompleto','eliminado')", name="estado"),
        Index(
            "uq_participante_celular_vigente",
            "celular_normalizado",
            unique=True,
            postgresql_where=text("celular_normalizado IS NOT NULL AND estado <> 'eliminado'"),
        ),
    )
    id: Mapped[uuid.UUID] = _pk()
    nombre: Mapped[str] = mapped_column(String(120))
    celular_normalizado: Mapped[str | None] = mapped_column(String(20))
    estado: Mapped[str] = mapped_column(String(20), server_default="activo", default="activo")
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VinculoUnidad(Base):
    __tablename__ = "vinculo_unidad"
    __table_args__ = (
        CheckConstraint("tipo_vinculo IN ('residente','contacto_negocio')", name="tipo"),
        Index(
            "uq_vinculo_vigente",
            "participante_id",
            "unidad_id",
            unique=True,
            postgresql_where=text("vigente_hasta IS NULL"),
        ),
    )
    id: Mapped[uuid.UUID] = _pk()
    participante_id: Mapped[uuid.UUID] = _fk("participante.id")
    unidad_id: Mapped[uuid.UUID] = _fk("unidad.id")
    tipo_vinculo: Mapped[str] = mapped_column(String(30))
    vigente_desde: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    unidad: Mapped[Unidad] = relationship()


class Consentimiento(Base):
    """Historial de aceptación o retiro, con versión de política y canal."""

    __tablename__ = "consentimiento"
    __table_args__ = (CheckConstraint("decision IN ('aceptado','retirado')", name="decision"),)
    id: Mapped[uuid.UUID] = _pk()
    participante_id: Mapped[uuid.UUID] = _fk("participante.id")
    version_politica: Mapped[str] = mapped_column(String(30))
    decision: Mapped[str] = mapped_column(String(20))
    canal: Mapped[str] = mapped_column(String(20))
    referencia_evidencia: Mapped[str | None] = mapped_column(String(200))
    registrado_at: Mapped[datetime] = _ts_now()


class SolicitudEliminacion(Base):
    __tablename__ = "solicitud_eliminacion"
    __table_args__ = (CheckConstraint("estado IN ('pendiente','en_proceso','atendida')", name="estado"),)
    id: Mapped[uuid.UUID] = _pk()
    participante_id: Mapped[uuid.UUID] = _fk("participante.id")
    estado: Mapped[str] = mapped_column(String(20), server_default="pendiente", default="pendiente")
    observacion: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = _ts_now()


class Gremio(Base):
    """Equipo que atiende un tipo de trabajo (Asorescatar, Huerta Ecorazón)."""

    __tablename__ = "gremio"
    id: Mapped[uuid.UUID] = _pk()
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True)


class CuentaOperadora(Base):
    __tablename__ = "cuenta_operadora"
    id: Mapped[uuid.UUID] = _pk()
    nombre: Mapped[str] = mapped_column(String(120))
    usuario: Mapped[str] = mapped_column(String(60), unique=True)
    pin_hash: Mapped[str | None] = mapped_column(String(200))
    referencia_autenticacion: Mapped[str | None] = mapped_column(String(200))
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True)
    version: Mapped[int] = mapped_column(Integer, server_default="1", default=1)
    created_at: Mapped[datetime] = _ts_now()

    permisos: Mapped[list[PermisoOperador]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class PermisoOperador(Base):
    __tablename__ = "permiso_operador"
    __table_args__ = (
        CheckConstraint("rol IN ('coordinacion','fundacion','admin')", name="rol"),
        CheckConstraint("rol <> 'coordinacion' OR gremio_id IS NOT NULL", name="coordinacion_con_gremio"),
    )
    id: Mapped[uuid.UUID] = _pk()
    cuenta_id: Mapped[uuid.UUID] = _fk("cuenta_operadora.id", ondelete="CASCADE")
    rol: Mapped[str] = mapped_column(String(20))
    gremio_id: Mapped[uuid.UUID | None] = _fk("gremio.id", nullable=True)


# --------------------------------------------------------------------------- catálogos


class TipoServicio(Base):
    __tablename__ = "tipo_servicio"
    id: Mapped[uuid.UUID] = _pk()
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    gremio_id: Mapped[uuid.UUID] = _fk("gremio.id")
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True)


class Recolector(Base):
    """Persona recolectora. No tiene cuenta ni credenciales: la coordinación registra por ella."""

    __tablename__ = "recolector"
    id: Mapped[uuid.UUID] = _pk()
    gremio_id: Mapped[uuid.UUID] = _fk("gremio.id")
    nombre: Mapped[str] = mapped_column(String(120))
    telefono_contacto: Mapped[str | None] = mapped_column(String(30))
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True)
    version: Mapped[int] = mapped_column(Integer, server_default="1", default=1)
    created_at: Mapped[datetime] = _ts_now()


class Material(Base):
    __tablename__ = "material"
    id: Mapped[uuid.UUID] = _pk()
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    gremio_id: Mapped[uuid.UUID] = _fk("gremio.id")
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True)
    version: Mapped[int] = mapped_column(Integer, server_default="1", default=1)


class MotivoRechazo(Base):
    __tablename__ = "motivo_rechazo"
    id: Mapped[uuid.UUID] = _pk()
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    gremio_id: Mapped[uuid.UUID | None] = _fk("gremio.id", nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True)


class PuntoRecepcion(Base):
    """Acopio o huerta donde se recibe y pesa material."""

    __tablename__ = "punto_recepcion"
    id: Mapped[uuid.UUID] = _pk()
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    gremio_id: Mapped[uuid.UUID] = _fk("gremio.id")
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True)


class VersionPrecioMaterial(Base):
    __tablename__ = "version_precio_material"
    __table_args__ = (
        CheckConstraint("precio_kg >= 0", name="precio_no_negativo"),
        CheckConstraint("vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="vigencia"),
    )
    id: Mapped[uuid.UUID] = _pk()
    material_id: Mapped[uuid.UUID] = _fk("material.id")
    precio_kg: Mapped[Decimal] = mapped_column(PRECIO)
    moneda: Mapped[str] = mapped_column(String(3), server_default="COP", default="COP")
    vigente_desde: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts_now()


class VersionEquivalencia(Base):
    """kg por recipiente (balde) en un contexto concreto; nunca una constante global."""

    __tablename__ = "version_equivalencia"
    __table_args__ = (
        CheckConstraint("kg_por_unidad > 0", name="kg_positivo"),
        CheckConstraint("vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="vigencia"),
    )
    id: Mapped[uuid.UUID] = _pk()
    gremio_id: Mapped[uuid.UUID] = _fk("gremio.id")
    punto_recepcion_id: Mapped[uuid.UUID | None] = _fk("punto_recepcion.id", nullable=True)
    recipiente: Mapped[str] = mapped_column(String(40))
    kg_por_unidad: Mapped[Decimal] = mapped_column(KG)
    vigente_desde: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts_now()


# --------------------------------------------------------------------------- solicitud y orden


class Solicitud(Base):
    """Pedido del residente. Su `codigo_pasaporte` (BR-00018) es el Pasaporte Circular."""

    __tablename__ = "solicitud"
    __table_args__ = (Index("ix_solicitud_unidad_creacion", "unidad_id", "created_at", "id"),)
    id: Mapped[uuid.UUID] = _pk()
    codigo_pasaporte: Mapped[str] = mapped_column(String(20), unique=True)
    unidad_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unidad.id"))
    participante_id: Mapped[uuid.UUID | None] = _fk("participante.id", nullable=True)
    canal_origen: Mapped[str] = mapped_column(String(20))
    observacion: Mapped[str | None] = mapped_column(String(500))
    ubicacion_operativa: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, server_default="1", default=1)
    created_at: Mapped[datetime] = _ts_now()

    ordenes: Mapped[list[Orden]] = relationship(back_populates="solicitud", order_by="Orden.created_at")
    servicios: Mapped[list[SolicitudServicio]] = relationship()
    unidad: Mapped[Unidad] = relationship()
    participante: Mapped[Participante | None] = relationship()


class SolicitudServicio(Base):
    __tablename__ = "solicitud_servicio"
    __table_args__ = (PrimaryKeyConstraint("solicitud_id", "tipo_servicio_id"),)
    solicitud_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("solicitud.id"))
    tipo_servicio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tipo_servicio.id"))
    orden_id: Mapped[uuid.UUID] = _fk("orden.id")


class Orden(Base):
    """Trabajo de un gremio dentro de una solicitud. nueva → asignada → recogida | rechazada."""

    __tablename__ = "orden"
    __table_args__ = (
        UniqueConstraint("solicitud_id", "gremio_id"),
        CheckConstraint("estado IN ('nueva','asignada','recogida','rechazada')", name="estado"),
        Index("ix_orden_bandeja", "gremio_id", "estado", "created_at", "id"),
    )
    id: Mapped[uuid.UUID] = _pk()
    solicitud_id: Mapped[uuid.UUID] = _fk("solicitud.id")
    gremio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gremio.id"))
    estado: Mapped[str] = mapped_column(String(20), server_default="nueva", default="nueva")
    version: Mapped[int] = mapped_column(Integer, server_default="1", default=1)
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    solicitud: Mapped[Solicitud] = relationship(back_populates="ordenes")
    asignaciones: Mapped[list[Asignacion]] = relationship(order_by="Asignacion.vigente_desde")
    resultado: Mapped[ResultadoOrden | None] = relationship(uselist=False)


class Asignacion(Base):
    __tablename__ = "asignacion"
    __table_args__ = (
        CheckConstraint("forma_aviso IN ('llamada','recado')", name="forma_aviso"),
        CheckConstraint("(inicio IS NULL) = (fin IS NULL)", name="horario_completo"),
        CheckConstraint("fin IS NULL OR fin > inicio", name="horario_orden"),
        Index("uq_asignacion_vigente", "orden_id", unique=True, postgresql_where=text("vigente_hasta IS NULL")),
    )
    id: Mapped[uuid.UUID] = _pk()
    orden_id: Mapped[uuid.UUID] = _fk("orden.id")
    recolector_id: Mapped[uuid.UUID] = _fk("recolector.id")
    inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    forma_aviso: Mapped[str] = mapped_column(String(20))
    registrada_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("cuenta_operadora.id"))
    vigente_desde: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    recolector: Mapped[Recolector] = relationship()


class ResultadoOrden(Base):
    __tablename__ = "resultado_orden"
    __table_args__ = (
        CheckConstraint("resultado IN ('recogida','rechazada')", name="resultado"),
        CheckConstraint(
            "(resultado = 'recogida' AND motivo_rechazo_id IS NULL) OR "
            "(resultado = 'rechazada' AND motivo_rechazo_id IS NOT NULL)",
            name="motivo_segun_resultado",
        ),
    )
    id: Mapped[uuid.UUID] = _pk()
    orden_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orden.id"), unique=True)
    resultado: Mapped[str] = mapped_column(String(20))
    motivo_rechazo_id: Mapped[uuid.UUID | None] = _fk("motivo_rechazo.id", nullable=True)
    observacion: Mapped[str | None] = mapped_column(String(500))
    confirmado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("cuenta_operadora.id"))
    ocurrido_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmado_at: Mapped[datetime] = _ts_now()


# --------------------------------------------------------------------------- pesaje


class Pesaje(Base):
    """Medición de material recibido (lote o individual). borrador → confirmado → anulado."""

    __tablename__ = "pesaje"
    __table_args__ = (
        CheckConstraint("estado IN ('borrador','confirmado','anulado')", name="estado"),
        CheckConstraint("origen_captura IN ('manual','baldes','foto_ia','dictado')", name="origen"),
        Index("ix_pesaje_gremio_fecha", "gremio_id", "fecha_medicion"),
        Index("ix_pesaje_recolector_fecha", "recolector_id", "fecha_medicion"),
    )
    id: Mapped[uuid.UUID] = _pk()
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    gremio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gremio.id"))
    recolector_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recolector.id"))
    proveedor_referencia: Mapped[str | None] = mapped_column(String(120))
    fecha_medicion: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    origen_captura: Mapped[str] = mapped_column(String(20))
    estado: Mapped[str] = mapped_column(String(20), server_default="borrador", default="borrador")
    numero_tiquete: Mapped[str | None] = mapped_column(String(40))
    emisor_tiquete: Mapped[str | None] = mapped_column(String(120))
    torre_origen_id: Mapped[uuid.UUID | None] = _fk("torre.id", nullable=True)
    unidad_medida_id: Mapped[uuid.UUID | None] = _fk("unidad.id", nullable=True)
    observacion: Mapped[str | None] = mapped_column(String(500))
    creado_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("cuenta_operadora.id"))
    confirmado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cuenta_operadora.id"))
    confirmado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sustituye_pesaje_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pesaje.id"))
    motivo_correccion: Mapped[str | None] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, server_default="1", default=1)
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    lineas: Mapped[list[LineaPesaje]] = relationship(
        cascade="all, delete-orphan", order_by="LineaPesaje.id", lazy="selectin"
    )
    ordenes: Mapped[list[PesajeOrden]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class LineaPesaje(Base):
    __tablename__ = "linea_pesaje"
    __table_args__ = (
        UniqueConstraint("pesaje_id", "material_id"),
        CheckConstraint("metodo_medicion IN ('bascula','conversion_balde')", name="metodo"),
        CheckConstraint("kg_aceptados >= 0 AND kg_rechazados >= 0", name="kg_no_negativos"),
        CheckConstraint("kg_aceptados + kg_rechazados > 0", name="algun_peso"),
        CheckConstraint("kg_rechazados = 0 OR motivo_rechazo_id IS NOT NULL", name="motivo_si_rechazo"),
        CheckConstraint(
            "metodo_medicion = 'bascula' OR (cantidad_aceptada IS NOT NULL AND cantidad_rechazada IS NOT NULL "
            "AND version_equivalencia_id IS NOT NULL)",
            name="conversion_completa",
        ),
    )
    id: Mapped[uuid.UUID] = _pk()
    pesaje_id: Mapped[uuid.UUID] = _fk("pesaje.id", ondelete="CASCADE")
    material_id: Mapped[uuid.UUID] = _fk("material.id")
    metodo_medicion: Mapped[str] = mapped_column(String(20))
    kg_aceptados: Mapped[Decimal] = mapped_column(KG)
    kg_rechazados: Mapped[Decimal] = mapped_column(KG)
    motivo_rechazo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("motivo_rechazo.id"))
    cantidad_aceptada: Mapped[Decimal | None] = mapped_column(KG)
    cantidad_rechazada: Mapped[Decimal | None] = mapped_column(KG)
    version_equivalencia_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("version_equivalencia.id"))
    precio_kg_aplicado: Mapped[Decimal | None] = mapped_column(PRECIO)
    version_precio_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("version_precio_material.id"))


class PesajeOrden(Base):
    """Procedencia de un lote. No tiene columna de kilos: vincular no reparte peso."""

    __tablename__ = "pesaje_orden"
    __table_args__ = (PrimaryKeyConstraint("pesaje_id", "orden_id"),)
    pesaje_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pesaje.id", ondelete="CASCADE"))
    orden_id: Mapped[uuid.UUID] = _fk("orden.id")


class EntregaDirecta(Base):
    __tablename__ = "entrega_directa"
    id: Mapped[uuid.UUID] = _pk()
    pesaje_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pesaje.id"), unique=True)
    punto_recepcion_id: Mapped[uuid.UUID] = _fk("punto_recepcion.id")
    unidad_id: Mapped[uuid.UUID | None] = _fk("unidad.id", nullable=True)
    participante_id: Mapped[uuid.UUID | None] = _fk("participante.id", nullable=True)
    recibida_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("cuenta_operadora.id"))
    created_at: Mapped[datetime] = _ts_now()


# --------------------------------------------------------------------------- incentivos


class VersionReglaIncentivo(Base):
    __tablename__ = "version_regla_incentivo"
    __table_args__ = (
        CheckConstraint("modalidad IN ('entrega_valida','entrega_directa','kg_individual')", name="modalidad"),
        CheckConstraint("ambito_tipo IN ('global','gremio','conjunto')", name="ambito"),
        CheckConstraint("(ambito_tipo = 'global') = (ambito_id IS NULL)", name="ambito_id"),
        CheckConstraint("vigente_hasta IS NULL OR vigente_hasta > vigente_desde", name="vigencia"),
    )
    id: Mapped[uuid.UUID] = _pk()
    codigo: Mapped[str] = mapped_column(String(60))
    modalidad: Mapped[str] = mapped_column(String(30))
    ambito_tipo: Mapped[str] = mapped_column(String(20))
    ambito_id: Mapped[uuid.UUID | None] = mapped_column()
    parametros: Mapped[dict[str, Any]] = mapped_column(JSONB)
    vigente_desde: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aprobada_por: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = _ts_now()


class MovimientoPuntos(Base):
    """Libro inmutable. El saldo es la suma de `delta`; `clave_aplicacion` evita doble abono."""

    __tablename__ = "movimiento_puntos"
    __table_args__ = (
        CheckConstraint("tipo IN ('abono','debito_canje','reversion','reintegro')", name="tipo"),
        CheckConstraint("tipo <> 'abono' OR delta > 0", name="abono_positivo"),
        Index("ix_movimiento_participante_fecha", "participante_id", "ocurrido_at"),
    )
    id: Mapped[uuid.UUID] = _pk()
    participante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participante.id"))
    unidad_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("unidad.id"))
    torre_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("torre.id"))
    delta: Mapped[Decimal] = mapped_column(PUNTOS)
    tipo: Mapped[str] = mapped_column(String(20))
    version_regla_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("version_regla_incentivo.id"))
    resultado_orden_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("resultado_orden.id"))
    entrega_directa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entrega_directa.id"))
    pesaje_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pesaje.id"))
    revierte_movimiento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("movimiento_puntos.id"))
    clave_aplicacion: Mapped[str] = mapped_column(String(160), unique=True)
    ocurrido_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts_now()


# --------------------------------------------------------------------------- educación


class ContenidoEducativo(Base):
    __tablename__ = "contenido_educativo"
    __table_args__ = (CheckConstraint("tipo IN ('video','imagen','texto')", name="tipo"),)
    id: Mapped[uuid.UUID] = _pk()
    titulo: Mapped[str] = mapped_column(String(160))
    tipo: Mapped[str] = mapped_column(String(20))
    recurso: Mapped[str | None] = mapped_column(String(500))
    texto: Mapped[str | None] = mapped_column(Text)
    general: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), default=False)
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = _ts_now()


class ContenidoMotivo(Base):
    __tablename__ = "contenido_motivo"
    __table_args__ = (PrimaryKeyConstraint("contenido_id", "motivo_rechazo_id"),)
    contenido_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contenido_educativo.id", ondelete="CASCADE"))
    motivo_rechazo_id: Mapped[uuid.UUID] = _fk("motivo_rechazo.id")


class ContenidoMaterial(Base):
    __tablename__ = "contenido_material"
    __table_args__ = (PrimaryKeyConstraint("contenido_id", "material_id"),)
    contenido_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contenido_educativo.id", ondelete="CASCADE"))
    material_id: Mapped[uuid.UUID] = _fk("material.id")


# --------------------------------------------------------------------------- técnico


class OperacionIdempotente(Base):
    """Clave de reintento por actor y ruta; guarda la respuesta exitosa original."""

    __tablename__ = "operacion_idempotente"
    __table_args__ = (
        UniqueConstraint("actor", "ruta", "clave"),
        CheckConstraint("estado IN ('en_proceso','completada')", name="estado"),
    )
    id: Mapped[uuid.UUID] = _pk()
    actor: Mapped[str] = mapped_column(String(120))
    ruta: Mapped[str] = mapped_column(String(200))
    clave: Mapped[str] = mapped_column(String(128))
    huella: Mapped[str] = mapped_column(String(64))
    estado: Mapped[str] = mapped_column(String(20))
    codigo_http: Mapped[int | None] = mapped_column(Integer)
    respuesta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _ts_now()
    expira_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ReferenciaLocal(Base):
    """Correspondencia de IDs temporales de la tablet con IDs del servidor (sincronización)."""

    __tablename__ = "referencia_local"
    __table_args__ = (PrimaryKeyConstraint("actor", "referencia_local"),)
    actor: Mapped[str] = mapped_column(String(160))
    referencia_local: Mapped[str] = mapped_column(String(128))
    recurso_tipo: Mapped[str] = mapped_column(String(40))
    recurso_id: Mapped[uuid.UUID] = mapped_column()
    created_at: Mapped[datetime] = _ts_now()


class EventoDominio(Base):
    """Historia de acciones relevantes. No copia teléfonos ni mensajes."""

    __tablename__ = "evento_dominio"
    id: Mapped[uuid.UUID] = _pk()
    tipo: Mapped[str] = mapped_column(String(60))
    solicitud_id: Mapped[uuid.UUID | None] = _fk("solicitud.id", nullable=True)
    orden_id: Mapped[uuid.UUID | None] = _fk("orden.id", nullable=True)
    pesaje_id: Mapped[uuid.UUID | None] = _fk("pesaje.id", nullable=True)
    actor_tipo: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[uuid.UUID | None] = mapped_column()
    datos: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), default=dict)
    ocurrido_at: Mapped[datetime] = _ts_now()


class EventoSalida(Base):
    """Bandeja de salida (outbox) de avisos al residente vía el bot.

    El destino se referencia por `participante_id`; el celular se resuelve al entregar.
    """

    __tablename__ = "evento_salida"
    __table_args__ = (
        CheckConstraint("estado IN ('pendiente','en_envio','enviado','fallido','descartado')", name="estado"),
        Index("ix_evento_salida_pendientes", "estado", "proximo_intento_at"),
    )
    id: Mapped[uuid.UUID] = _pk()
    tipo: Mapped[str] = mapped_column(String(40))
    participante_id: Mapped[uuid.UUID | None] = _fk("participante.id", nullable=True)
    solicitud_id: Mapped[uuid.UUID | None] = _fk("solicitud.id", nullable=True)
    orden_id: Mapped[uuid.UUID | None] = _fk("orden.id", nullable=True)
    datos: Mapped[dict[str, Any]] = mapped_column(JSONB)
    estado: Mapped[str] = mapped_column(String(20), server_default="pendiente", default="pendiente")
    intentos: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    proximo_intento_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    id_externo: Mapped[str | None] = mapped_column(String(200))
    ultimo_error: Mapped[str | None] = mapped_column(String(500))
    enviado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
