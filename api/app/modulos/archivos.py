"""Evidencia operativa en disco local.

La foto del tiquete se guarda aquí. La foto y el audio del vecino que entran por
`POST /v1/ia/interpretar` no pasan por este módulo. No hay almacenamiento de objetos.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errores import no_encontrado, prohibido
from app.core.seguridad import Actor, actor_operador
from app.core.tipos import ahora
from app.db import get_db, get_sessionmaker
from app.models import Archivo, Pesaje, PesajeArchivo

log = logging.getLogger("brota.archivos")
router = APIRouter(tags=["archivos"])


def directorio() -> Path:
    base = Path(get_settings().archivos_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base.resolve()


def ruta_en_disco(storage_key: str) -> Path:
    if (
        not storage_key
        or storage_key.startswith(".")
        or "/" in storage_key
        or "\\" in storage_key
        or storage_key in {".", ".."}
    ):
        raise no_encontrado("archivo")
    base = directorio()
    destino = (base / storage_key).resolve()
    if not destino.is_relative_to(base):
        raise no_encontrado("archivo")
    return destino


def guardar_bytes(*, proposito: str, mime: str, contenido: bytes) -> Archivo:
    """Escribe el contenido con un nombre uuid. No añade la fila: el llamador la confirma en su transacción."""
    clave = str(uuid.uuid4())
    destino = directorio() / clave
    temporal = directorio() / f".{clave}.tmp"
    temporal.write_bytes(contenido)
    temporal.replace(destino)
    return Archivo(
        proposito=proposito,
        mime=mime,
        tamano=len(contenido),
        sha256=hashlib.sha256(contenido).hexdigest(),
        storage_key=clave,
    )


def borrar_disco(storage_key: str) -> None:
    try:
        ruta_en_disco(storage_key).unlink(missing_ok=True)
    except OSError:
        log.warning("No se pudo borrar el fichero %s", storage_key)


def depurar_vencidos(db: Session) -> int:
    """Borra del disco lo ya vencido y deja la fila con `eliminado_at`. No toca el pesaje."""
    instante = ahora()
    vencidos = db.execute(
        select(Archivo).where(
            Archivo.expira_at.is_not(None),
            Archivo.expira_at < instante,
            Archivo.eliminado_at.is_(None),
        )
    ).scalars().all()
    borrados = 0
    for archivo in vencidos:
        try:
            ruta_en_disco(archivo.storage_key).unlink(missing_ok=True)
        except OSError:
            log.warning("Sigue en disco el archivo vencido %s", archivo.id)
            continue
        archivo.eliminado_at = instante
        borrados += 1
    db.flush()
    return borrados


def depurar_al_arrancar() -> None:
    try:
        with get_sessionmaker()() as db:
            n = depurar_vencidos(db)
            db.commit()
            if n:
                log.info("Archivos vencidos depurados al arrancar: %s", n)
    except Exception:
        log.warning("No se pudieron depurar archivos vencidos al arrancar", exc_info=True)


def depurar_en_sesion_propia() -> None:
    """Confirma la depuración aparte, para que un borrador fallido no la deshaga."""
    with get_sessionmaker()() as db:
        depurar_vencidos(db)
        db.commit()


@router.get("/archivos/{archivo_id}")
def get_archivo(
    archivo_id: uuid.UUID,
    actor: Actor = Depends(actor_operador),
    db: Session = Depends(get_db),
):
    """Bytes de la evidencia. Solo la coordinación del gremio del pesaje vinculado."""
    archivo = db.get(Archivo, archivo_id)
    if archivo is None or archivo.eliminado_at is not None:
        raise no_encontrado("archivo")
    gremios = db.execute(
        select(Pesaje.gremio_id)
        .join(PesajeArchivo, PesajeArchivo.pesaje_id == Pesaje.id)
        .where(PesajeArchivo.archivo_id == archivo.id)
    ).scalars().all()
    if not gremios:
        raise no_encontrado("archivo")
    if not any(actor.coordina(gremio_id) for gremio_id in gremios):
        raise prohibido("Solo la coordinación de este gremio puede ver este archivo.")
    destino = ruta_en_disco(archivo.storage_key)
    if not destino.is_file():
        raise no_encontrado("archivo")
    return FileResponse(destino, media_type=archivo.mime, filename=archivo.storage_key)
