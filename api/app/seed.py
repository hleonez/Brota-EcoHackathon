"""Datos semilla del piloto (Villas de San Pablo · Brisas).

Uso:  uv run python -m app.seed

Se puede ejecutar varias veces: solo crea lo que falta (busca por código / usuario).

IMPORTANTE: torres, viviendas, precios y equivalencias son VALORES DE EJEMPLO para la demo.
Reemplázalos con la lista real de Asorescatar, el número real de viviendas y el peso real de un
balde de la huerta antes de mostrar cifras como reales.

PIN de las cuentas: variable SEED_PIN (4–12 dígitos). Si no existe, se genera uno y se imprime.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.seguridad import hash_pin
from app.db import get_sessionmaker
from app.models import (
    CapacidadTorre,
    Conjunto,
    ContenidoEducativo,
    ContenidoMaterial,
    ContenidoMotivo,
    CuentaOperadora,
    Gremio,
    Huerta,
    Material,
    MotivoRechazo,
    PermisoOperador,
    PuntoRecepcion,
    Recolector,
    Residuo,
    TipoServicio,
    Torre,
    Unidad,
    VersionEquivalencia,
    VersionPrecioMaterial,
    VersionReglaIncentivo,
)
from app.seed_residuos import RESIDUOS

INICIO = datetime(2026, 11, 1, 5, 0, tzinfo=timezone.utc)  # 1-nov-2026 00:00 en Bogotá

GREMIOS = [("ASORESCATAR", "Asorescatar · Recicladores"), ("ECORAZON", "Huerta Ecorazón")]
SERVICIOS = [("RECICLABLES", "♻ Reciclable", "ASORESCATAR"), ("ORGANICOS", "🍌 Orgánico", "ECORAZON")]
# (código, nombre, gremio, precio COP/kg de ejemplo o None)
MATERIALES = [
    ("CARTON", "Cartón", "ASORESCATAR", "450"),
    ("ARCHIVO", "Archivo (papel blanco)", "ASORESCATAR", "700"),
    ("PLEGADIZA", "Plegadiza", "ASORESCATAR", "250"),
    ("PET", "PET (botellas)", "ASORESCATAR", "1000"),
    ("PLASTICO", "Plástico soplado", "ASORESCATAR", "600"),
    ("VIDRIO", "Vidrio", "ASORESCATAR", "100"),
    ("CHATARRA", "Chatarra", "ASORESCATAR", "600"),
    ("ALUMINIO", "Aluminio", "ASORESCATAR", "3500"),
    ("ORGANICOS", "Residuos orgánicos", "ECORAZON", None),
]
MOTIVOS = [
    ("MOJADO", "Material mojado", None),
    ("MEZCLADO", "Material mezclado", None),
    ("CONTAMINADO", "Material contaminado", None),
    ("NO_APROVECHABLE", "No es aprovechable", None),
]
PUNTOS = [("ACOPIO_ASORESCATAR", "Punto de acopio Asorescatar", "ASORESCATAR"), ("HUERTA_ECORAZON", "Huerta Ecorazón", "ECORAZON")]
RECOLECTORES = {"ASORESCATAR": ["Rosa (demo)", "Jairo (demo)", "Marta (demo)"], "ECORAZON": ["Huertero demo 1", "Huertero demo 2"]}
TORRES = [("1", 110), ("2", 110), ("3", 110), ("4", 110), ("5", 110)]  # ≈550 viviendas (ejemplo)
CONTENIDOS = [
    ("Cómo entregar el cartón", "Entrégalo seco, doblado y sin grasa. Si se moja, déjalo secar antes de pedir.", ["MOJADO"], ["CARTON"], False, "separacion"),
    ("Separa bien tus reciclables", "Plástico, papel, vidrio y metal limpios y secos; sin restos de comida.", ["MEZCLADO", "CONTAMINADO"], [], False, "separacion"),
    ("Qué va a la huerta", "Cáscaras, restos de frutas y verduras, café y poda. Sin bolsas plásticas ni carne.", ["NO_APROVECHABLE"], ["ORGANICOS"], False, "huerta"),
    ("Consejo de Brisa", "Separa en casa: reciclable limpio y seco por un lado, orgánico por otro. ¡Así todo brota!", [], [], True, "servicio"),
    ("Horarios y rutas del piloto", "Ejemplo del piloto: la coordinación acuerda el día y la hora. La preferencia del solicitante no programa la visita. Las rutas de demostración cubren el conjunto y el corredor comercial.", [], [], False, "horarios_rutas"),
]
CUENTAS = [
    ("coord-reciclaje", "Coordinación Asorescatar", [("coordinacion", "ASORESCATAR")]),
    ("coord-huerta", "Coordinación Huerta Ecorazón", [("coordinacion", "ECORAZON")]),
    ("fundacion", "Fundación Santo Domingo", [("fundacion", None)]),
    ("admin", "Administración Brota", [("admin", None)]),
]


def _uno(db: Session, modelo, **filtros):
    return db.execute(select(modelo).filter_by(**filtros)).scalar_one_or_none()


def sembrar(db: Session) -> dict[str, str]:
    creados: dict[str, str] = {}
    g = {}
    for cod, nom in GREMIOS:
        g[cod] = _uno(db, Gremio, codigo=cod) or Gremio(codigo=cod, nombre=nom)
        db.add(g[cod])
    db.flush()
    for cod, nom, gc in SERVICIOS:
        if not _uno(db, TipoServicio, codigo=cod):
            db.add(TipoServicio(codigo=cod, nombre=nom, gremio_id=g[gc].id))
    # Fichas de residuos: el contenido de ejemplo se actualiza en cada corrida (aún no hay edición en el panel).
    for i, (cod, nom, emoji, cat, acepta, gc, menu, sin, prep, evitar, alt, verif) in enumerate(RESIDUOS):
        r = _uno(db, Residuo, codigo=cod) or Residuo(codigo=cod)
        r.nombre, r.emoji, r.categoria, r.acepta, r.en_menu, r.orden = nom, emoji, cat, acepta, menu, (i + 1) * 10
        r.gremio_id = g[gc].id if gc else None
        r.sinonimos, r.preparacion, r.evitar, r.alternativa, r.verificaciones = sin, prep, evitar, alt, verif
        db.add(r)
    mat = {}
    for cod, nom, gc, precio in MATERIALES:
        m = _uno(db, Material, codigo=cod)
        if m is None:
            m = Material(codigo=cod, nombre=nom, gremio_id=g[gc].id)
            db.add(m)
            db.flush()
            if precio is not None:
                db.add(VersionPrecioMaterial(material_id=m.id, precio_kg=Decimal(precio), vigente_desde=INICIO))
        mat[cod] = m
    mot = {}
    for cod, nom, _gremio in MOTIVOS:
        mot[cod] = _uno(db, MotivoRechazo, codigo=cod) or MotivoRechazo(codigo=cod, nombre=nom)
        db.add(mot[cod])
    pr = {}
    for cod, nom, gc in PUNTOS:
        pr[cod] = _uno(db, PuntoRecepcion, codigo=cod) or PuntoRecepcion(codigo=cod, nombre=nom, gremio_id=g[gc].id)
        db.add(pr[cod])
    db.flush()
    if not _uno(db, VersionEquivalencia, gremio_id=g["ECORAZON"].id, recipiente="balde"):
        db.add(
            VersionEquivalencia(
                gremio_id=g["ECORAZON"].id, punto_recepcion_id=pr["HUERTA_ECORAZON"].id, recipiente="balde",
                kg_por_unidad=Decimal("8.000"), vigente_desde=INICIO,
            )
        )
    huerta = _uno(db, Huerta, nombre="Huerta Ecorazón (demo)")
    if huerta is None:
        huerta = Huerta(nombre="Huerta Ecorazón (demo)", gremio_id=g["ECORAZON"].id, ubicacion="Villas de San Pablo (ejemplo)")
        db.add(huerta)
        db.flush()
    for gc, nombres in RECOLECTORES.items():
        for n in nombres:
            if not _uno(db, Recolector, nombre=n, gremio_id=g[gc].id):
                db.add(Recolector(nombre=n, gremio_id=g[gc].id, tipo="huertero" if gc == "ECORAZON" else "reciclador", huerta_id=huerta.id if gc == "ECORAZON" else None))

    conj = _uno(db, Conjunto, nombre="Brisas de San Pablo")
    if conj is None:
        conj = Conjunto(nombre="Brisas de San Pablo", etapa="Villas de San Pablo · piloto")
        db.add(conj)
        db.flush()
    creados["conjunto_id"] = str(conj.id)
    for cod, viviendas in TORRES:
        t = _uno(db, Torre, conjunto_id=conj.id, codigo=cod)
        if t is None:
            t = Torre(conjunto_id=conj.id, codigo=cod, nombre=f"Torre {cod}")
            db.add(t)
            db.flush()
            db.add(CapacidadTorre(torre_id=t.id, numero_viviendas=viviendas, vigente_desde=INICIO))
            for piso in range(1, 6):
                for apto in range(1, 5):
                    db.add(Unidad(tipo="hogar", torre_id=t.id, referencia_local=f"{piso}{apto:02d}"))
    for ref, dir_ in (("Asadero El Corredor (demo)", "Corredor comercial"), ("Frutería La Brisa (demo)", "Corredor comercial")):
        if not _uno(db, Unidad, referencia_local=ref, tipo="negocio"):
            db.add(Unidad(tipo="negocio", referencia_local=ref, direccion_referencia=dir_))

    for codigo, modalidad, puntos in (("ENTREGA_VALIDA_V1", "entrega_valida", "10"), ("ENTREGA_DIRECTA_V1", "entrega_directa", "15")):
        if not _uno(db, VersionReglaIncentivo, codigo=codigo):
            db.add(
                VersionReglaIncentivo(
                    codigo=codigo, modalidad=modalidad, ambito_tipo="global", parametros={"puntos": puntos},
                    vigente_desde=INICIO, aprobada_por="Propuesta del plan (pendiente de validar con la Fundación)",
                )
            )
    db.flush()

    for titulo, texto, motivos, materiales, general, tema in CONTENIDOS:
        existente = _uno(db, ContenidoEducativo, titulo=titulo)
        if existente:
            if existente.tema != tema:
                existente.tema = tema
            continue
        c = ContenidoEducativo(titulo=titulo, tipo="texto", texto=texto, general=general, tema=tema, publicado=True)
        db.add(c)
        db.flush()
        for mc in motivos:
            db.add(ContenidoMotivo(contenido_id=c.id, motivo_rechazo_id=mot[mc].id))
        for mc in materiales:
            db.add(ContenidoMaterial(contenido_id=c.id, material_id=mat[mc].id))

    pin = os.environ.get("SEED_PIN") or ""
    nuevas = [u for u, _, _ in CUENTAS if not _uno(db, CuentaOperadora, usuario=u)]
    if nuevas and not pin:
        pin = f"{secrets.randbelow(10**6):06d}"
        creados["pin_generado"] = pin
    for usuario, nombre, permisos in CUENTAS:
        if usuario in nuevas:
            c = CuentaOperadora(usuario=usuario, nombre=nombre, pin_hash=hash_pin(pin))
            c.permisos = [PermisoOperador(rol=r, gremio_id=g[gc].id if gc else None) for r, gc in permisos]
            db.add(c)
    db.commit()
    creados["cuentas_nuevas"] = ", ".join(nuevas) or "ninguna"
    return creados


def main() -> None:
    with get_sessionmaker()() as db:
        info = sembrar(db)
    print("Semilla aplicada.")
    for k, v in info.items():
        print(f"  {k}: {v}")
    if "pin_generado" in info:
        print("  (Guarda el PIN: no se vuelve a mostrar. Usa SEED_PIN para fijarlo.)")


if __name__ == "__main__":
    main()
