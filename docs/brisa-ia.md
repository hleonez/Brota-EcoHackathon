# Brisa IA · diseño del bot de reciclaje

> Estado: **fase 1 construida** (19-nov-2026); fases 2–5 por construir. Recoge lo que pidió el equipo y el
> [prompt maestro de Brisa](prompt-maestro-brisa.md). Se construye por fases; cada fase se puede
> probar en el laboratorio (`/lab`) y con WhatsApp real.

## 1. Qué queremos

Hoy Brisa registra al vecino y crea la solicitud con un solo toque (♻ / 🍌 / 🔄). Funciona, pero el
recolector puede llegar y encontrar que nada se puede llevar: pierden tiempo el reciclador, el vecino
y la organización.

Queremos un bot que **primero enseñe y después ayude a pedir**:

- Un saludo amable con un menú amplio: pedir recolección, resolver dudas, consultar, quejarse o
  hablar con alguien. Además, que entienda texto libre en cualquier momento.
- Que pregunte **qué materiales** tiene la persona y, por cada uno, le dé los **cuidados** (por
  ejemplo, «el cartón mojado no sirve») con un **chequeo** corto antes de pedir.
- Que entienda **fotos y audios** con IA.
- Un **resumen** final con **Enviar solicitud**, **Corregir** o **Cancelar**. Nada se crea sin
  confirmación.
- Que la coordinación y el recolector sepan **qué materiales** van a encontrar y cómo los
  declaró el vecino.

## 2. Principio de diseño

**La IA entiende, el catálogo decide, la persona confirma y la API registra.**

| Quién | Qué hace | Qué no hace |
| --- | --- | --- |
| **IA (Gemini)** | Entiende texto, audio y fotos. Propone intención y materiales. Redacta respuestas a dudas con base en el catálogo. | Decidir si un material se recibe, inventar horarios, puntos o reglas, ni crear solicitudes. |
| **Catálogo (API)** | Dice si un material se recibe, quién lo recibe, cómo prepararlo, qué evitar y qué preguntar. | — |
| **Bot** | Guía la conversación con botones y listas, lleva el borrador y muestra el resumen. | Guardar fotos o audios. |
| **Persona** | Responde los chequeos y confirma el resumen. | — |
| **API** | Valida catálogo, permisos y duplicados. Crea la solicitud con sus materiales. | — |

Si la IA falla o se acaba la cuota, Brisa sigue funcionando con listas y sinónimos del catálogo.
La IA mejora la experiencia, pero el servicio no depende de ella.

## 3. La conversación nueva

### 3.1 Saludo y menú

```text
¡Hola, Carmen! 🌱 Soy Brisa. ¿En qué te ayudo hoy?
[ Ver opciones ▾ ]   (lista de WhatsApp)
  ♻ Pedir una recolección
  ❓ Tengo una duda          ¿Esto se recicla? ¿Cómo lo preparo?
  📦 Mis solicitudes        estado de lo que pedí
  ⭐ Mis puntos y la liga
  ⚠ Reportar un problema   no pasaron, mal trato, otro
  🙋 Hablar con una persona
```

WhatsApp permite máximo 3 botones por mensaje; por eso el menú es una **lista** (hasta 10 filas).
En cualquier momento la persona puede escribir, mandar un audio o una foto. Brisa detecta la
intención y responde primero a lo que preguntó. Siempre se puede escribir **MENÚ** o **CANCELAR**.

### 3.2 Pedir una recolección

```text
Brisa: ¿Qué vas a entregar? Escríbelo, mándame una foto o un audio, o elige de la lista.
       [ Elegir materiales ▾ ]  Cartón · Papel · Botellas PET · Plástico · Vidrio · Latas/metal · Orgánicos
Vecino: tengo unas cajas y unas botellas            ← texto, audio o foto
Brisa: Entendí: 📦 cartón y 🧴 botellas plásticas. ¿Es correcto?   [Sí] [Corregir]

── por cada material, su ficha (1 o 2 preguntas, nunca un formulario) ──
Brisa: 📦 El cartón se aprovecha si está limpio y seco, sin grasa ni comida.
       ¿Tu cartón está limpio y seco?   [Sí, está listo] [Está mojado] [No estoy seguro]
Vecino: Está mojado
Brisa: Si se mojó solo con agua, déjalo secar y lo pedimos después. Con grasa no lo reciben.
       Por ahora lo dejo por fuera. 💡 Aplánalo y guárdalo bajo techo.
Brisa: 🧴 Las botellas van vacías y tapadas; no hace falta lavarlas a fondo.
       ¿Están vacías?   [Sí] [No todavía]
Vecino: Sí

Brisa: ¿Tienes algo más?   [Agregar material] [No, eso es todo]

── resumen ──
Brisa: 🌱 Esto vamos a pedir:
       ♻ Botellas PET: vacías ✅
       📍 Torre 3 · Apto 402
       Queda por fuera: 📦 cartón (mojado). Cuando seque, lo pides.
       ¿La envío?   [Enviar solicitud] [Corregir] [Cancelar]
Vecino: Enviar solicitud
Brisa: ¡Listo! 💚 Tu solicitud BR-00018 quedó registrada. Te aviso quién pasa.
```

