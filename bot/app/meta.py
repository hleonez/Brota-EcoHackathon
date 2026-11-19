"""Utilidades de configuración de Meta (usa WHATSAPP_TOKEN de bot/.env).

    uv run python -m app.meta estado      # número, y qué apps reciben los webhooks de la cuenta
    uv run python -m app.meta suscribir   # conecta ESTA app a la cuenta de WhatsApp Business

Si el webhook está verificado y suscrito a `messages` pero no llega ningún POST al bot,
casi siempre es porque la cuenta de WhatsApp Business (WABA) no tiene suscrita la app.
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx

from app.config import get_settings


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    p = argparse.ArgumentParser(description="Configuración de la WhatsApp Cloud API")
    p.add_argument("accion", choices=["estado", "suscribir"])
    p.add_argument("--waba", default=None, help="WhatsApp Business Account ID (por defecto, el del número)")
    a = p.parse_args()

    s = get_settings()
    h = {"Authorization": f"Bearer {s.whatsapp_token}"}
    base = s.graph_base()
    with httpx.Client(timeout=20) as c:
        num = c.get(f"{base}/{s.whatsapp_phone_number_id}",
                    params={"fields": "display_phone_number,verified_name,quality_rating"}, headers=h).json()
        if "error" in num:
            raise SystemExit(f"Meta rechazó el token o el Phone Number ID: {num['error'].get('message')}")
        print(f"Número: {num.get('display_phone_number')} · {num.get('verified_name')}")
        waba = a.waba
        if waba is None:
            raise SystemExit("Indica --waba <WhatsApp Business Account ID> (está en Configuración de la API).")
        if a.accion == "suscribir":
            r = c.post(f"{base}/{waba}/subscribed_apps", headers=h).json()
            print("Suscripción:", json.dumps(r, ensure_ascii=False))
        apps = c.get(f"{base}/{waba}/subscribed_apps", headers=h).json()
        print("Apps que reciben los webhooks de esta cuenta:")
        for x in apps.get("data", []):
            d = x.get("whatsapp_business_api_data", {})
            print(f"  · {d.get('name')} (app_id {d.get('id')})")


if __name__ == "__main__":
    main()
