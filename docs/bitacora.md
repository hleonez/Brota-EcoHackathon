# Bitácora de cambios · Brota

Registro paso a paso de lo que se decide y se construye. Cada entrada dice **qué cambió,
por qué, cómo se verificó y qué quedó pendiente**. La entrada más reciente va al final.
Se actualiza en cada paso de trabajo.

## Estado actual

| Pieza | Estado | Dónde |
| --- | --- | --- |
| PostgreSQL 18 (Docker) | Funcionando | `infra/` |
| API central (FastAPI) | Núcleo, coordinación y fichas de residuos (migración 0003); 23 pruebas | `api/` |
| Integración con el bot | Probada con WhatsApp real (vecino) | [integracion-bot.md](integracion-bot.md) |
| Bot de WhatsApp (Meta) | Menú nuevo, dudas y pedido guiado con resumen; 32 pruebas; webhook real conectado | `bot/` |
| Laboratorio de pruebas | `http://localhost:8090/lab`: celulares simulados + tablero de órdenes y rutas | `bot/app/laboratorio.py` |
| App de Meta | BrotaBrisa conectada al número de prueba (webhook + suscripción de la cuenta) | [guia-bot-meta.md](guia-bot-meta.md) |
| Panel de coordinación (tablet) | Bandeja, asignar, rutas, cerrar e historial; probado de punta a punta | `web/coordinacion/` |
| Coordinación por WhatsApp | Respaldo opcional (`COORDINACION_POR_WHATSAPP=true`); por defecto solo alerta | [integracion-bot.md](integracion-bot.md) §4 |
| Pesajes en el panel, panel de la Fundación | Pendiente | `web/` |
| Brisa IA | Fase 1 (fichas, chequeos, resumen) construida; fases 2–5 (Gemini, audio, fotos, casos) por construir | [brisa-ia.md](brisa-ia.md) |
| Canjes, certificado, exportaciones | Pendiente | — |

Ramas en GitHub, cada una sobre la anterior: `feat/api-nucleo` → `feat/bot-whatsapp` →
`feat/coordinacion-whatsapp` (esta última aún local). **`main` no se ha modificado**; se fusiona
la última rama después de verificar.

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

## 7 · 18-nov-2026 · Bot con WhatsApp real y coordinación por WhatsApp (rama `feat/coordinacion-whatsapp`)

**Conexión real con Meta:**
- `bot/.env` con token, Phone Number ID y App Secret; bot local + túnel `cloudflared`; webhook
  verificado por Meta y suscrito a `messages`.
- Problema encontrado: el webhook estaba verificado pero no llegaba ningún mensaje. La cuenta de
  WhatsApp de prueba solo tenía suscrita la app interna de Meta. Se resolvió con
  `POST /{WABA_ID}/subscribed_apps` (nuevo script `uv run python -m app.meta suscribir --waba …`).
- Prueba desde un celular real: registro (Torre 2 · Apto 403), consentimiento y solicitud
  **BR-00002** creada en la API.

**Decisión:** la coordinadora gestiona por **WhatsApp con Brisa** (sin frontend por ahora; la tablet
llegará después sobre la misma API). Para probar, el celular de un compañero hace de coordinadora.

**API (migración `0002`):**
- `cuenta_operadora.celular_normalizado` (único). Con `X-Canal-Celular` de ese número, la API
  trata la llamada como la cuenta operadora y aplica sus permisos por gremio.
- `evento_salida.cuenta_operadora_id`: avisos dirigidos a la coordinación. Nuevo aviso
  `nueva_orden` para cada cuenta de coordinación del gremio con celular, al crear una solicitud.
- `PATCH /v1/cuentas-operadoras/{id}` admite `celular`.

**Bot (`bot/app/coordinacion.py`):** menú de coordinación, bandeja de nuevas y asignadas,
asignar recolector (lista con su teléfono) y franja (próximas franjas de hoy y mañana), cerrar como
recogida o rechazada con motivo del gremio. El aviso `nueva_orden` llega con el botón «Asignar».
Los botones llevan la orden en su `id`, así el flujo no depende de memoria.

**Verificación:** API 21 pruebas (nueva: coordinación por WhatsApp de punta a punta, permisos por
gremio y celular único); bot 19 pruebas (nuevas: menú, asignar y cerrar, rechazo con motivo,
franjas, aviso con botón). Migración probada de subida y bajada; contenedor de la API actualizado.