Reglas:

- Solo se pregunta lo que está en la ficha del material, y solo lo que falta.
- Cada material queda en uno de cuatro estados: **listo**, **por preparar** (fuera del envío, con
  instrucciones), **no se recibe** (con alternativa) o **en revisión** (la coordinación lo valida).
- Si hay reciclables y orgánicos, sale **una** solicitud con dos órdenes (Asorescatar y Ecorazón),
  como ya funciona.
- Los materiales peligrosos (pilas, medicamentos, agujas, químicos, bombillos) **nunca** entran en
  una recolección normal. Brisa explica dónde llevarlos según el catálogo.
- No se crea nada hasta que la persona toque **Enviar solicitud** (o lo escriba claramente). El
  mensaje que confirma el envío es la clave de idempotencia.

### 3.3 Dudas

«¿El icopor se recicla?», «¿dónde boto el aceite?», «¿la cáscara de huevo va a la huerta?»: la IA
responde en 1 a 3 frases con base en el catálogo. Si el catálogo no lo tiene, Brisa lo dice:
«Podría aprovecharse, pero necesito verificar si nuestro equipo lo recibe». Al final ofrece
[Pedir recolección] o [Otra duda].

### 3.4 Problemas y hablar con una persona

Se crea un **caso** (tipo, texto, solicitud relacionada si la hay) que aparece en el panel de
coordinación. Brisa solo dice «lo dejé registrado» cuando la API lo confirma.

## 4. Catálogo de materiales (fichas)

Hoy la tabla `material` solo tiene código, nombre y gremio. Cada material pasa a tener su ficha:

| Campo | Ejemplo (cartón) |
| --- | --- |
| `codigo`, `nombre`, `emoji` | CARTON, Cartón, 📦 |
| `categoria` | reciclable / organico / peligroso / no_aprovechable |
| `acepta` | si · no · revision |
| `gremio_id` | Asorescatar (vacío si no se recibe) |
| `sinonimos` | cajas, caja, cartones, empaque de cartón |
| `preparacion` | Limpio, seco y aplanado. Sin grasa ni restos de comida. |
| `evitar` | Mojado, con grasa (cajas de pizza), con cinta o plástico pegado. |
| `alternativa` | Para no aceptados: dónde llevarlo (p. ej. pilas → punto posconsumo). |
| `verificaciones` | «¿Está limpio y seco?» → Sí (listo) / Mojado (por preparar + consejo) / No sé (consejo) |
| `contenido_educativo` | Enlace a la ficha «Cómo entregar el cartón» (ya existe) |

Lista inicial propuesta. Es contenido de ejemplo y **debe validarse con Asorescatar y la Huerta
Ecorazón antes del piloto**:

- **Reciclables (Asorescatar):** cartón, archivo (papel blanco), periódico y revistas, plegadiza,
  PET, plástico soplado (envases de aseo), vidrio de envases, aluminio (latas), chatarra, Tetra Pak.
- **Orgánicos (Ecorazón):** cáscaras y restos de frutas y verduras, posos de café, cáscaras de
  huevo, hojas y poda. Carnes, huesos, lácteos, comida cocinada y aceite: en el ejemplo **no se
  reciben**, por confirmar con la huerta.
- **No se reciben en la ruta:** pilas, medicamentos, bombillos, aerosoles, aceite de cocina usado,
  icopor sucio, papel higiénico y servilletas usadas, pañales, vidrio roto o espejos. Cada uno con
  su alternativa.

## 5. Cambios por pieza

> **Construido en la fase 1:** tabla `residuo` (fichas, en `api/app/seed_residuos.py`) y
> `solicitud_residuo`; `GET /v1/residuos`; `POST /v1/solicitudes` con `residuos`; menú en lista, pedido
> guiado y dudas por ficha en el bot (`bot/app/pedido.py`, `bot/app/catalogo.py`); materiales y
> chequeos en las tarjetas del panel. La ficha es una tabla propia, no `material`, porque el
> material del pesaje lleva precio por kg y otra granularidad.

