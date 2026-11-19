# Bitácora de cambios · Brota

Registro paso a paso de lo que se decide y se construye. Cada entrada dice **qué cambió,
por qué, cómo se verificó y qué quedó pendiente**. La entrada más reciente va al final.
Se actualiza en cada paso de trabajo.

## Estado actual

| Pieza | Estado | Dónde |
| --- | --- | --- |
| PostgreSQL 18 (Docker) | Funcionando | `infra/` |
| API central (FastAPI) | Núcleo funcionando, 20 pruebas en verde | `api/`, rama `feat/api-nucleo` |
| Integración con el bot | Probada de punta a punta (dry-run contra la API real) | [integracion-bot.md](integracion-bot.md) |
| Bot de WhatsApp (Meta) | Esqueleto funcionando, 14 pruebas; falta conectarlo al webhook de Meta | `bot/`, rama `feat/bot-whatsapp` |
| App de Meta | Creada (BrotaBrisa), número de prueba enviando | [guia-bot-meta.md](guia-bot-meta.md) |
| Paneles / tablet | Pospuesto | `web/` |
| IA con Gemini (tiquete, audios) | Decidido, por construir en la API | — |
| Canjes, certificado, exportaciones | Pendiente | — |

Ramas: `feat/api-nucleo` (subida a GitHub) y `feat/bot-whatsapp` (sale de la anterior; aún
local). **`main` no se ha modificado**; se fusiona después de verificar.

---

## 1 · 18-nov-2026 · Análisis inicial

**Fuentes revisadas:** plan maestro (NeuralSprint), contrato modular de API 0.2 (PDF),
diseño de base de datos (PDF), 8 imágenes del producto, el repositorio y la carpeta de Drive
(tenía solo las subcarpetas Backend, Frontend, Videos y Documentación, vacías).

**Hallazgos:**
- El repositorio solo tenía infraestructura de PostgreSQL; ningún código de aplicación.
- El diseño de datos es sólido (solicitud ≠ orden, recolector sin cuenta, pesaje por lote sin
  repartir kilos, IA que propone y humano que confirma, libro de puntos inmutable).
- El alcance documentado (12 módulos, ~45 tablas) no cabe en dos jornadas: se recorta al
  recorrido pedir → asignar → recoger/rechazar → pesar → puntos → resumen.
- El repo tenía el contrato 0.1; el PDF 0.2 era más nuevo.

**Brechas encontradas en el diseño (resueltas en el paso 2):**
- El contrato asumía que el webhook de WhatsApp vivía en la API; como el bot se hace aparte,
  faltaba cómo se autentica el bot, cómo identifica al residente y cómo recibe los avisos.
- Tablas mencionadas sin definir: `punto_recepcion`, dispositivo/referencias offline.
- Sin credenciales para la tablet de coordinación.
- Datos de las imágenes sin respaldo en el modelo (CO₂ evitado, compostaje, inventario,
  rutas): se dejan como visión, no se construyen ahora.

---

## 2 · 18-nov-2026 · Núcleo del backend (commit `33a2a9a`)

**Decisiones:**
- Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic + uv (stack del plan maestro). Revisable si el
  reto impone otro el 20-nov.
- El bot es un servicio aparte: se autentica con `BOT_SERVICE_TOKEN` y envía el número del
  residente en `X-Canal-Celular`. El estado de la conversación vive en el bot.
- Avisos al residente: bandeja de salida en la misma transacción del hecho; el bot los
  reserva (modo *pull*, por defecto) o la API se los envía por webhook firmado (modo *push*).
- Coordinación entra con usuario + PIN (hash scrypt) y recibe un JWT; permisos por gremio.

**Base de datos — migración `0001` (35 tablas):**
- Del diseño: territorio, participante y consentimiento, gremios, catálogos, solicitud,
  orden, asignación, resultado, pesaje y líneas, entrega directa, reglas y movimientos de
  puntos, contenidos educativos, idempotencia, eventos de dominio y de salida.
- **Agregadas:** `punto_recepcion`, `referencia_local` (sincronización offline),
  `solicitud_eliminacion` (derecho a borrar datos); `usuario` y `pin_hash` en
  `cuenta_operadora`; secuencias para los códigos `BR-00001` (Pasaporte) y `PS-00001` (pesaje).
- **Omitidas por ahora:** canjes, archivos/IA, versión de regla de Liga, certificados emitidos.

**API (48 endpoints):** registro por canal, catálogos y búsqueda de unidad, solicitud mixta
con Pasaporte, bandeja y asignación, resultado con puntos y educación, pesajes
(borrador → confirmado → corrección, báscula y baldes), entregas directas, saldo de puntos,
Liga de Torres, resumen y serie para paneles, configuración versionada, `/sync` offline y
rutas del canal para avisos. Detalle en [contrato-api.md](contrato-api.md).

