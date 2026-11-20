"""Simula un mensaje de WhatsApp contra el bot local, firmado como lo haría Meta.

Uso (con el bot corriendo en modo dry-run):
    uv run python -m app.simular "hola"
    uv run python -m app.simular --boton RECICLABLES
    uv run python -m app.simular --lista <torre_id>
    uv run python -m app.simular "puntos" --de 573001112233

Imprime lo que Brisa respondió (GET /dev/mensajes).
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import time
import uuid

import httpx

from app.config import get_settings


def payload(de: str, texto: str | None, boton: str | None, lista: str | None, nombre: str) -> dict:
    m: dict = {"from": de, "id": f"wamid.sim.{uuid.uuid4().hex}", "timestamp": str(int(time.time()))}
    if boton:
        m.update(type="interactive", interactive={"type": "button_reply", "button_reply": {"id": boton, "title": boton}})
    elif lista:
        m.update(type="interactive", interactive={"type": "list_reply", "list_reply": {"id": lista, "title": lista}})
    else:
        m.update(type="text", text={"body": texto or "hola"})
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "sim", "changes": [{"field": "messages", "value": {
            "messaging_product": "whatsapp",
            "contacts": [{"profile": {"name": nombre}, "wa_id": de}],
            "messages": [m],
        }}]}],
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Simula un mensaje entrante de WhatsApp")
    p.add_argument("texto", nargs="?", default=None)
    p.add_argument("--de", default="573001112233", help="wa_id del vecino (sin +)")
    p.add_argument("--boton", help="id del botón tocado (RECICLABLES, ORGANICOS, LOS_DOS, ACEPTO...)")
    p.add_argument("--lista", help="id de la fila elegida en una lista (p. ej. el id de la torre)")
    p.add_argument("--nombre", default="Vecino de prueba")
    p.add_argument("--url", default=None, help="URL del bot (por defecto http://localhost:PORT)")
    p.add_argument("--espera", type=float, default=2.0, help="segundos a esperar la respuesta")
    a = p.parse_args()
    # La consola de Windows usa cp1252 por defecto y no imprime emojis.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

    s = get_settings()
    url = a.url or f"http://localhost:{s.port}"
    cuerpo = json.dumps(payload(a.de, a.texto, a.boton, a.lista, a.nombre)).encode()
    firma = "sha256=" + hmac.new(s.whatsapp_app_secret.encode(), cuerpo, hashlib.sha256).hexdigest()

    antes = len(httpx.get(f"{url}/dev/mensajes", params={"para": a.de}).json().get("data", []))
    r = httpx.post(f"{url}/webhook", content=cuerpo,
                   headers={"Content-Type": "application/json", "X-Hub-Signature-256": firma})
    print(f"Webhook → {r.status_code} {r.text}")
    time.sleep(a.espera)
    nuevos = httpx.get(f"{url}/dev/mensajes", params={"para": a.de}).json().get("data", [])[antes:]
    if not nuevos:
        print("(Brisa no respondió todavía; revisa los logs del bot)")
    for m in nuevos:
        if m["type"] == "text":
            print(f"\nBrisa: {m['text']['body']}")
        elif m["type"] == "interactive":
            i = m["interactive"]
            print(f"\nBrisa: {i['body']['text']}")
            if i["type"] == "button":
                for b in i["action"]["buttons"]:
                    print(f"   [--boton {b['reply']['id']}]  {b['reply']['title']}")
            else:
                for row in i["action"]["sections"][0]["rows"]:
                    print(f"   [--lista {row['id']}]  {row['title']}")
        else:
            print(f"\nBrisa: {m}")


if __name__ == "__main__":
    main()
