"""Datos editables del programa: nombre, horario, días de recolección, contacto y saludo de Brisa.

`GET /v1/programa` es público (lo leen el bot y las páginas). `PATCH /v1/programa` es de
Administración: recibe solo las claves que cambian; `null` devuelve una clave a su valor por defecto.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Request
from pydantic import Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.idempotencia import escritura
from app.core.seguridad import Actor, actor_admin
from app.core.tipos import Entrada, Salida, ahora
from app.db import get_db
from app.models import ParametroPrograma
from app.modulos.comun import registrar_evento

router = APIRouter(tags=["programa"])

MAX_VALOR = 500

POR_DEFECTO: dict[str, str] = {
    "nombre_programa": "EcoConecta Villas de San Pablo",
    "horario_atencion": "Lunes a sábado, 8:00 a. m. a 5:00 p. m.",
    "dias_recoleccion": "Según la ruta de cada colectivo",
    "telefono_contacto": "",
    "correo_contacto": "",
    "mensaje_bienvenida": "",
}

_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ProgramaOut(Salida):
    nombre_programa: str
    horario_atencion: str
    dias_recoleccion: str
    telefono_contacto: str
    correo_contacto: str
    mensaje_bienvenida: str


class ProgramaPatch(Entrada):
    """Solo las claves que cambian. Una clave desconocida se rechaza; `null` vuelve al valor por defecto."""

    nombre_programa: str | None = Field(default=None, max_length=MAX_VALOR)
    horario_atencion: str | None = Field(default=None, max_length=MAX_VALOR)
    dias_recoleccion: str | None = Field(default=None, max_length=MAX_VALOR)
    telefono_contacto: str | None = Field(default=None, max_length=MAX_VALOR)
    correo_contacto: str | None = Field(default=None, max_length=MAX_VALOR)
    mensaje_bienvenida: str | None = Field(default=None, max_length=MAX_VALOR)

    @model_validator(mode="after")
    def _validar(self):
        if self.correo_contacto and not _CORREO.match(self.correo_contacto):
            raise ValueError("correo_contacto no parece un correo válido")
        if self.nombre_programa is not None and not self.nombre_programa:
            raise ValueError("nombre_programa no puede quedar vacío")
        return self


def leer_programa(db: Session) -> ProgramaOut:
    guardados = dict(db.execute(select(ParametroPrograma.clave, ParametroPrograma.valor)).all())
    return ProgramaOut(**{c: guardados.get(c, d) for c, d in POR_DEFECTO.items()})


@router.get("/programa")
def get_programa(db: Session = Depends(get_db)) -> dict:
    """Público: todas las claves, con el valor por defecto en las que no se han guardado."""
    return {"data": leer_programa(db).model_dump(mode="json")}


@router.patch("/programa")
def patch_programa(
    datos: ProgramaPatch, request: Request, actor: Actor = Depends(actor_admin), db: Session = Depends(get_db)
):
    def _fn():
        cambios = {c: getattr(datos, c) for c in POR_DEFECTO if c in datos.model_fields_set}
        for clave, valor in cambios.items():
            if valor is None:
                db.execute(delete(ParametroPrograma).where(ParametroPrograma.clave == clave))
                continue
            ins = pg_insert(ParametroPrograma).values(
                clave=clave, valor=valor, updated_at=ahora(), actualizado_por=actor.cuenta_id
            )
            db.execute(
                ins.on_conflict_do_update(
                    index_elements=["clave"],
                    set_={"valor": ins.excluded.valor, "updated_at": ins.excluded.updated_at,
                          "actualizado_por": ins.excluded.actualizado_por},
                )
            )
        if cambios:
            registrar_evento(db, "programa_actualizado", actor, datos={"claves": sorted(cambios)})
        db.flush()
        return leer_programa(db)

    return escritura(request, db, actor, datos, _fn)
