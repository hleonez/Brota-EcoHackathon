# Bot de WhatsApp de Brota (Brisa)

Python + FastAPI. Recibe el webhook de la WhatsApp Cloud API (Meta), conversa con el vecino y
llama a la API de Brota. Guía de Meta: [docs/guia-bot-meta.md](../docs/guia-bot-meta.md).
Contrato con la API: [docs/integracion-bot.md](../docs/integracion-bot.md).

```text
app/
├─ main.py          Webhook (GET verificación, POST mensajes con firma), /health, /dev/mensajes
├─ whatsapp.py      Cliente de la Graph API: texto, botones, listas, plantillas, firma, lectura del webhook
├─ brota.py         Cliente de la API de Brota (X-Canal-Celular + Idempotency-Key = wamid)
├─ conversacion.py  Máquina de estados de Brisa: registro → consentimiento → menú
├─ pedido.py        Pedido guiado: materiales, chequeos de cada ficha, resumen y envío
├─ catalogo.py      Reconoce materiales en texto libre con los sinónimos de las fichas
├─ coordinacion.py  Modo coordinación: bandeja, asignar recolector y franja, cerrar
├─ meta.py          Utilidades de Meta: estado y suscripción de la cuenta de WhatsApp
├─ laboratorio.py   Laboratorio local (/lab): celulares simulados + tablero de órdenes y rutas
├─ textos.py        Todo lo que dice Brisa (edítalo aquí)
├─ avisos.py        Bucle: reservar avisos en la API → enviar por WhatsApp → confirmar
├─ simular.py       Simulador de mensajes entrantes (sin Meta)
└─ config.py        Variables de entorno (bot/.env)
```

**Coordinación:** la coordinadora trabaja en el panel ([web/coordinacion](../web/coordinacion/README.md)).
Si su número está en su cuenta (campo `celular` en la API), Brisa le manda una alerta por cada
solicitud nueva con el enlace al panel (`PANEL_COORDINACION_URL`). Con `COORDINACION_POR_WHATSAPP=true`
también puede asignar y cerrar desde el chat (BANDEJA, ASIGNADAS), como respaldo si no hay tablet.
Detalle en [docs/integracion-bot.md](../docs/integracion-bot.md) §4.

**Si el webhook está verificado pero no llega ningún mensaje:** conecta la app a la cuenta de WhatsApp:
`uv run python -m app.meta suscribir --waba <WhatsApp Business Account ID>`.

Lo que ya entiende un vecino: «hola» abre el menú (♻ Pedir recolección, ❓ Tengo una duda, 📦 Mis
solicitudes, ⭐ Mis puntos, 🏆 Liga). **Pedir** es guiado (`app/pedido.py`):
1. Elige materiales de la lista o los escribe («cajas y botellas», con `app/catalogo.py`).
2. Brisa le enseña cómo prepararlos y hace los chequeos de cada ficha.
3. Muestra un resumen con Enviar / Corregir / Cancelar. Nada se crea antes de «Enviar».

Si escribe un material sin estar pidiendo («¿el icopor se recicla?»), Brisa le muestra la ficha.
También entiende CANCELAR, PUNTOS, ESTADO, LIGA y BORRAR MIS DATOS. Audios y fotos responden «pronto»
(llegarán con Gemini en la fase 3). Diseño: [docs/brisa-ia.md](../docs/brisa-ia.md).

## Laboratorio: ver el flujo completo en el navegador

Con `LAB_ACTIVO=true` en `bot/.env`, abre `http://localhost:8090/lab`:

- Dos teléfonos tipo WhatsApp: vecinos de prueba (Laura, Carlos, Sofía) y las dos coordinaciones.
- Tablero con las órdenes por estado y las **rutas de los recolectores**.
- La primera vez, «Preparar demo» con el usuario `admin` y su PIN: les da a las cuentas de
  coordinación los celulares simulados (`573000000101`, `573000000102`).

Todo pasa por el bot y la API de verdad; lo que Brisa le envía a un celular simulado se queda en el
laboratorio y nunca sale a Meta. Tu celular real puede ser el vecino por WhatsApp mientras la
coordinación responde desde el navegador. Solo responde desde tu máquina (por el túnel da 404).

