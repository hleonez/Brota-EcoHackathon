"""M12 · Salud, capacidades y sesiones de operadores."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errores import AppError
from app.core.seguridad import emitir_token, verificar_pin
from app.core.tipos import Entrada
from app.db import get_db, get_engine
from app.models import CuentaOperadora
from app.modulos.ia import proveedor_autorizado

CONTRATO_VERSION = "0.3-ecoconecta.2"

salud = APIRouter(tags=["salud"])
router = APIRouter(tags=["sistema"])


@salud.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@salud.get("/health/ready")
def ready() -> JSONResponse:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return JSONResponse({"status": "ready"})


@router.get("/capacidades")
def capacidades() -> dict:
    s = get_settings()
    ia_activa = proveedor_autorizado()
    return {
        "data": {
            "version_contrato": CONTRATO_VERSION,
            "modulos": {
                "identidad": True,
                "territorio": True,
                "solicitudes": True,
                "coordinacion": True,
                "pesajes": True,
                "entregas_directas": True,
                "puntos": True,
                "canjes": False,
                "archivos_ia": False,
                "ia_mensajes": ia_activa,  # texto, audio y fotos del vecino (M06)
                "educacion_avisos": True,
                "liga": True,
                "reportes": True,
                "configuracion": True,
                "sincronizacion": True,
            },
            "decimales": {"kg": 3, "puntos": 2, "precio": 4, "formato": "string con punto"},
            "avisos": {"modo": s.avisos_modo, "max_intentos": s.avisos_max_intentos},
            "sync": {
                "max_operaciones": s.sync_max_operaciones,
                "ventana_offline_horas": s.idempotencia_retencion_horas,
                "acciones": [
                    "crear_pesaje",
                    "actualizar_borrador_pesaje",
                    "confirmar_pesaje",
                    "registrar_entrega_directa",
                    "asignar_orden",
                    "programar_orden",
                    "registrar_resultado_orden",
                ],
            },
            "idempotencia": {"retencion_horas": s.idempotencia_retencion_horas},
            "registro": {"politica_datos_version": s.politica_datos_version, "canal": "whatsapp"},
            "reglas": {"solicitud_abierta_unica": s.regla_solicitud_abierta},
            "zona_horaria": s.zona_horaria,
            "piloto": "restringido",
            "ia_disponible": ia_activa,
            "estados_orden": ["nueva", "asignada", "programada", "recogida", "rechazada", "cancelada"],
        }
    }


class SesionIn(Entrada):
    usuario: str = Field(min_length=1, max_length=60)
    pin: str = Field(min_length=4, max_length=12)


@router.post("/auth/sesiones", status_code=201)
def iniciar_sesion(datos: SesionIn, db: Session = Depends(get_db)) -> dict:
    cuenta = db.execute(
        select(CuentaOperadora).where(CuentaOperadora.usuario == datos.usuario.lower())
    ).scalar_one_or_none()
    ok = verificar_pin(datos.pin, cuenta.pin_hash if cuenta else None)
    if cuenta is None or not ok or not cuenta.activo:
        raise AppError(401, "INVALID_CREDENTIALS", "Usuario o PIN incorrectos.")
    token, segundos = emitir_token(cuenta.id)
    return {
        "data": {
            "token": token,
            "tipo": "Bearer",
            "expira_en": segundos,
            "cuenta": {
                "id": str(cuenta.id),
                "nombre": cuenta.nombre,
                "permisos": [
                    {"rol": p.rol, "gremio_id": str(p.gremio_id) if p.gremio_id else None} for p in cuenta.permisos
                ],
            },
        }
    }