**Pendiente:** número del compañero en la cuenta `coord-reciclaje`, agregarlo como destinatario en
Meta y probar el ciclo completo con dos celulares.

---

## 8 · 19-nov-2026 · Laboratorio para ver el flujo completo (rama `feat/coordinacion-whatsapp`)

**Por qué:** aún no tenemos el número del compañero y queríamos ver el recorrido entero (vecino →
coordinación → recolector → cierre) sin depender de varios celulares.

**Qué es:** una página local servida por el bot, `http://localhost:8090/lab` (`LAB_ACTIVO=true`):
- Dos teléfonos tipo WhatsApp con personas de prueba: vecinos Laura, Carlos y Sofía; Coordinación
  Asorescatar y Coordinación Huerta Ecorazón. Botones y listas se tocan igual que en WhatsApp.
- Conversan con el **bot real y la API real**; solo cambia el último paso: lo que Brisa envía a un
  celular simulado se queda en el laboratorio y **nunca sale a Meta**. Los celulares reales siguen por
  WhatsApp y su conversación también se ve (solo lectura, número enmascarado).
- Tablero: órdenes por estado (nuevas, asignadas, recogidas, rechazadas) y **rutas de recolectores**
  (paradas pendientes por franja). El recolector no usa app: la coordinación lo llama.
- «Preparar demo»: con el PIN de `admin`, asigna a `coord-reciclaje` y `coord-huerta` los celulares
  simulados `573000000101` y `573000000102` (se cambian por el del compañero cuando lo tengamos).
- Seguridad: apagado por defecto y solo responde desde esta máquina; por el túnel de cloudflared o
  cualquier proxy devuelve 404.

**Verificación:** 4 pruebas nuevas (apagado por defecto, bloqueo por túnel, simulado no sale a Meta
y real sí, preparar demo); bot 23 pruebas. Recorrido hecho en el navegador: Carlos se registra
(Torre 1 · Apto 203) → pide reciclables (BR-00003) → la coordinación recibe «🆕» con «Asignar» →
Rosa, hoy 2–4 pm → Carlos recibe «🚲 Rosa pasa…» → la parada aparece en la ruta de Rosa → la
coordinación marca «Recogida» → Carlos recibe «+10 puntos · Tienes 10».

**Nota:** en el seed hay apartamentos del 101 al 504 (pisos 1–5, aptos 01–04). Una vivienda con
solicitud abierta no puede pedir otra del mismo servicio: Brisa le recuerda la que tiene.

**Incidente (19-nov, 2:45 a. m.):** Brisa no respondió al celular real. Los mensajes sí llegaban,
pero Meta rechazaba los envíos con el error 190: el token temporal de WhatsApp venció. Arreglo:
token nuevo en `bot/.env`. Ahora la consola lo dice en una línea clara en vez de un error largo, y ya
no se llena con las consultas del laboratorio. Solución de fondo: token permanente (usuario del
sistema), en la guía del número propio.

---

## 9 · 19-nov-2026 · Panel de coordinación para tablet (rama `feat/coordinacion-whatsapp`)

**Por qué:** en el diseño del sistema la coordinadora trabaja en la tablet, no en WhatsApp. Por
WhatsApp se ve una solicitud a la vez y no hay cómo registrar pesajes. La coordinación por WhatsApp
había sido un puente mientras no teníamos frontend.

**Qué se hizo:**
- `web/coordinacion/`: React 19 + Vite + TypeScript, puerto 3000, tablet primero (botones grandes,
  modo oscuro). Ingreso con usuario y PIN (JWT de la API).
  - **Bandeja:** nuevas y asignadas; se actualiza sola cada 15 s y avisa cuando llega una nueva.
  - **Asignar o reasignar:** recolector, franja y forma de aviso (llamada o recado).
  - **Rutas de hoy:** paradas por recolector, ordenadas por franja.
  - **Cerrar:** recogida o rechazada con motivo.
  - **Historial:** órdenes cerradas con totales del día.
  - Cada escritura usa `version_esperada` e `Idempotency-Key`. Si otra persona cambió la orden, el
    panel lo dice y recarga.
