# Integrar el bot de WhatsApp (Brisa) con la API

El bot es un servicio aparte: recibe el webhook de WhatsApp (Meta Cloud API o Twilio),
verifica la firma del proveedor, maneja la conversación y llama a la API de Brota para todo lo
que es dominio: registro, solicitudes, puntos, Liga y avisos. La API **no** recibe el webhook
de Meta ni guarda el estado de la conversación.

```text
WhatsApp ──webhook──► Bot (tuyo) ──HTTP + token──► API Brota ──► PostgreSQL
    ▲                    │   ▲                          │
    └──── mensajes ──────┘   └── avisos (pull o push) ──┘
```

Referencia interactiva de todos los esquemas: `http://localhost:8000/docs` (OpenAPI).

## 1. Autenticación

Todas las llamadas del bot llevan:

| Cabecera | Valor |
| --- | --- |
| `Authorization` | `Bearer <BOT_SERVICE_TOKEN>` (el mismo valor configurado en `api/.env`) |
| `X-Canal-Celular` | El número del residente **ya verificado por el proveedor**: el `wa_id` de Meta (`573001112233`) o `+573001112233`. Un móvil de 10 dígitos que empiece por 3 se asume colombiano. |
| `Idempotency-Key` | Obligatoria en `POST`/`PATCH` de dominio (1–128 caracteres). **Usa el `wamid` del mensaje entrante**: si Meta reenvía el webhook o el usuario toca dos veces, la API devuelve la misma respuesta sin duplicar. |

Sin `X-Canal-Celular` el bot actúa como servicio (solo para reservar avisos). El cuerpo nunca
concede identidad ni rol: el celular solo llega por esa cabecera, que solo acepta el token del bot.

> Guarda `BOT_SERVICE_TOKEN` como secreto del bot. Quien lo tenga puede actuar por cualquier
> celular, igual que el propio canal de WhatsApp.

## 2. Flujo de conversación → endpoints

Prefijo de todas las rutas: `/v1` (detrás del proxy: `/api/v1`).

### Al recibir cualquier mensaje

`GET /v1/me` → `registrado: false` (registro) o `true` (menú). Incluye `nombre`, `unidades[]`,
`consentimiento_vigente` y `politica_datos_version`.

### A · Registro único (SIN_REGISTRO → CONSENTIMIENTO)

1. Pide el nombre.
2. `GET /v1/conjuntos` → `GET /v1/conjuntos/{id}/torres` → muestra torres (lista interactiva; hay 5).
3. Pide el apartamento y busca: `GET /v1/unidades?torre_id=<id>&referencia=402`.
   Devuelve 0 o 1 unidad (`etiqueta`: «Torre 3 · Apto 402»). El canal no puede listar el directorio.
   Para negocios: `GET /v1/unidades?tipo=negocio&referencia=<nombre exacto>`.
4. Botones «Sí, acepto / Ver más / No». Si acepta:

```http
POST /v1/registros
Authorization: Bearer <BOT_SERVICE_TOKEN>
X-Canal-Celular: 573001112233
Idempotency-Key: wamid.HBgM...
Content-Type: application/json

{"nombre": "Carmen", "unidad_id": "<uuid>",
 "consentimiento": {"version_politica": "2026-11", "decision": "aceptado"}}
```

`201` → registrado. `409 CONTACT_ALREADY_REGISTERED` → ya existía. `422 CONSENT_REQUIRED` si
`decision` no es `aceptado` (si dice «No», simplemente no llames a la API).

### B · Menú y pedir en dos toques (MENÚ)

Al arrancar, cachea `GET /v1/catalogos` → `tipos_servicio` por `codigo`:
`RECICLABLES` (♻) y `ORGANICOS` (🍌). «Los dos» = enviar ambos IDs.

```http
POST /v1/solicitudes
{"tipo_servicio_ids": ["<id RECICLABLES>", "<id ORGANICOS>"], "observacion": "opcional"}
```

`unidad_id` es opcional si el residente tiene una sola unidad. Respuesta `201`:

```json
{"data": {"id": "...", "codigo_pasaporte": "BR-00018", "ubicacion_operativa": "Torre 3 · Apto 402",
  "canal_origen": "whatsapp",
  "avance": {"ordenes_totales": 2, "ordenes_finalizadas": 0, "estado_general": "pendiente", "alcance": "propio"},
  "ordenes": [{"id": "...", "gremio_nombre": "Asorescatar · Recicladores", "estado": "nueva", "version": 1}, ...]}}
```

Brisa responde: «Recibido, te aviso quién pasa 💚 (BR-00018)».

Errores que debe manejar el bot:

| HTTP / `error.code` | Qué decir |
| --- | --- |
| `409 OPEN_REQUEST_EXISTS` | Ya hay una abierta: `error.codigo_pasaporte`, `error.solicitud_id`. «Ya tienes una solicitud en camino (BR-…)». |
| `403 CONSENT_REQUIRED` | Volver a pedir el consentimiento → `POST /v1/me/consentimientos`. |
| `403 NOT_REGISTERED` | El número no está registrado → flujo A. |
| `422 VALIDATION_ERROR` | `error.fields` dice qué campo; normalmente un bug del bot. |
| `409 IDEMPOTENCY_CONFLICT` | Reusaste una clave con otro cuerpo: genera otra clave. |
| `5xx` / red | Reintenta **con la misma** `Idempotency-Key`. |

### C · Consultas del residente