**API** (migración `0003`):

- `material`: nuevos campos de la ficha; `gremio_id` opcional para los no aceptados. Nueva tabla
  `verificacion_material` (pregunta, opciones, resultado de cada opción y consejo).
- `solicitud_material`: qué declaró el vecino por solicitud (material, cantidad aproximada en texto,
  estado de verificación, respuestas, fuente: lista, texto, foto o audio, y confianza de la IA).
- `POST /v1/solicitudes` acepta `materiales`; las órdenes por gremio se derivan de ellos.
  `tipo_servicio_ids` sigue funcionando.
- `GET /v1/materiales`: catálogo con fichas, para el bot y los paneles.
- `POST /v1/ia/interpretar` (texto, audio o imagen) → intención y materiales en JSON validado
  contra el catálogo. `POST /v1/ia/responder` → respuesta a una duda.
- `POST /v1/casos` y bandeja de casos para quejas y «hablar con una persona».

**Bot:** nuevo menú (lista), borrador de solicitud con estados por material, fichas y chequeos,
resumen con Enviar/Corregir/Cancelar, descarga de audio e imagen de Meta y envío a la API. El estado
de la conversación pasa de memoria a Redis cuando haya varias réplicas.

**Panel de coordinación:** cada tarjeta muestra los materiales y su chequeo («📦 Cartón · seco ✔»),
así se sabe qué llevar. Pestaña de **Casos**. Más adelante, edición del catálogo.

## 6. IA con Gemini

- **Dónde vive:** solo en la API (`GEMINI_API_KEY` en `api/.env`). El bot nunca ve la clave.
- **Modelo:** Gemini Flash, multimodal. Una sola llamada entiende texto, audio o imagen y devuelve
  **JSON con esquema** (intención, materiales con código del catálogo, condiciones mencionadas,
  dudas, peligros, confianza).
- **Instrucción de sistema:** el prompt maestro, dividido en dos:
  1. **Extracción:** corto y estricto, devuelve JSON.
  2. **Respuesta a dudas:** tono de Brisa, 1 a 3 frases.

  El catálogo vigente va incluido en el contexto; es pequeño.
- **Validación:** la API descarta códigos que no estén en el catálogo, y un material peligroso
  siempre se marca por la ficha, no por la IA. Si la confianza es baja, Brisa pregunta en vez de
  suponer.
- **Seguridad:** el texto que aparezca dentro de una foto o un audio es dato, nunca instrucción.
- **Privacidad:** las fotos y audios no se guardan; solo el resultado estructurado. El aviso de
  datos lo menciona. **Importante:** en el plan gratuito de Google AI Studio, Google puede usar lo
  enviado para mejorar sus productos. Para el piloto con vecinos reales conviene activar facturación
  (plan pagado) o, como mínimo, no enviar fotos con personas.
- **Sin IA** (error, cuota agotada o sin clave): sinónimos del catálogo y listas. Brisa avisa
  «hoy no puedo escuchar audios; escríbeme o elige de la lista».

## 7. Fases

| Fase | Entrega | Cómo se prueba |
| --- | --- | --- |
| **1. Catálogo y flujo guiado** (sin IA) ✅ | Fichas y chequeos, nuevo menú, materiales por lista o texto con sinónimos, resumen con Enviar/Corregir/Cancelar, materiales en la solicitud y en el panel | Laboratorio + WhatsApp real |
| **2. IA de texto** | Intención y materiales desde texto libre; respuestas a dudas con el catálogo | «tengo unas cajas y botellas», «¿el icopor se recicla?» |
| **3. Audio y fotos** | Descarga desde Meta → Gemini → «Entendí: … ¿Es correcto?» | Audio y foto desde el celular |
| **4. Casos** | Reportar problema y hablar con una persona; bandeja de casos en el panel | Queja desde WhatsApp → aparece en el panel |
| **5. Afinar** | Estado en Redis, plantillas de Meta, métricas (rechazos evitados, materiales más comunes) | Panel de la Fundación |

## 8. Lo que necesitamos del equipo

1. **Criterios reales** de Asorescatar y de la Huerta Ecorazón: qué reciben, cómo lo quieren y qué
   no. Mientras tanto se usa la lista de ejemplo marcada «por validar».
2. **A dónde mandar** lo que no se recibe (pilas, medicamentos, aceite) en Barranquilla.
3. **Clave de Gemini** de Google AI Studio en `api/.env` (fase 2) y decidir si se activa facturación
   para el piloto.
4. ¿Quién atiende los **casos** («hablar con una persona»): coordinación, Fundación o ambos?
