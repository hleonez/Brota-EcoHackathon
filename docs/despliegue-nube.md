# Despliegue en Neon, Render y Cloudflare

La base queda en Neon, la API y Brisa en Render (Virginia) y el panel en Cloudflare Pages. El navegador solo habla con la API. El bot llama a la API por la URL pública que Render le inyecta.

Los secretos no van en Git. Salen de `api/.env` y `bot/.env` en el momento de cargarlos en Render, o de la consola de Neon al crear el proyecto.

## Qué se carga y qué no

Desde `api/.env`, el mismo valor en Render:

- `JWT_SECRET`
- `BOT_SERVICE_TOKEN` (también en el servicio del bot; no generes otro)
- `GEMINI_API_KEY`

Desde `bot/.env`:

- `WHATSAPP_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_APP_SECRET`
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_WABA_ID`

No subas la base local. `DB_HOST=127.0.0.1`, `DB_PASSWORD` vacío, `DB_PASSWORD_FILE`, `BROTA_API_URL=http://localhost:…` y el CORS de localhost se quedan en el equipo. `BOT_WEBHOOK_SECRET` tampoco: los avisos van en modo `pull`.

En Render el bot arranca con `WHATSAPP_DRY_RUN=false`, `AVISOS_ACTIVOS=true` y `LAB_ACTIVO=false`. No definas `TUNEL_METRICAS_URL`.

`SEED_PIN` no está en los `.env`. Elígelo al crear el Blueprint (4 a 12 dígitos) y guárdalo solo en Render. La semilla lo usa la primera vez; si lo omites, lo inventa y lo imprime una sola vez en el registro del servicio.

## 1. Neon

Hace falta una sesión de la CLI (`neon login`). Región `aws-us-east-1`, al lado de Render Virginia. Conexión directa, sin el host `-pooler`.

```powershell
neon projects create --name brota --database brota --pg-version 18 --region-id aws-us-east-1 --no-secrets
```

Si la CLI no reconoce la región, `neon projects create --help` lista los id. Guarda el id del proyecto y usa la rama inicial (`main` o `production`, la que muestre `neon branches list`).

```powershell
neon connection-string main --project-id $neonProjectId --database-name brota --role-name brota_owner --ssl verify-full
```

Ese comando imprime la contraseña. Parte la URL en `DB_HOST`, `DB_USER`, `DB_PASSWORD` y confirma `DB_NAME=brota`. El host no lleva `-pooler`. `DB_SSLMODE` queda en `verify-full` y `PGSSLROOTCERT=system` en [render.yaml](../render.yaml). La imagen slim no trae CAs: [api/Dockerfile](../api/Dockerfile) instala `ca-certificates` y la API pide `sslrootcert=system`. Esa imagen tiene que estar en la rama que Render construye. Mientras `develop` no la tenga, el servicio puede arrancar con `DB_SSLMODE=require` (cifrado, sin verificar el certificado). No copies la URL a un archivo del repositorio.

## 2. Render

El Blueprint es [render.yaml](../render.yaml). Los dos servicios son Docker, plan `0.5c-512mb` (el cómputo de pago más pequeño; no se duerme). Render ya no usa el id `starter`. El health de la API es `/health/live`, para que un Neon recién despertado no tumbe el deploy. `/health/ready` se comprueba a mano.

Ese plan exige una tarjeta. Si el workspace no tiene datos de pago, Render responde 402 y los servicios solo pueden crearse en `free`, que se duerme a los quince minutos. En ese caso Meta deja de alcanzar el webhook hasta el siguiente arranque. Cuando haya una tarjeta en el panel de facturación, cambia `brota-api` y `brota-bot` a `0.5c-512mb`.

En el Dashboard: **New → Blueprint**, elige este repositorio y la rama. En las variables `sync: false` pega los valores del apartado anterior. `BOT_SERVICE_TOKEN` tiene que coincidir en `brota-api` y `brota-bot`.

`BROTA_API_URL` no se pega: el Blueprint la toma de `RENDER_EXTERNAL_URL` de `brota-api`.

Al terminar:

```text
GET https://<brota-api>.onrender.com/health/live
GET https://<brota-api>.onrender.com/health/ready
GET https://<brota-bot>.onrender.com/health
```

`/health/ready` debe decir `ready`. El registro de `brota-api` muestra la semilla. Si apareció un PIN generado, cópialo en ese momento a la variable `SEED_PIN` del servicio para no perderlo.

El bot es una sola instancia. No subas `numInstances`.

## 3. Cloudflare Pages

Cuando la API ya tenga URL pública:

- Raíz: `web/coordinacion`
- Comando: `npm ci && npm run build`
- Salida: `dist`
- Variable de build: `VITE_API_URL` = `https://<brota-api>.onrender.com` (sin barra final)

Vite fija esa URL al compilar. Si cambia, hay que volver a construir.

Luego, en Render:

- `brota-api` → `CORS_ALLOWED_ORIGINS` = origen exacto del panel (`https://….pages.dev` o el dominio propio), sin barra final.
- `brota-bot` → `PANEL_COORDINACION_URL` = esa misma URL.

No dejes `CORS_ALLOWED_ORIGINS` en blanco: una cadena vacía tapa el valor por defecto del código. Si el panel todavía no existe, omite la variable.

## 4. Webhook de Meta

Cuando `https://<brota-bot>.onrender.com/health` responda, en Meta (WhatsApp → Configuración → Webhook):

- URL de devolución: `https://<brota-bot>.onrender.com/webhook`
- Token de verificación: el `WHATSAPP_VERIFY_TOKEN` que ya está en `bot/.env`
- Campo suscrito: `messages`

Se registra una vez. La URL de Render no cambia en cada arranque, así que no hace falta el túnel rápido ni el bucle de `bot/app/enlace.py`.

## Cuentas

Neon, Render y Cloudflare piden inicio de sesión en el navegador. Esta guía no crea esas cuentas.

## Direcciones de este despliegue

- Neon: proyecto `brota`, id `proud-smoke-57644286`, región `aws-us-east-1`, base `brota`, rol `brota_owner`.
- API: `https://brota-api-6bpj.onrender.com` (`/health/live`, `/health/ready`).
- Bot: `https://brota-bot.onrender.com`. Webhook: `https://brota-bot.onrender.com/webhook`.
- Panel: `https://brota-panel.pages.dev`. `CORS_ALLOWED_ORIGINS` y `PANEL_COORDINACION_URL` apuntan a ese origen.
- Rama que Render construye: `develop`.

Los dos servicios quedaron en el plan `free` porque el workspace no tiene tarjeta. `DB_SSLMODE` del servicio es `require` hasta que `develop` incluya la imagen con `ca-certificates`; entonces se vuelve a `verify-full` y `PGSSLROOTCERT=system`, que es lo que declara `render.yaml`.
