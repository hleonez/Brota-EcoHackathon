# Guía paso a paso · Bot de WhatsApp (Brisa) con la Cloud API de Meta

Objetivo: que un vecino escriba «hola» a Brisa, se registre, pida una recolección y reciba
los avisos, todo contra la API de Brota. Complementa [integracion-bot.md](integracion-bot.md),
que detalla cada endpoint de la API.

> Meta cambia sus pantallas y versiones con frecuencia. Si un nombre de menú no coincide,
> busca el equivalente en el panel; usa la versión de Graph API que muestre tu app.

```text
Vecino ──WhatsApp──► Meta ──webhook HTTPS──► bot/ ──HTTP + token──► api/ ──► PostgreSQL
                       ▲                       │
                       └──── Graph API ◄───────┘  (enviar mensajes, descargar audios)
```

## Fase 0 · Lo que necesitas

- Cuenta de Facebook con acceso a [Meta for Developers](https://developers.facebook.com/).
- Un **portafolio de negocio** (Business Manager) a nombre del proyecto.
- Tu celular para recibir los mensajes de prueba.
- La API de Brota corriendo en local (`api/README.md`) con `BOT_SERVICE_TOKEN` en `api/.env`.
- `cloudflared` o `ngrok` para exponer el bot con HTTPS mientras desarrollas.

## Fase 1 · Crear la app y probar con el número de prueba (≈30 min)

1. En Meta for Developers: **Mis apps → Crear app** → caso de uso de **WhatsApp**
   (conectar con clientes) → vincúlala a tu portafolio de negocio.
2. En **WhatsApp → Configuración de la API** verás:
   - un **número de prueba** gratuito,
   - el **Phone number ID** y el **WhatsApp Business Account ID** (anótalos),
   - un **token de acceso temporal** (vence en ~24 h; sirve solo para hoy).
3. En «Para», agrega tu celular como destinatario (te llega un código). El número de prueba
   solo puede escribir a **máximo 5 números** autorizados.
4. Prueba el envío con la plantilla `hello_world`:

```powershell
$token = "<TOKEN_TEMPORAL>"; $phoneId = "<PHONE_NUMBER_ID>"
$body = @{ messaging_product = "whatsapp"; to = "57300XXXXXXX"; type = "template";
           template = @{ name = "hello_world"; language = @{ code = "en_US" } } } | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri "https://graph.facebook.com/v21.0/$phoneId/messages" `
  -Headers @{ Authorization = "Bearer $token" } -ContentType "application/json" -Body $body
```

Si te llega el mensaje, la cuenta funciona. (Cambia `v21.0` por la versión que muestre el panel.)

## Fase 2 · Recibir mensajes: webhook (≈1 h)

1. Levanta el bot en local (`bot/`, puerto 8090; ver `bot/README.md`). Ya trae dos rutas:
   - `GET /webhook` → verificación: si `hub.mode == "subscribe"` y `hub.verify_token` es igual a tu
     `WHATSAPP_VERIFY_TOKEN`, responde **el texto** de `hub.challenge` con 200; si no, 403.
   - `POST /webhook` → mensajes: valida la firma, responde **200 de inmediato** y procesa después.
2. Exponlo con HTTPS: `cloudflared tunnel --url http://localhost:8090` (te da una URL `https://...trycloudflare.com`).
3. En **WhatsApp → Configuración → Webhook**: URL de devolución = `https://<tu-url>/webhook`,
   token de verificación = tu `WHATSAPP_VERIFY_TOKEN` → Verificar y guardar.
4. Suscríbete al campo **`messages`**.
5. **Valida la firma** de cada POST: cabecera `X-Hub-Signature-256` = `sha256=` + HMAC-SHA256 del
   **cuerpo crudo** con el **App Secret** (Configuración de la app → Básica). Si no coincide, descarta.

Lo que llega en un mensaje (lo importante):

```json
{"entry": [{"changes": [{"value": {
  "contacts": [{"profile": {"name": "Carmen"}, "wa_id": "573001112233"}],
  "messages": [{"from": "573001112233", "id": "wamid.HBgM...", "type": "text", "text": {"body": "hola"}}]
}}]}]}
```

Otros tipos: `interactive` (respuesta a botón o lista: `interactive.button_reply.id` o
`interactive.list_reply.id`), `audio` (`audio.id`), `image`. Los `statuses` (entregado, leído)
llegan por el mismo webhook: ignóralos o úsalos para registro.

## Fase 3 · Conectar con la API de Brota (≈2–3 h)

Por cada mensaje entrante:

| Del webhook | A la API de Brota |
| --- | --- |
| `messages[0].from` | Cabecera `X-Canal-Celular` |
| `messages[0].id` (`wamid`) | Cabecera `Idempotency-Key` en los POST |
| — | `Authorization: Bearer <BOT_SERVICE_TOKEN>` |

Máquina de estados mínima (guárdala en memoria o Redis, por celular):

```text
SIN_REGISTRO → PIDE_NOMBRE → PIDE_TORRE (lista) → PIDE_APTO → CONSENTIMIENTO (botones) → MENÚ
MENÚ: ♻ Reciclable · 🍌 Orgánico · 🔄 Los dos   (+ texto «PUNTOS», «LIGA», «ESTADO»)
```

1. Al recibir cualquier mensaje: `GET /v1/me`. Si `registrado` es `false` → registro.
2. Torres: `GET /v1/conjuntos` y `GET /v1/conjuntos/{id}/torres` → mensaje de **lista**
   (los botones admiten máximo 3; las listas, hasta 10 filas).
3. Apartamento: `GET /v1/unidades?torre_id=...&referencia=402`. Si viene vacío, vuelve a preguntar.
4. Consentimiento con botones → `POST /v1/registros`.
5. Menú: botones con `id` = código del servicio. Al iniciar, cachea `GET /v1/catalogos` y traduce
   `RECICLABLES` / `ORGANICOS` a sus IDs → `POST /v1/solicitudes`.
6. Maneja `409 OPEN_REQUEST_EXISTS` («ya tienes una en camino, BR-…») y `403 CONSENT_REQUIRED`.

Enviar botones (Graph API, `POST /{phone_number_id}/messages`):

```json
{"messaging_product": "whatsapp", "to": "573001112233", "type": "interactive",
 "interactive": {"type": "button", "body": {"text": "¡Hola, Carmen! ¿Qué quieres que recojamos?"},
   "action": {"buttons": [
     {"type": "reply", "reply": {"id": "RECICLABLES", "title": "♻ Reciclable"}},
     {"type": "reply", "reply": {"id": "ORGANICOS", "title": "🍌 Orgánico"}},
     {"type": "reply", "reply": {"id": "LOS_DOS", "title": "🔄 Los dos"}}]}}}
```

Lista de torres:

```json
{"messaging_product": "whatsapp", "to": "573001112233", "type": "interactive",
 "interactive": {"type": "list", "body": {"text": "¿En qué torre vives?"},
   "action": {"button": "Elegir torre", "sections": [{"title": "Brisas de San Pablo",
     "rows": [{"id": "<torre_id>", "title": "Torre 1"}, {"id": "<torre_id>", "title": "Torre 2"}]}]}}}
```

Límites útiles: título de botón ≤ 20 caracteres, título de fila de lista ≤ 24.

## Fase 4 · Avisos de la API al vecino (≈1 h)

Un bucle cada 2–5 s en el bot:

1. `POST /v1/canal/avisos/reservas` con `{"limite": 10}`.
2. Para cada aviso, envía `datos.texto_sugerido` a `destino.celular` (en el rechazo, agrega
   `datos.contenido`).
3. Confirma: `POST /v1/canal/avisos/{id}/resultado` con `{"estado":"enviado","id_externo":"<wamid>"}`
   o `{"estado":"fallido","error":"<código de Meta>"}`.

**Ventana de 24 horas:** el texto libre y los botones solo se pueden enviar dentro de las 24 h siguientes
al último mensaje del vecino. Fuera de ella, Meta exige una **plantilla aprobada** (error 131047). Crea en
**WhatsApp Manager → Plantillas** tres plantillas de categoría *Utilidad*, en español:

| Plantilla | Texto sugerido | Variables (de `datos`) |
| --- | --- | --- |
| `brota_asignacion` | «🚲 {{1}} pasa {{2}} por tu recolección {{3}}.» | `recolector_nombre`, `franja_texto`, `codigo_pasaporte` |
| `brota_recoleccion` | «💚 ¡Gracias! Tu material llegó bien separado. +{{1}} puntos, tienes {{2}}.» | `puntos_otorgados`, `saldo` |
| `brota_rechazo` | «😕 Esta vez no se pudo llevar tu material: {{1}}. Escríbenos para ver cómo hacerlo.» | `motivo` |

Envíalas a aprobación pronto: puede tardar desde minutos hasta horas.

## Fase 5 · Token permanente y número propio (antes de la demo)

**Token permanente:** Configuración del negocio → Usuarios del sistema → Agregar (admin) →
Asignar activos (la app y la cuenta de WhatsApp) → Generar token con los permisos
`whatsapp_business_messaging` y `whatsapp_business_management`. Guárdalo como secreto del bot.

**Tu número:**
- Un número registrado en la Cloud API **deja de funcionar en la app de WhatsApp** de ese teléfono.
  Si hoy lo usas en WhatsApp, elimina esa cuenta en la app antes de registrarlo, o usa una **SIM
  nueva dedicada a Brisa** (recomendado). Meta ofrece «coexistencia» para números de la app
  WhatsApp Business: confirma en su documentación si aplica a tu caso.
- WhatsApp → Configuración de la API → **Agregar número** → nombre visible (p. ej. «Brisa · Brota»)
  → verificación por SMS o llamada → define el PIN de verificación en dos pasos.
- El nombre visible pasa por revisión de Meta.

**Modo publicado (Live):** para recibir mensajes de cualquier persona en el número real, la app
debe estar publicada, lo que pide una **URL de política de privacidad**. Brota la necesita de todos
modos (Ley 1581): publica una página sencilla con la política de datos `2026-11`.

## Fase 6 · Publicar (servidor de la demo)

Recomendado, siguiendo el plan: un VPS con Docker Compose y Caddy (HTTPS automático).

```text
Internet ──HTTPS──► Caddy ──► bot:8090   (solo /webhook)
                         └──► api:8000   (/api, para los paneles cuando existan)
bot ──red interna──► http://api:8000/v1
```

- El bot y la API van en el mismo Compose: el bot llama a `http://api:8000` sin salir a internet.
- Solo se publica el webhook del bot (y luego los paneles). PostgreSQL nunca se publica.
- Variables del bot como secretos: `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`,
  `WHATSAPP_VERIFY_TOKEN`, `BROTA_API_URL`, `BOT_SERVICE_TOKEN`.
- Cambia la URL del webhook en Meta a la del servidor y vuelve a verificar.

## Lista de comprobación de la demo

- [ ] «hola» desde un número nuevo → registro completo en menos de 1 minuto.
- [ ] «Los dos» → una solicitud BR-… con dos órdenes (`GET /v1/ordenes` de cada coordinación).
- [ ] Asignar desde la API o el panel → llega «🚲 … pasa …» al celular.
- [ ] Recogida → llega «+10 puntos»; «PUNTOS» responde el saldo.
- [ ] Rechazo → llega el motivo y el consejo educativo.
- [ ] Doble toque rápido en un botón → una sola solicitud.
- [ ] Apagar el bot 1 minuto con avisos pendientes → al volver, se envían sin perderse.
- [ ] Número del jurado: autorizado (número de prueba) o número propio ya en modo publicado.