- Bot: a la coordinación ahora le llega **solo la alerta** «🆕 Nueva solicitud… 👉 Asígnala en el panel».
  Si le escribe a Brisa, recibe cuántas nuevas tiene y el enlace al panel. Las variables:
  - `COORDINACION_POR_WHATSAPP=true` devuelve los botones para asignar y cerrar desde el chat (respaldo
    si no hay tablet).
  - `PANEL_COORDINACION_URL` pone el enlace al panel en la alerta.
- La API no cambió: el panel usa `/v1/auth/sesiones`, `/v1/ordenes`, `/v1/recolectores`,
  `/v1/catalogos`, `asignacion` y `resultado`.

**Verificación:** el panel compila sin errores de tipos; bot 25 pruebas (nuevas: alerta hacia el
panel, botones en modo respaldo, la coordinadora que escribe recibe el enlace). Recorrido en el
navegador:
1. Sofía pide «Los dos» (BR-00004) y el panel la muestra sola, sin recargar.
2. Se asigna a Marta, hoy 2–4 pm: Sofía recibe «🚲 Marta pasa…» y la parada aparece en Rutas.
3. Se rechaza por «Material mojado»: Sofía recibe el consejo del cartón.
4. Laura pide reciclables (BR-00005): la coordinación recibe la alerta de solo texto, se asigna en el
   panel y se marca recogida. Laura gana +10 puntos.

Revisado en tamaño tablet (768 × 1024) sin errores en la consola.

**Incidente resuelto:** el token nuevo de WhatsApp ya funciona (Meta responde con los datos del número).

---

## 10 · 19-nov-2026 · Prueba real completa y diseño de Brisa IA

**Prueba con WhatsApp real:** el túnel de cloudflared se había cerrado; se abrió uno nuevo y se
actualizó el webhook en Meta. Recorrido completo:
1. Jeremy pide desde su celular (BR-00006).
2. La coordinación la asigna en el panel y Jeremy recibe el aviso.
3. Se cierra como recogida y Jeremy recibe sus puntos.

**Pedido del equipo:** un bot de reciclaje más potente. Que **enseñe antes de pedir**: qué
materiales, cómo prepararlos y chequeos como «¿el cartón está seco?». Que entienda fotos y audios
con IA y muestre un resumen con Enviar/Corregir/Cancelar. Que tenga un menú amigable (duda,
solicitud, queja, hablar con alguien) y responda cualquier pregunta. Se recibió un prompt maestro
completo para Brisa.

**Decisión:** «la IA entiende, el catálogo decide, la persona confirma y la API registra». Gemini
interpreta y redacta, pero si un material se recibe lo dice el catálogo de la API; nada se crea sin
«Enviar solicitud»; sin IA el bot sigue funcionando con listas y sinónimos.

**Documentos nuevos:**
- [brisa-ia.md](brisa-ia.md): conversación nueva, fichas de materiales, cambios en API, bot y panel,
  y 5 fases.
- [prompt-maestro-brisa.md](prompt-maestro-brisa.md): el prompt del equipo, con el menú ampliado.

**Pendiente del equipo:** criterios reales de Asorescatar y Ecorazón, a dónde llevar lo que no se
recibe, clave de Gemini y si se activa facturación (el plan gratuito puede usar los datos enviados).

---

## 11 · 19-nov-2026 · Brisa IA, fase 1: enseñar antes de pedir

**API (migración `0003`):**
- **`residuo`:** ficha de lo que declara el vecino. Dice si se recibe (`si`/`no`/`revision`) y qué
  gremio lo recoge, e incluye sinónimos, preparación, qué evitar, alternativa (a dónde llevar lo que
  no se recibe) y `verificaciones`: preguntas con opciones de botón y su resultado (listo, por
  preparar, no, revisión), con consejo.
  - Es una tabla aparte de `material` porque el material del pesaje lleva precio por kg y otra
    granularidad.
- **`solicitud_residuo`:** lo que el vecino declaró y lo que respondió.
- **`GET /v1/residuos`:** devuelve las fichas.
- **`POST /v1/solicitudes`:** acepta `residuos`. Los servicios (una orden por gremio) se deducen de
  ellos. Lo que no se recibe da 422, y una respuesta que la ficha no tiene, también.
