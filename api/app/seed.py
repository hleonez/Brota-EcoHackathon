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

from app.config import get_settings
from app.core.seguridad import hash_pin, normalizar_celular
from app.db import get_sessionmaker
from app.models import (
    Aliado,
    CapacidadTorre,
    Conjunto,
    Consentimiento,
    ContenidoEducativo,
    ContenidoMaterial,
    ContenidoMotivo,
    CuentaOperadora,
    Gremio,
    HabilitacionPiloto,
    Huerta,
    ItemCanje,
    Material,
    MotivoRechazo,
    Participante,
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
    VinculoUnidad,
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
# (usuario, nombre, permisos [(rol, código de gremio)] o None, recolector (nombre, código de gremio) o None).
# Con recolector, el único permiso es su tipo y su gremio. Las otras cuentas no tienen trabajador.
CUENTAS = [
    ("coord-reciclaje", "Coordinación Asorescatar", [("coordinacion", "ASORESCATAR")], None),
    ("coord-huerta", "Coordinación Huerta Ecorazón", [("coordinacion", "ECORAZON")], None),
    ("fundacion", "Fundación Santo Domingo", [("fundacion", None)], None),
    ("admin", "Administración Brota", [("admin", None)], None),
    ("huertero-demo", "Huertero demo 1", None, ("Huertero demo 1", "ECORAZON")),
    ("reciclador-demo", "Rosa (demo)", None, ("Rosa (demo)", "ASORESCATAR")),
]
# (celular, nombre, unidad "negocio"|"hogar", habilitar en el piloto).
PARTICIPANTES = [
    ("573100000201", "Contacto Asadero El Corredor (demo)", "negocio", True),
    ("573100000101", "Residente Torre 1 apto 101", "hogar", True),
    ("573100000102", "Otro residente Torre 1 apto 101", "hogar", False),
]


def _uno(db: Session, modelo, **filtros):
    return db.execute(select(modelo).filter_by(**filtros)).scalar_one_or_none()


def _sembrar_participantes(db: Session, conjunto_id) -> str:
    """Tres contactos de ejemplo. Una segunda corrida no duplica vínculo ni habilitación."""
    admin = _uno(db, CuentaOperadora, usuario="admin")
    if admin is None:
        raise RuntimeError("La semilla necesita la cuenta admin para habilitar el piloto.")
    torre = _uno(db, Torre, conjunto_id=conjunto_id, codigo="1")
    hogar = _uno(db, Unidad, torre_id=torre.id, tipo="hogar", referencia_local="101") if torre else None
    negocio = _uno(db, Unidad, tipo="negocio", referencia_local="Asadero El Corredor (demo)")
    if hogar is None or negocio is None:
        raise RuntimeError("Faltan la vivienda Torre 1 apto 101 o el asadero de la semilla.")
    politica = get_settings().politica_datos_version
    unidades = {"hogar": hogar, "negocio": negocio}
    for celular, nombre, clave, habilitar in PARTICIPANTES:
        unidad = unidades[clave]
        normalizado = normalizar_celular(celular)
        p = db.execute(
            select(Participante).where(
                Participante.celular_normalizado == normalizado, Participante.estado != "eliminado"
            )
        ).scalar_one_or_none()
        if p is None and normalizado != celular:
            # Corridas anteriores guardaron el wa_id sin «+». Se reescribe para no duplicar.
            p = db.execute(
                select(Participante).where(
                    Participante.celular_normalizado == celular, Participante.estado != "eliminado"
                )
            ).scalar_one_or_none()
            if p is not None:
                p.celular_normalizado = normalizado
        if p is None:
            p = Participante(nombre=nombre, celular_normalizado=normalizado, estado="activo")
            db.add(p)
            db.flush()
        ultimo = db.execute(
            select(Consentimiento)
            .where(Consentimiento.participante_id == p.id)
            .order_by(Consentimiento.registrado_at.desc(), Consentimiento.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if ultimo is None or ultimo.decision != "aceptado" or ultimo.version_politica != politica:
            db.add(
                Consentimiento(
                    participante_id=p.id, version_politica=politica, decision="aceptado", canal="asistido"
                )
            )
        vinculo = db.execute(
            select(VinculoUnidad).where(
                VinculoUnidad.participante_id == p.id,
                VinculoUnidad.unidad_id == unidad.id,
                VinculoUnidad.vigente_hasta.is_(None),
            )
        ).scalar_one_or_none()
        if vinculo is None:
            tipo = "residente" if unidad.tipo == "hogar" else "contacto_negocio"
            db.add(VinculoUnidad(participante_id=p.id, unidad_id=unidad.id, tipo_vinculo=tipo))
        if not habilitar:
            continue
        ya = db.execute(
            select(HabilitacionPiloto).where(
                HabilitacionPiloto.participante_id == p.id, HabilitacionPiloto.unidad_id == unidad.id
            )
        ).scalar_one_or_none()
        if ya is None:
            db.add(
                HabilitacionPiloto(
                    participante_id=p.id,
                    unidad_id=unidad.id,
                    activo=True,
                    vigente_desde=INICIO,
                    habilitada_por=admin.id,
                )
            )
    return ", ".join(celular for celular, *_resto in PARTICIPANTES)


def _sembrar_canjes(db: Session, gremio_huerta) -> None:
    """Ejemplo: aliado de la huerta, bolsa de abono, plántula y descuento del corredor.

    El premio colectivo de la torre no es un ítem. Los costos y las existencias son de demostración.
    """
    aliado = _uno(db, Aliado, nombre="Huerta Ecorazón")
    if aliado is None:
        aliado = Aliado(nombre="Huerta Ecorazón", gremio_id=gremio_huerta.id)
        db.add(aliado)
        db.flush()
    premios = (
        ("Bolsa de abono", Decimal("20.00"), 40),
        ("Plántula", Decimal("15.00"), 40),
        ("Descuento del corredor", Decimal("25.00"), None),
    )
    for nombre, costo, existencias in premios:
        if _uno(db, ItemCanje, aliado_id=aliado.id, nombre=nombre):
            continue
        db.add(ItemCanje(aliado_id=aliado.id, nombre=nombre, costo_puntos=costo, existencias=existencias))


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
    nuevas = [usuario for usuario, *_resto in CUENTAS if not _uno(db, CuentaOperadora, usuario=usuario)]
    if nuevas and not pin:
        pin = f"{secrets.randbelow(10**6):06d}"
        creados["pin_generado"] = pin
    for usuario, nombre, permisos, recolector_ref in CUENTAS:
        if usuario not in nuevas:
            continue
        recolector = None
        if recolector_ref is not None:
            nombre_recolector, codigo_gremio = recolector_ref
            recolector = _uno(db, Recolector, nombre=nombre_recolector, gremio_id=g[codigo_gremio].id)
            if recolector is None:
                raise RuntimeError(f"Falta el recolector de la semilla: {nombre_recolector}")
        c = CuentaOperadora(
            usuario=usuario,
            nombre=nombre,
            pin_hash=hash_pin(pin),
            trabajador_id=recolector.id if recolector else None,
        )
        if recolector is not None:
            c.permisos = [PermisoOperador(rol=recolector.tipo, gremio_id=recolector.gremio_id)]
        else:
            c.permisos = [PermisoOperador(rol=rol, gremio_id=g[codigo].id if codigo else None) for rol, codigo in permisos]
        db.add(c)
    db.flush()
    creados["celulares"] = _sembrar_participantes(db, conj.id)
    _sembrar_canjes(db, g["ECORAZON"])
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