| Intención | Llamada |
| --- | --- |
| «PUNTOS» | `GET /v1/me/puntos` → `saldo` (string, p. ej. `"25.00"`) |
| Historial de puntos | `GET /v1/me/movimientos-puntos` |
| «¿Ya vienen?» | `GET /v1/solicitudes?abiertas=true` → `avance`, `ordenes[].asignacion` (recolector y franja) |
| Pasaporte | `GET /v1/solicitudes/{id}/pasaporte` |
| Liga de Torres | `GET /v1/liga?conjunto_id=<id>&desde=2026-11-01T05:00:00Z&hasta=2026-12-01T05:00:00Z` (ranking sin datos personales) |
| «Borrar mis datos» | `POST /v1/me/solicitudes-eliminacion` → `202` con seguimiento |
| Retirar consentimiento | `POST /v1/me/consentimientos` con `decision: "retirado"` |

Fechas en query: ISO 8601 con zona. Usa `Z` (o codifica `+` como `%2B`).

### D · Audio, texto libre y foto

La API todavía no expone IA (`/v1/capacidades` → `archivos_ia: false`). Si el bot interpreta
un audio o texto con un modelo, **pide confirmación al residente** («¿Pido la recolección de
cartón y botellas? Sí / No») y solo entonces llama `POST /v1/solicitudes` con los IDs del catálogo.
Nunca crees una solicitud solo con la interpretación.

## 3. Avisos de la API al residente (sincronización)

Cuando la coordinación asigna, confirma una recogida, rechaza o confirma una entrega directa,
la API guarda un aviso en la misma transacción. El bot los envía por WhatsApp.

Tipos de aviso y `datos`:

| `tipo` | Cuándo | `datos` principales |
| --- | --- | --- |
| `asignacion` | Se asigna o reasigna un recolector | `codigo_pasaporte`, `gremio`, `recolector_nombre`, `inicio`, `fin`, `franja_texto`, `reasignacion` |
| `recoleccion_confirmada` | Orden recogida | `puntos_otorgados`, `saldo`, `evaluacion_puntos` |
| `rechazo_educativo` | Orden rechazada | `motivo`, `motivo_codigo`, `contenido` (`titulo`, `tipo`, `recurso`, `texto`) |
| `entrega_directa_confirmada` | Entrega en huerta/acopio con puntos | `pesaje_codigo`, `puntos_otorgados`, `saldo` |

Todos traen `texto_sugerido` en la voz de Brisa (puedes enviarlo tal cual o usar tu plantilla).
Fuera de la ventana de 24 h de WhatsApp necesitas **plantillas aprobadas** por Meta: mapea cada
`tipo` a una plantilla y usa `datos` como variables.

### Modo pull (por defecto, `AVISOS_MODO=pull`)

Bucle del bot cada 2–5 s:

```http
POST /v1/canal/avisos/reservas
Authorization: Bearer <BOT_SERVICE_TOKEN>
{"limite": 10}
```

```json
{"data": [{
  "id": "6f1c...", "tipo": "asignacion", "estado": "en_envio", "intentos": 1,
  "destino": {"participante_id": "...", "celular": "+573001112233", "nombre": "Carmen"},
  "solicitud_id": "...", "orden_id": "...",
  "datos": {"codigo_pasaporte": "BR-00018", "recolector_nombre": "Rosa (demo)",
            "franja_texto": "hoy entre 4:00 p. m. y 5:00 p. m.",
            "texto_sugerido": "🚲 Rosa (demo) pasa hoy entre 4:00 p. m. y 5:00 p. m. Ten la bolsa lista en la puerta."},
  "reservado_hasta": "2026-11-20T21:01:00Z"}]}
```

Después de enviar cada uno:

```http
POST /v1/canal/avisos/{id}/resultado
{"estado": "enviado", "id_externo": "wamid.HBgM..."}
```

o `{"estado": "fallido", "error": "131026 ...", "reintentar": true}`. Un fallo con reintento
vuelve a `pendiente` con espera creciente; tras `AVISOS_MAX_INTENTOS` queda `fallido`.
Si no confirmas antes de `reservado_hasta`, el aviso se vuelve a entregar: **deduplica por `id`**.
Diagnóstico: `GET /v1/canal/avisos?estado=fallido`.

### Modo webhook (`AVISOS_MODO=webhook`)

La API hace `POST` a `BOT_WEBHOOK_URL` con el mismo objeto de la reserva y estas cabeceras:

| Cabecera | Valor |
| --- | --- |
| `X-Brota-Evento-Id` | `id` del aviso (para deduplicar) |
| `X-Brota-Firma` | `sha256=` + HMAC-SHA256 hexadecimal del cuerpo crudo con `BOT_WEBHOOK_SECRET` |

Responde `2xx` cuando WhatsApp aceptó el mensaje (opcional: `{"id_externo": "wamid..."}`).
Cualquier otro código reintenta; `410` lo marca fallido sin reintento. Verificación en Node:

```js
const esperado = 'sha256=' + crypto.createHmac('sha256', SECRET).update(rawBody).digest('hex');
const ok = crypto.timingSafeEqual(Buffer.from(esperado), Buffer.from(req.get('X-Brota-Firma') || ''));
```

En Python: `hmac.compare_digest(esperado, firma)` con `hmac.new(secret, raw, hashlib.sha256)`.

## 4. Probar sin WhatsApp

Con la API en marcha y la semilla aplicada (ver `api/README.md`):

```powershell
$h = @{ Authorization = "Bearer $env:BOT_SERVICE_TOKEN"; "X-Canal-Celular" = "573001112233" }
Invoke-RestMethod http://localhost:8000/v1/me -Headers $h
```

La suite `api/tests/test_recorrido.py` recorre el flujo completo del bot (registro, solicitud
mixta, avisos pull, puntos, webhook firmado) y sirve de ejemplo ejecutable.
