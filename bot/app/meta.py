"""Utilidades de configuración de Meta (usa WHATSAPP_TOKEN de bot/.env).

    uv run python -m app.meta estado              # número, y qué apps reciben los webhooks de la cuenta
    uv run python -m app.meta suscribir           # conecta ESTA app a la cuenta de WhatsApp Business
    uv run python -m app.meta plantillas          # estado de las plantillas de Brota en Meta
    uv run python -m app.meta crear-plantillas    # las envía a aprobación (omite las que ya existen)
    uv run python -m app.meta perfil              # textos del perfil de WhatsApp (descripción, web…)
    uv run python -m app.meta perfil --foto assets/perfil-brisa.jpg   # y además la foto

La cuenta (WABA) sale de WHATSAPP_WABA_ID en bot/.env o de --waba.
Si el webhook está verificado y suscrito a `messages` pero no llega ningún POST al bot,
casi siempre es porque la cuenta de WhatsApp Business (WABA) no tiene suscrita la app.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from pathlib import Path

import httpx

from app.config import get_settings

# Plantillas de los avisos que pueden salir fuera de la ventana de 24 h (ver app/avisos.py:
# el orden de las variables coincide con PLANTILLAS de ese módulo). Categoría: UTILITY.
# Reglas de Meta: el texto no empieza ni termina en una variable; cada variable lleva ejemplo.
# Para que Meta las deje como UTILITY: solo información de UNA transacción (código, estado, datos),
# sin frases promocionales ni de ánimo («sigue separando…»). Un nombre borrado no se puede reusar en
# 30 días: por eso las versiones (_v2).
DEFINICIONES: dict[str, tuple[str, list[str]]] = {
    "brota_asignacion": (
        "🚲 {{1}} pasará por tu recolección {{2}} (solicitud {{3}}). Ten el material listo en la puerta. "
        "Brota 💚",
        ["Rosa", "hoy entre 2:00 p. m. y 4:00 p. m.", "BR-00018"],
    ),
    "brota_recoleccion_v2": (
        "Recolección {{1}}: tu material fue recibido. Puntos ganados: {{2}}. Saldo actual: {{3}} puntos.",
        ["BR-00018", "10", "25"],
    ),
    "brota_rechazo_v2": (
        "Recolección {{1}}: el material no se pudo recibir. Motivo: {{2}}. Responde a este mensaje si "
        "quieres indicaciones para la próxima vez.",
        ["BR-00018", "material mojado"],
    ),
    "brota_nueva_orden_v2": (
        "Nueva solicitud de recolección {{1}}. Ubicación: {{2}}. Servicio: {{3}}. Asígnala en el panel de "
        "coordinación.",
        ["BR-00018", "Torre 3 · Apto 402", "Reciclable"],
    ),
}


# Perfil del número en WhatsApp (lo que ve el vecino al tocar el nombre). Límites de Meta:
# about ≤ 139, description ≤ 512, hasta 2 websites. El NOMBRE visible no se cambia por aquí:
# se pide en WhatsApp Manager y Meta lo revisa.
PERFIL: dict[str, object] = {
    "about": "🌱 Brisa, asistente de reciclaje de Brota · Villas de San Pablo",
    "description": (
        "Soy Brisa 🌱. Pide aquí la recolección de tu material reciclable y orgánico, resuelve dudas "
        "sobre cómo separar y suma puntos para tu torre. Escríbeme o mándame una nota de voz o una foto."
    ),
    "address": "Villas de San Pablo, Barranquilla",
    "websites": ["https://github.com/hleonez/Brota-EcoHackathon"],
    "vertical": "OTHER",
}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    p = argparse.ArgumentParser(description="Configuración de la WhatsApp Cloud API")
    p.add_argument("accion", choices=["estado", "suscribir", "plantillas", "crear-plantillas", "perfil"])
    p.add_argument("--waba", default=None, help="WhatsApp Business Account ID (por defecto, WHATSAPP_WABA_ID)")
    p.add_argument("--foto", default=None, help="perfil: imagen JPG o PNG cuadrada (640×640 recomendado)")
    a = p.parse_args()

    s = get_settings()
    h = {"Authorization": f"Bearer {s.whatsapp_token}"}
    base = s.graph_base()
    waba = a.waba or s.whatsapp_waba_id or None
    with httpx.Client(timeout=20) as c:
        num = c.get(f"{base}/{s.whatsapp_phone_number_id}",
                    params={"fields": "display_phone_number,verified_name,quality_rating"}, headers=h).json()
        if "error" in num:
            raise SystemExit(f"Meta rechazó el token o el Phone Number ID: {num['error'].get('message')}")
        print(f"Número: {num.get('display_phone_number')} · {num.get('verified_name')}")
        if a.accion == "perfil":
            _perfil(c, base, h, s.whatsapp_phone_number_id, s.whatsapp_token, s.whatsapp_app_id, a.foto)
            return
        if waba is None:
            raise SystemExit("Indica --waba <WhatsApp Business Account ID> o WHATSAPP_WABA_ID en bot/.env.")
        if a.accion in ("plantillas", "crear-plantillas"):
            if a.accion == "crear-plantillas":
                _crear(c, base, h, waba, s.plantillas_idioma)
            _listar(c, base, h, waba)
            return
        if a.accion == "suscribir":
            r = c.post(f"{base}/{waba}/subscribed_apps", headers=h).json()
            print("Suscripción:", json.dumps(r, ensure_ascii=False))
        apps = c.get(f"{base}/{waba}/subscribed_apps", headers=h).json()
        print("Apps que reciben los webhooks de esta cuenta:")
        for x in apps.get("data", []):
            d = x.get("whatsapp_business_api_data", {})
            print(f"  · {d.get('name')} (app_id {d.get('id')})")


def _subir_foto(c: httpx.Client, base: str, h: dict[str, str], token: str, app_id: str, ruta: Path) -> str:
    """API de subida reanudable de Meta: abre una sesión en la app y sube los bytes; devuelve el handle."""
    datos = ruta.read_bytes()
    if len(datos) > 5 * 1024 * 1024:
        raise SystemExit("La foto pesa más de 5 MB.")
    tipo = mimetypes.guess_type(ruta.name)[0] or ""
    if tipo not in ("image/jpeg", "image/png"):
        raise SystemExit("La foto debe ser JPG o PNG.")
    if not app_id:
        app_id = c.get(f"{base}/app", headers=h).json().get("id", "")
    sesion = c.post(f"{base}/{app_id}/uploads", headers=h,
                    params={"file_name": ruta.name, "file_length": len(datos), "file_type": tipo}).json()
    if "id" not in sesion:
        raise SystemExit(f"Meta no abrió la subida: {sesion.get('error', {}).get('message', sesion)}")
    r = c.post(f"{base}/{sesion['id']}", content=datos,
               headers={"Authorization": f"OAuth {token}", "file_offset": "0"}).json()
    if "h" not in r:
        raise SystemExit(f"Meta no recibió la foto: {r.get('error', {}).get('message', r)}")
    return r["h"]


def _perfil(c: httpx.Client, base: str, h: dict[str, str], numero: str, token: str, app_id: str,
            foto: str | None) -> None:
    cuerpo: dict[str, object] = {"messaging_product": "whatsapp", **PERFIL}
    if foto:
        cuerpo["profile_picture_handle"] = _subir_foto(c, base, h, token, app_id, Path(foto))
        print(f"  + foto subida: {foto}")
    r = c.post(f"{base}/{numero}/whatsapp_business_profile", json=cuerpo, headers=h).json()
    if "error" in r:
        e = r["error"]
        raise SystemExit(f"Meta rechazó el perfil: {e.get('error_user_msg') or e.get('message')}")
    campos = "about,description,address,websites,vertical,profile_picture_url"
    ahora = c.get(f"{base}/{numero}/whatsapp_business_profile", headers=h, params={"fields": campos}).json()
    p = (ahora.get("data") or [{}])[0]
    print("Perfil actualizado:")
    for k in ("about", "description", "address", "websites", "vertical"):
        print(f"  · {k}: {p.get(k)}")
    print(f"  · foto: {'sí' if p.get('profile_picture_url') else 'no'}")


def _existentes(c: httpx.Client, base: str, h: dict[str, str], waba: str) -> dict[str, dict]:
    r = c.get(f"{base}/{waba}/message_templates", headers=h,
              params={"limit": 100, "fields": "name,language,status,category,rejected_reason"}).json()
    if "error" in r:
        raise SystemExit(f"No pude leer las plantillas: {r['error'].get('message')}")
    return {x["name"]: x for x in r.get("data", [])}


def _crear(c: httpx.Client, base: str, h: dict[str, str], waba: str, idioma: str) -> None:
    ya = _existentes(c, base, h, waba)
    for nombre, (texto, ejemplo) in DEFINICIONES.items():
        if nombre in ya:
            print(f"  = {nombre}: ya existe ({ya[nombre]['status']})")
            continue
        cuerpo = {
            "name": nombre, "language": idioma, "category": "UTILITY",
            "components": [{"type": "BODY", "text": texto, "example": {"body_text": [ejemplo]}}],
        }
        r = c.post(f"{base}/{waba}/message_templates", json=cuerpo, headers=h).json()
        if "error" in r:
            e = r["error"]
            print(f"  ✗ {nombre}: {e.get('error_user_msg') or e.get('message')}")
        else:
            print(f"  + {nombre}: enviada ({r.get('status')}, categoría {r.get('category')})")


def _listar(c: httpx.Client, base: str, h: dict[str, str], waba: str) -> None:
    ya = _existentes(c, base, h, waba)
    print("Plantillas de Brota:")
    for nombre in DEFINICIONES:
        x = ya.get(nombre)
        if x is None:
            print(f"  · {nombre}: no existe")
        else:
            motivo = f" · {x['rejected_reason']}" if x.get("rejected_reason") not in (None, "NONE") else ""
            print(f"  · {nombre}: {x['status']} ({x.get('category')}, {x.get('language')}){motivo}")


if __name__ == "__main__":
    main()