- Cada orden trae sus residuos con `chequeos` legibles, y la alerta a la coordinación los nombra.
- **Seed:** 19 fichas de **ejemplo, por validar con Asorescatar y Ecorazón** (`api/app/seed_residuos.py`).
  - 10 reciclables u orgánicos que se reciben.
  - 1 en revisión (Tetra Pak).
  - 8 que no van en la ruta (comida cocinada, aceite, pilas, medicamentos, bombillos, químicos,
    electrónicos, icopor y sanitarios), cada uno con su alternativa.

**Bot:**
- **Menú en lista:** ♻ Pedir recolección · ❓ Tengo una duda · 📦 Mis solicitudes · ⭐ Mis puntos ·
  🏆 Liga. Si hay un pedido sin enviar, aparece «📝 Seguir mi pedido».
- **Pedido guiado (`pedido.py`):**
  1. Materiales por lista o por texto libre («cajas de pizza, botellas de vidrio y cáscaras»), con
     `catalogo.py`: sinónimos, plurales y la frase más larga primero.
  2. Brisa confirma lo que entendió.
  3. Por cada ficha muestra la preparación y hace 1 o 2 chequeos con botones.
  4. Pregunta «¿algo más?».
  5. Muestra un **resumen** con lo incluido, la ubicación y lo que queda por fuera, con
     **Enviar / Corregir / Cancelar**. Corregir permite quitar, agregar o volver a revisar lo que ya
     se preparó.
  6. Solo «Enviar» crea la solicitud, con el `wamid` como clave de idempotencia.
- **Dudas:** «¿el icopor se recicla?» muestra la ficha (✅ se recibe / 🔎 en revisión / 🚫 no va, con
  la alternativa) y ofrece pedirlo. Si un vecino menciona materiales sin estar pidiendo, primero se
  le enseña.
- **Ajuste tras probar:** si *algunas* botellas o latas tienen un problema, el material sigue en el
  pedido y Brisa solo pide separar lo malo («Saca los rotos; los enteros sí»).

**Panel:** cada tarjeta muestra los materiales con ✔ o «🔎 revisar al recoger» y lo que respondió el vecino.

**Verificación:** API 23 pruebas (catálogo de fichas, solicitud con residuos, rechazos, vista de
coordinación y alerta). Bot 32 pruebas (buscador de materiales, pedido completo, lo que no se recibe,
corregir y volver a revisar, dudas, menú que conserva el pedido, solicitud abierta, listo con
consejo). Recorrido real en el laboratorio:
1. Carlos escribe «tengo unas cajas de pizza, 4 botellas de vidrio y cáscaras de mango».
2. Brisa entiende cartón, vidrio y frutas.
3. Respuestas: cartón «no estoy seguro» (revisión), vidrio con rotos, frutas separadas.
4. Resumen y envío: **BR-00007**.
5. En el panel aparece «📦 Cartón 🔎 revisar al recoger · ¿Tu cartón está limpio y seco? No estoy seguro».

**Siguiente:** fase 2 con Gemini (texto libre e intención, respuestas a dudas fuera del catálogo).
Hace falta la clave en `api/.env`.

---

## Próximos pasos

- [ ] Revisar las ramas y fusionar `feat/coordinacion-whatsapp` a `main`.
- [x] Bot: Fase 1 de la guía (app de Meta y número de prueba).
- [x] Bot: esqueleto con registro, menú, solicitudes y avisos contra la API.
- [x] Bot: Fase 2 (webhook real con `cloudflared`) y prueba desde el celular.
- [x] Coordinación: ciclo completo probado en el laboratorio.
- [ ] Coordinación: probar con el celular de un compañero (asignar → aviso al vecino → cerrar).
- [x] Panel de coordinación para tablet (bandeja, asignar, rutas, cerrar, historial).
- [ ] Panel: pesajes (kg por material, tiquete con Gemini) y modo sin conexión.
- [x] Brisa IA fase 1: catálogo con fichas, flujo guiado y resumen (sin IA).
- [ ] Validar las fichas con Asorescatar y la Huerta Ecorazón.
- [ ] Brisa IA fases 2–4: IA de texto, audio y fotos; casos (quejas, hablar con una persona).
- [ ] Bot con número propio y token permanente (guía por escribir).
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
