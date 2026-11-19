"""Utilidades de configuración de Meta (usa WHATSAPP_TOKEN de bot/.env).

    uv run python -m app.meta estado              # número, y qué apps reciben los webhooks de la cuenta
    uv run python -m app.meta suscribir           # conecta ESTA app a la cuenta de WhatsApp Business
    uv run python -m app.meta plantillas          # estado de las plantillas de Brota en Meta
    uv run python -m app.meta crear-plantillas    # las envía a aprobación (omite las que ya existen)

La cuenta (WABA) sale de WHATSAPP_WABA_ID en bot/.env o de --waba.
Si el webhook está verificado y suscrito a `messages` pero no llega ningún POST al bot,
casi siempre es porque la cuenta de WhatsApp Business (WABA) no tiene suscrita la app.
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx

from app.config import get_settings

# Plantillas de los avisos que pueden salir fuera de la ventana de 24 h (ver app/avisos.py:
# el orden de las variables coincide con PLANTILLAS de ese módulo). Categoría: UTILITY.
# Reglas de Meta: el texto no empieza ni termina en una variable; cada variable lleva ejemplo.
DEFINICIONES: dict[str, tuple[str, list[str]]] = {
    "brota_asignacion": (
        "🚲 {{1}} pasará por tu recolección {{2}} (solicitud {{3}}). Ten el material listo en la puerta. "
        "Brota 💚",
        ["Rosa", "hoy entre 2:00 p. m. y 4:00 p. m.", "BR-00018"],
    ),
    "brota_recoleccion": (
        "💚 ¡Gracias! Tu material llegó bien separado: ganaste {{1}} puntos y ahora tienes {{2}}. "
        "Sigue separando con Brota 🌱",
        ["10", "25"],
    ),
    "brota_rechazo": (
        "😕 Esta vez no se pudo llevar tu material: {{1}}. Escríbeme y te cuento cómo prepararlo para la "
        "próxima. Brota 🌱",
        ["material mojado"],
    ),
    "brota_nueva_orden": (
        "🆕 Nueva solicitud {{1}} en {{2}}: {{3}}. Asígnala en el panel de coordinación de Brota.",
        ["BR-00018", "Torre 3 · Apto 402", "Reciclable"],
    ),
}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    p = argparse.ArgumentParser(description="Configuración de la WhatsApp Cloud API")
    p.add_argument("accion", choices=["estado", "suscribir", "plantillas", "crear-plantillas"])
    p.add_argument("--waba", default=None, help="WhatsApp Business Account ID (por defecto, WHATSAPP_WABA_ID)")
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
