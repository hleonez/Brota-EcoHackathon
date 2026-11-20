"""M11 · Sincronización offline de la tablet.

Cada operación usa su propia transacción y su `operacion_id` como clave de idempotencia
(por cuenta y dispositivo). Repetir el lote no duplica kilos ni puntos. Si una dependencia
falla, las dependientes quedan `bloqueada`. Las referencias locales (`referencia_local`)
se resuelven a IDs del servidor y se devuelven en `referencias`.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errores import AppError, prohibido
from app.core.idempotencia import ejecutar_idempotente
from app.core.seguridad import Actor, actor_operador
from app.core.tipos import Entrada, InstanteEntrada, ahora
from app.db import get_db
from app.models import ReferenciaLocal
from app.modulos import coordinacion, pesajes

router = APIRouter(tags=["sincronización"])

Accion = Literal[
    "crear_pesaje",
    "actualizar_borrador_pesaje",
    "confirmar_pesaje",
    "registrar_entrega_directa",
    "asignar_orden",
    "programar_orden",
    "registrar_resultado_orden",
]


class OperacionIn(Entrada):
    operacion_id: str = Field(min_length=1, max_length=128)
    accion: Accion
    recurso_id: str | None = Field(default=None, max_length=128)
    referencia_local: str | None = Field(default=None, max_length=128)
    depende_de: list[str] = Field(default_factory=list, max_length=50)
    creada_local_at: InstanteEntrada
    datos: dict[str, Any]


class SyncIn(Entrada):
    dispositivo_id: str = Field(min_length=1, max_length=80)
    operaciones: list[OperacionIn] = Field(min_length=1)


# accion -> (modelo de datos, crea recurso, función)
_ACCIONES: dict[str, tuple[type[BaseModel], bool, Callable[..., BaseModel]]] = {
    "programar_orden": (coordinacion.ProgramacionIn, False, lambda db, a, rid, d: coordinacion.programar(db, a, rid, d)),
    "crear_pesaje": (pesajes.PesajeIn, True, lambda db, a, rid, d: pesajes.crear_pesaje(db, a, d)),
    "registrar_entrega_directa": (
        pesajes.EntregaDirectaIn, True, lambda db, a, rid, d: pesajes.registrar_entrega_directa(db, a, d)
    ),
    "actualizar_borrador_pesaje": (
        pesajes.PesajePatch, False, lambda db, a, rid, d: pesajes.actualizar_borrador(db, a, rid, d)
    ),
    "confirmar_pesaje": (pesajes.ConfirmacionIn, False, lambda db, a, rid, d: pesajes.confirmar(db, a, rid, d)),
    "asignar_orden": (coordinacion.AsignacionIn, False, lambda db, a, rid, d: coordinacion.asignar(db, a, rid, d)),
    "registrar_resultado_orden": (
        coordinacion.ResultadoIn, False, lambda db, a, rid, d: coordinacion.registrar_resultado(db, a, rid, d)
    ),
}


def _orden_topologico(ops: list[OperacionIn]) -> list[OperacionIn]:
    ids = [o.operacion_id for o in ops]
    if len(set(ids)) != len(ids):
        raise AppError(400, "BAD_REQUEST", "operacion_id repetido en el lote.")
    por_id = {o.operacion_id: o for o in ops}
    visitado: dict[str, int] = {}
    orden: list[OperacionIn] = []

    def visitar(oid: str) -> None:
        estado = visitado.get(oid)
        if estado == 1:
            raise AppError(400, "BAD_REQUEST", "Dependencias cíclicas en el lote.")
        if estado == 2:
            return
        visitado[oid] = 1
        for dep in por_id[oid].depende_de:
            if dep in por_id:
                visitar(dep)
        visitado[oid] = 2
        orden.append(por_id[oid])

    for o in ops:
        visitar(o.operacion_id)
    return orden


def _resolver(db: Session, ambito: str, valor: str | None, locales: dict[str, uuid.UUID]) -> uuid.UUID | None:
    if valor is None:
        return None
    if valor in locales:
        return locales[valor]
    ref = db.get(ReferenciaLocal, (ambito, valor))
    if ref is not None:
        locales[valor] = ref.recurso_id
        return ref.recurso_id
    try:
        return uuid.UUID(valor)
    except ValueError:
        raise AppError(409, "DEPENDENCY_PENDING", f"La referencia local {valor} aún no existe en el servidor.") from None


def sincronizar(db: Session, actor: Actor, lote: SyncIn) -> dict[str, Any]:
    if not actor.gremios_coordinados and actor.trabajador_id is None:
        raise prohibido("La sincronización operativa es para coordinación o para el trabajador asignado.")
    s = get_settings()
    if len(lote.operaciones) > s.sync_max_operaciones:
        raise AppError(400, "BAD_REQUEST", f"Máximo {s.sync_max_operaciones} operaciones por lote.")
    ordenadas = _orden_topologico(lote.operaciones)
    ambito = f"{actor.clave}|{lote.dispositivo_id}"
    locales: dict[str, uuid.UUID] = {}
    estados: dict[str, str] = {}
    resultados: dict[str, dict[str, Any]] = {}
    limite_antiguedad = ahora() - timedelta(hours=s.idempotencia_retencion_horas)

    for op in ordenadas:
        r: dict[str, Any] = {"operacion_id": op.operacion_id}
        fallidas = [d for d in op.depende_de if d in estados and estados[d] not in ("aplicada", "repetida")]
        if fallidas:
            r.update(estado="bloqueada", codigo_http=424, error={"code": "DEPENDENCY_FAILED", "message": f"Falló {fallidas[0]}"})
        elif op.creada_local_at < limite_antiguedad:
            r.update(
                estado="rechazada", codigo_http=409,
                error={"code": "OPERATION_TOO_OLD", "message": "Operación fuera de la ventana offline; requiere revisión."},
            )
        else:
            modelo, crea, fn = _ACCIONES[op.accion]
            try:
                if actor.trabajador_id is not None and not actor.gremios_coordinados and op.accion != "registrar_resultado_orden":
                    raise prohibido("El trabajador solo registra el resultado de su asignación.")
                datos = TypeAdapter(modelo).validate_python(op.datos)
                recurso = None if crea else _resolver(db, ambito, op.recurso_id, locales)
                if not crea and recurso is None:
                    raise AppError(422, "VALIDATION_ERROR", "recurso_id es obligatorio para esta acción.")

                def _run(op=op, datos=datos, recurso=recurso, fn=fn, crea=crea):
                    out = fn(db, actor, recurso, datos)
                    if crea and op.referencia_local:
                        db.merge(
                            ReferenciaLocal(
                                actor=ambito, referencia_local=op.referencia_local,
                                recurso_tipo="pesaje", recurso_id=out.id,  # type: ignore[attr-defined]
                            )
                        )
                        db.flush()
                    return (201 if crea else 200), {"data": out.model_dump(mode="json")}

                cuerpo = {"accion": op.accion, "recurso_id": op.recurso_id, "datos": op.datos}
                (codigo, resp), repetida = ejecutar_idempotente(
                    db, ambito, f"sync:{op.accion}", op.operacion_id, cuerpo, _run
                )
                r.update(estado="repetida" if repetida else "aplicada", codigo_http=codigo, data=resp.get("data"))
                if crea and op.referencia_local and resp.get("data", {}).get("id"):
                    locales[op.referencia_local] = uuid.UUID(resp["data"]["id"])
            except ValidationError as e:
                db.rollback()
                campos = {".".join(str(x) for x in err["loc"]) or "datos": err["msg"] for err in e.errors()}
                r.update(estado="rechazada", codigo_http=422,
                         error={"code": "VALIDATION_ERROR", "message": "Revisa los campos", "fields": campos})
            except AppError as e:
                db.rollback()
                r.update(
                    estado="conflicto" if e.status == 409 else "rechazada",
                    codigo_http=e.status,
                    error=e.cuerpo(None)["error"],
                )
        estados[op.operacion_id] = r["estado"]
        resultados[op.operacion_id] = r

    return {
        "dispositivo_id": lote.dispositivo_id,
        "resultados": [resultados[o.operacion_id] for o in lote.operaciones],
        "referencias": {k: str(v) for k, v in locales.items()},
    }


@router.post("/sync")
def post_sync(lote: SyncIn, actor: Actor = Depends(actor_operador), db: Session = Depends(get_db)):
    return {"data": sincronizar(db, actor, lote)}


