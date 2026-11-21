"""M12 · Salud, capacidades y sesiones de operadores."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errores import AppError
from app.core import limite_acceso
from app.core.seguridad import HASH_SENUELO, emitir_token, verificar_pin
from app.core.tipos import Entrada
from app.db import get_db, get_engine
from app.models import CuentaOperadora

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
                "ia_mensajes": False,  # texto, audio y fotos del vecino (M06)
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
            "ia_disponible": False,
            "estados_orden": ["nueva", "asignada", "programada", "recogida", "rechazada", "cancelada"],
        }
    }


class SesionIn(Entrada):
    usuario: str = Field(min_length=1, max_length=60)
    pin: str = Field(min_length=4, max_length=12)


@router.post("/auth/sesiones", status_code=201)
def iniciar_sesion(datos: SesionIn, request: Request, db: Session = Depends(get_db)) -> dict:
    usuario = datos.usuario.strip().lower()
    ip = request.client.host if request.client else "desconocida"
    espera = limite_acceso.segundos_de_espera(usuario, ip)
    if espera:
        minutos = max(1, -(-espera // 60))
        raise AppError(
            429, "TOO_MANY_ATTEMPTS",
            f"Demasiados intentos fallidos. Espera {minutos} min y vuelve a intentar.",
            extra={"reintentar_en_segundos": espera}, headers={"Retry-After": str(espera)},
        )
    cuenta = db.execute(select(CuentaOperadora).where(CuentaOperadora.usuario == usuario)).scalar_one_or_none()
    # Con usuario inexistente se verifica igual contra un hash señuelo: la respuesta tarda lo mismo
    # y no revela qué usuarios existen.
    ok = verificar_pin(datos.pin, cuenta.pin_hash if cuenta and cuenta.pin_hash else HASH_SENUELO)
    if cuenta is None or not ok or not cuenta.activo:
        limite_acceso.registrar_fallo(usuario, ip)
        raise AppError(401, "INVALID_CREDENTIALS", "Usuario o contraseña incorrectos.")
    limite_acceso.registrar_exito(usuario)
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