## 1 · Probar sin Meta (modo dry-run)

Requisitos: la API de Brota corriendo (ver `api/README.md`) y [uv](https://docs.astral.sh/uv/).

```powershell
cd bot
Copy-Item .env.example .env
```

En `bot/.env`:
- `WHATSAPP_DRY_RUN=true`
- `WHATSAPP_APP_SECRET` y `WHATSAPP_VERIFY_TOKEN`: cualquier texto aleatorio (para el simulador)
- `BROTA_API_URL`: URL de la API (p. ej. `http://localhost:8000`)
- `BOT_SERVICE_TOKEN`: el mismo valor que en `api/.env`

```powershell
uv sync
uv run uvicorn app.main:app --reload --port 8090
```

En otra terminal, conversa como si fueras un vecino:

```powershell
uv run python -m app.simular "hola"
```

El simulador muestra la respuesta de Brisa y los botones o filas con el comando para elegirlos
(`--boton RECICLABLES`, `--lista <id de torre>`). Recorrido completo:

```powershell
uv run python -m app.simular "Laura"
uv run python -m app.simular --lista <id de la Torre 3>
uv run python -m app.simular "402"
uv run python -m app.simular --boton ACEPTO
uv run python -m app.simular --boton LOS_DOS
```

Cuando la coordinación asigne la orden en la API, el aviso aparece solo en `GET http://localhost:8090/dev/mensajes`.

## 2 · Conectar con Meta (número de prueba)

1. En `bot/.env`, completa con los datos de **WhatsApp → Configuración de la API** y
   **Configuración de la app → Básica**:
   `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`, y pon `WHATSAPP_DRY_RUN=false`.
   Define `WHATSAPP_VERIFY_TOKEN` con un texto aleatorio que también escribirás en Meta.
2. Arranca el bot (`uv run uvicorn app.main:app --reload --port 8090`).
3. Exponlo con HTTPS en otra terminal:

```powershell
cloudflared tunnel --url http://localhost:8090
```

4. En Meta: **WhatsApp → Configuración → Webhook → Editar**. URL de devolución:
   `https://<la-url-de-cloudflared>/webhook`; token de verificación: tu `WHATSAPP_VERIFY_TOKEN`.
   Verificar y guardar. Luego en **Campos del webhook**, suscríbete a **messages**.
5. Escríbele «hola» al número de prueba desde tu celular. Brisa debe responder.

La URL de `cloudflared` cambia cada vez que lo reinicias: actualízala en Meta. El token temporal
vence en ~24 h (error 190 en los logs): genera uno nuevo o usa el permanente (guía, fase 5).

## 3 · Docker

Desde la raíz del repositorio, con `api/.env` y `bot/.env` listos:

```powershell
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml -f infra/compose.api.yaml -f infra/compose.bot.yaml up -d --build --wait
```

El bot llama a la API por la red interna (`http://api:8000`). Puertos locales: `API_LOCAL_PORT`
(8000) y `BOT_LOCAL_PORT` (8090).

## Pruebas

```powershell
uv run pytest
```

Simulan Meta y la API de Brota: firma del webhook, verificación, registro completo, consentimiento
rechazado, saludos tomados como nombre, apartamento escrito de varias formas, «Los dos»,
reenvíos de Meta sin duplicar, solicitud abierta, puntos y avisos fuera de la ventana de 24 h
(con y sin plantilla).

## Notas

- El estado del registro vive en memoria: si el bot se reinicia a mitad de un registro, el vecino
  empieza de nuevo. Para varias réplicas, cambiar `Memoria` por Redis.
- Plantillas para avisos fuera de 24 h: `brota_asignacion`, `brota_recoleccion`, `brota_rechazo`
  (ver la guía). Actívalas con `WHATSAPP_USAR_PLANTILLAS=true` cuando Meta las apruebe.
- Tras cambiar dependencias: `uv export --no-dev --no-hashes --format requirements-txt -o requirements.txt`.