**Otros archivos:** `api/Dockerfile`, `infra/compose.api.yaml` (capa opcional, no altera la
validación de infraestructura), semilla `app/seed.py`, documentación de la API y del bot.

**Datos semilla (valores de ejemplo, reemplazar con datos reales):** conjunto Brisas de San
Pablo, 5 torres × 110 viviendas (20 apartamentos de muestra por torre), 2 negocios, materiales
con precios inventados, 8 kg por balde, +10 puntos por entrega válida y +15 por entrega directa,
recolectores «(demo)», cuentas `coord-reciclaje`, `coord-huerta`, `fundacion`, `admin`.

**Verificación:**
- `uv run pytest`: 20 pruebas de punta a punta contra la base separada `brota_test`
  (registro, solicitud mixta, idempotencia, doble toque concurrente, solicitud abierta, permisos
  por gremio, reasignación, avisos pull y webhook firmado, puntos sin duplicar, rechazo con
  educación, lote, baldes, corrección, Liga, reportes, sync sin duplicar kilos).
- Migración probada de subida y bajada; `alembic check` sin diferencias con el modelo.
- Contenedor Docker construido: aplica migraciones y responde `/health/ready`.
- La validación de `infra/check-config.py` sigue pasando.

**Pendiente de este paso:**
- Rol de PostgreSQL restringido para la API (en desarrollo se usa el administrador).
- Reemplazar los valores de ejemplo de la semilla.

---

## 3 · 18-nov-2026 · Rama subida a GitHub

- Se creó la rama `feat/api-nucleo` y se subió a `origin` (`hleonez/Brota-EcoHackathon`).
- `main` queda intacto hasta revisar. Para el PR:
  https://github.com/hleonez/Brota-EcoHackathon/pull/new/feat/api-nucleo

---

## 4 · 18-nov-2026 · Plan del bot con la API de Meta

El equipo construye el bot con la WhatsApp Cloud API de Meta y un número propio.

**Recomendaciones acordadas para revisar:**
1. Desarrollar con el **número de prueba** de Meta (hasta 5 destinatarios autorizados).
2. Registrar el número real con antelación. Ese número **deja de funcionar en la app de
   WhatsApp** del teléfono (salvo el modo de coexistencia para WhatsApp Business, por confirmar):
   se recomienda una SIM dedicada a Brisa.
3. Generar un **token permanente** con un usuario del sistema (el token del panel vence en ~24 h).
4. Webhook público con HTTPS (`cloudflared` o `ngrok` en local) y verificación de
   `X-Hub-Signature-256` con el App Secret.
5. Crear pronto 3 **plantillas de utilidad** (asignación, recolección confirmada, rechazo) para
   avisos fuera de la ventana de 24 h.

**Conexión con la API:** `from` → `X-Canal-Celular`; `wamid` → `Idempotency-Key`; botones →
`tipo_servicio_ids` del catálogo; torres en mensaje de lista; avisos por
`/v1/canal/avisos/reservas`.

**Decisión pendiente:** lenguaje del bot y si se arma un esqueleto inicial.

---

## 5 · 18-nov-2026 · Revisión de estructura, guía del bot y elección de Gemini

**Revisión de la estructura (¿es escalable y profesional?):** sí para el piloto y para seguir
creciendo. Es un monolito modular (lo que pide el plan), con migraciones versionadas, contrato
documentado, pruebas contra PostgreSQL real, idempotencia y permisos por gremio. Mejoras
identificadas, por prioridad:

| Prioridad | Mejora | Por qué |
| --- | --- | --- |
| Alta | CI de la API en GitHub Actions (ruff + pytest con PostgreSQL) | Hoy las pruebas solo corren en local |
| Alta | El bot en `bot/` dentro del mismo repositorio, con su Dockerfile y servicio Compose | Un solo contrato y un solo despliegue |
| Media | Rol de PostgreSQL restringido para la API | Hoy usa el administrador en desarrollo |
| Media | Configuración de ruff en `pyproject.toml` | Estilo uniforme en el equipo |
| Media | Dividir `pesajes.py` (800 líneas) en esquemas/servicio/rutas al volver a tocarlo | Legibilidad |
| Baja | Despachador de avisos como proceso aparte si hay varias réplicas | Hoy es un hilo dentro de la API |
| Baja | Carga anticipada en listados (consultas N+1) | Solo importa con miles de registros |

**Guía del bot:** nueva [guia-bot-meta.md](guia-bot-meta.md), con 6 fases: crear la app de Meta,
webhook, conexión con la API, avisos, token permanente y número propio, y publicación.

**IA con Gemini (Google AI Studio):** se adopta Gemini como proveedor. Encaja con el plan:
entiende audio e imágenes directamente (no hace falta un servicio de transcripción aparte) y
devuelve JSON con esquema. Decisiones:
- La llave de Gemini vive **solo en la API** (módulo M06), no en el bot ni en la tablet. El bot y
  la tablet llaman a la API; la IA propone y una persona confirma.
- Nivel gratuito solo con datos ficticios: según los términos de Google, lo enviado en el nivel
  gratuito puede usarse para mejorar sus productos. Con vecinos reales, nivel de pago.
- Si Gemini falla, el flujo manual sigue funcionando.

---

## 6 · 18-nov-2026 · App de Meta y esqueleto del bot (rama `feat/bot-whatsapp`)

**Meta (Fase 1 de la guía, hecha por el equipo):**
- App **BrotaBrisa** creada con el caso de uso de WhatsApp, en el portafolio existente «Fymbot»:
  el límite de portafolios de la cuenta impidió crear uno nuevo. Sirve para desarrollo. Antes de
  registrar el número real conviene un portafolio «Brota» (creado por otro integrante).
- Número de prueba +1 555 656-3261; el `hello_world` llegó al celular autorizado.
- Un token temporal quedó visible en una captura: se recomendó regenerarlo y tapar los secretos.

**Decisión:** bot en **Python + FastAPI** (mismo stack que la API), dentro del repo en `bot/`.

**Qué se construyó (`bot/`):**
- Webhook de Meta: verificación (`GET /webhook`), recepción con validación de la firma
  `X-Hub-Signature-256`, respuesta inmediata y procesamiento en segundo plano, en orden por vecino,
  e ignorando reenvíos de Meta por `wamid`.
- Conversación de Brisa: registro (nombre → torre en lista → apartamento → consentimiento con
  «Ver más»), menú de 3 botones, PUNTOS, ESTADO, LIGA y BORRAR MIS DATOS.
- Cliente de la API con `X-Canal-Celular` y `Idempotency-Key` = `wamid`.
- Bucle de avisos: reserva → envío → confirmación; si pasaron 24 h, plantilla aprobada
  (`brota_asignacion`, `brota_recoleccion`, `brota_rechazo`) cuando se active.
- Modo **dry-run** (no llama a Meta) y **simulador** de mensajes firmados para probar sin celular.
- `bot/Dockerfile` e `infra/compose.bot.yaml` (el bot llama a la API por la red interna).

**Ajustes en la API:** se quitó el doble punto en el aviso de asignación («p. m.. Ten…»).

**Verificación:**
- 14 pruebas del bot con Meta y la API simuladas; 20 de la API siguen en verde.
- Prueba real, dry-run contra la API en Docker: registro de un vecino, «Los dos» → BR-00001,
  segunda solicitud bloqueada por la regla de solicitud abierta, asignación y recogida hechas por
  la coordinación → el bot entregó solos los dos avisos («Jairo pasa mañana…», «+10 puntos») y la
  API los marcó como enviados.
- Encontrado y corregido en las pruebas: «Apto 402» no se reconocía; «hola» se tomaba como nombre.
- Contenedores de API y bot construidos y sanos; la validación de infraestructura sigue pasando.

**Pendiente:** conectar el webhook real de Meta (README del bot, sección 2), plantillas,
token permanente y número propio.

---

## Próximos pasos

- [ ] Revisar las ramas `feat/api-nucleo` y `feat/bot-whatsapp` y fusionarlas a `main`.
- [x] Bot: Fase 1 de la guía (app de Meta y número de prueba).
- [x] Bot: esqueleto con registro, menú, solicitudes y avisos contra la API.
- [ ] Bot: Fase 2 (webhook real con `cloudflared`) y prueba desde el celular.
- [ ] Plantillas de WhatsApp enviadas a aprobación.
- [ ] API: CI en GitHub Actions y configuración de ruff.
- [ ] API: módulo M06 con Gemini (interpretar audio/texto y leer el tiquete de pesaje).
- [ ] Datos reales: viviendas por torre, lista de precios de Asorescatar, peso del balde.
- [ ] 20-nov: ajustar al stack y criterios oficiales del reto.
- [ ] Después: Certificado Verde, exportación Excel, canjes, paneles.

## Decisiones abiertas para el equipo

| Pregunta | Propuesta actual |
| --- | --- |
| ¿El saldo de puntos es de la persona o del hogar? | Personal |
| ¿Se acumulan puntos por entrega y por kg? | No; solo por entrega válida |
| ¿Cuántas solicitudes abiertas por servicio? | Una (configurable) |
| ¿Cuánto pesa un balde de la huerta? | 8 kg de ejemplo |
| ¿Fórmula de la Liga? | % de hogares que participan; desempate por kg |
