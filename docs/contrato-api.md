> Contrato vigente: `0.3-ecoconecta.2`. La entrada de preferencia cambió y ya no acepta el texto libre obligatorio de `0.3-ecoconecta.1`. El detalle de reglas, la matriz RN y lo que deben enviar el bot y el panel está en [estado de API](avance-api-ecoconecta.md). Gemini sigue desactivado. Donde una sección 0.2 contradiga este aviso o la sección 5, manda `0.3-ecoconecta.2`.

# Contrato de API · Brota

Estado: **0.3-ecoconecta.2, implementado** en `api/` (FastAPI), sobre la base 0.2-brota.1.
Los esquemas exactos de entrada y salida se publican en OpenAPI: `GET /docs` y `GET /openapi.json`.
Si este documento y OpenAPI discrepan, manda OpenAPI y se corrige este archivo.

Integración del bot de WhatsApp: [integracion-bot.md](integracion-bot.md).

## 1. Convenciones

- Base local `http://localhost:8000/v1`; detrás del proxy `/api/v1` (`ROOT_PATH=/api`). Salud fuera de `/v1`.
- JSON UTF-8, campos `snake_case`, IDs UUID como string generados por el servidor.
- Escritura: se rechazan campos desconocidos (`422`). Lectura: los clientes ignoran campos nuevos.
- Instantes ISO 8601 con zona; respuestas en UTC con `Z`. Periodos `[desde, hasta)`. Meses y
  semanas locales en `America/Bogota`.
- **Decimales como strings con punto**: kg con 3 decimales (`"9.000"`), puntos con 2, precios con 4.
  Un número JSON (`9.0`) se rechaza.
- Respuesta individual `{"data": {...}}`; listas `{"data": [...], "pagination": {"limit", "offset", "has_more"}}`
  (`limit` 20 por defecto, máximo 100; orden `created_at` desc, `id` desc).
- Error: `{"error": {"code", "message", "fields?", "request_id", ...}}`. `code` es estable.
- Recursos editables traen `version`; las acciones exigen `version_esperada` (`409 VERSION_CONFLICT`).
- `POST`/`PATCH` de dominio exigen `Idempotency-Key` (1–128). Misma clave y cuerpo → misma
  respuesta (cabecera `Idempotent-Replayed: true`); otro cuerpo → `409 IDEMPOTENCY_CONFLICT`;
  sin clave → `400 IDEMPOTENCY_KEY_REQUIRED`. Retención: 72 h. Excepciones: `/auth/sesiones`,
  `/sync` (usa `operacion_id` por operación) y `/canal/avisos/*`.

Códigos: `200`, `201`, `202`, `400`, `401`, `403`, `404` (inexistente o fuera de ámbito), `409`,
`422`, `503`. Códigos de error de dominio: `VALIDATION_ERROR`, `VERSION_CONFLICT`,
`INVALID_TRANSITION`, `OPEN_REQUEST_EXISTS`, `IDEMPOTENCY_CONFLICT`, `CONSENT_REQUIRED`,
`NOT_REGISTERED`, `CONTACT_ALREADY_REGISTERED`, `LIGA_NOT_CONFIGURED`, `VIGENCIA_SOLAPADA`,
`DEPENDENCY_PENDING`, `OPERATION_TOO_OLD`, `DUPLICATE`, `INVALID_CREDENTIALS`, `PILOT_NOT_ENABLED`,
`TIQUETE_ILEGIBLE`.

## 2. Actores y autenticación

`Authorization: Bearer <token>`:

| Actor | Credencial | Alcance |
| --- | --- | --- |
| Bot de WhatsApp (servicio) | `BOT_SERVICE_TOKEN` | Reservar y confirmar avisos |
| Residente / negocio | `BOT_SERVICE_TOKEN` + `X-Canal-Celular` | Su perfil, solicitudes de sus unidades, puntos, Liga |
| Contacto no registrado | Igual, número sin registro | Registrarse, consultar territorio y catálogos |
| Coordinación | JWT de `POST /v1/auth/sesiones` (usuario + PIN) | Órdenes, recolectores y pesajes **de su gremio** |
| Fundación | JWT, rol `fundacion` | Reportes agregados y Liga |
| Administración | JWT, rol `admin` | Catálogos, configuración y cuentas |

Reciclador y huertero pueden tener cuenta y atender solo su asignación vigente. La coordinación
sigue pudiendo registrar el resultado de quien no tiene teléfono. `admin` no concede bandeja,
directorio de unidades ni datos personales. Fundación ve reportes agregados, sin dirección ni celular.

## 3. Endpoints

`●` implementado · `○` previsto en 0.2, aún no implementado.

### M12 · Salud, capacidades y sesión
| | Ruta | Notas |
| --- | --- | --- |
| ● | `GET /health/live`, `GET /health/ready` | `ready` comprueba PostgreSQL (`503` si no) |
| ● | `GET /v1/capacidades` | Módulos activos, decimales, sync, modo de avisos, política vigente |
| ● | `POST /v1/auth/sesiones` | `{usuario, pin}` → `{token, expira_en, cuenta}` |

### M01 · Identidad
| | Ruta | Notas |
| --- | --- | --- |
| ● | `GET /v1/me` | `tipo_actor`, `registrado`, unidades, consentimiento, permisos, capacidades y `habilitaciones` vigentes del participante |
| ● | `POST /v1/registros` | Canal: `{nombre, unidad_id, consentimiento}`; exige `aceptado` |
| ● | `POST /v1/registros/asistidos` | Coordinación/admin; puede quedar `incompleto` |
| ● | `POST /v1/me/consentimientos` | `aceptado` / `retirado` con versión vigente |
| ● | `POST`, `GET /v1/me/solicitudes-eliminacion` | `202` con seguimiento |
| ● | `GET`, `POST /v1/cuentas-operadoras`, `PATCH /v1/cuentas-operadoras/{id}` | Admin; PIN hasheado (scrypt); `celular` opcional para operar por WhatsApp (único) |
| ● | `GET /v1/participantes` | Solo admin. `id`, `nombre` y unidades con vínculo vigente (`id`, `tipo`, `etiqueta`). Excluye `eliminado`; incluye a quien aún no tiene habilitación. Coordinación y fundación reciben `403` |

### M02 · Territorio y catálogos
| | Ruta | Notas |
| --- | --- | --- |
| ● | `GET /v1/conjuntos`, `GET /v1/conjuntos/{id}/torres` | Torres con `numero_viviendas` vigente |
| ● | `GET /v1/unidades` | Canal: coincidencia exacta `torre_id` + `referencia`. Directorio filtrado: solo coordinación de su gremio. Admin, fundación y trabajador reciben `403` |
| ● | `GET /v1/unidades/gestion` | Solo admin. Unidades activas con `id`, `tipo`, `referencia_local`, `etiqueta` y torre. Filtro opcional `tipo`. Coordinación, fundación y trabajador reciben `403`. No abre el directorio de coordinación |
| ● | `POST /v1/unidades` | Admin |
| ● | `GET /v1/catalogos` | Gremios, tipos de servicio, materiales, motivos, puntos de recepción, equivalencias vigentes |
| ● | `GET`, `POST /v1/recolectores`, `PATCH /v1/recolectores/{id}` | Coordinación del gremio o admin |

### M03 · Solicitudes y Pasaporte Circular
| | Ruta | Notas |
| --- | --- | --- |
| ● | `GET /v1/residuos` | Fichas: si se recibe (`acepta`: si/no/revision), gremio, sinónimos, preparación, qué evitar, alternativa y `verificaciones` (preguntas con opciones y resultado) |
| ● | `POST /v1/solicitudes` | Residente con habilitación vigente (`403 PILOT_NOT_ENABLED` si falta, venció o está revocada; no se hereda por torre). Preferencia exclusiva: ventana `preferencia_inicio`/`preferencia_fin` o `preferencia_sin_restriccion: true` con fechas nulas. La respuesta incluye `preferencia_horaria` derivada y `tipo_generador` copiado de la unidad. Una orden por gremio. `unidad_id` opcional con una sola unidad. Residuo con `acepta: no` → 422 |
| ● | `GET /v1/solicitudes` | `unidad_id?`, `abiertas?`. Residente: sus unidades; coordinación: su gremio |
| ● | `GET /v1/solicitudes/{id}` | `avance.estado_general`: `pendiente`, `en_curso`, `parcial`, `atendida`, `cancelada`, `rechazada`, `finalizada_con_novedades` |
| ● | `GET /v1/solicitudes/{id}/pasaporte` | Eventos, pesajes de procedencia (sin reparto de kg) y puntos |

Cada orden trae `residuos` (los de su gremio) con `estado` (`listo`/`revision`) y `chequeos` legibles, para la
bandeja de coordinación.

Regla de solicitud abierta (configurable, `REGLA_SOLICITUD_ABIERTA`): un servicio con orden
`nueva`/`asignada` en la misma unidad → `409 OPEN_REQUEST_EXISTS` con `codigo_pasaporte`.

`POST /v1/solicitudes/{id}/cancelacion` (residente, `{motivo?}`): las órdenes `nueva`/`asignada` pasan a
`cancelada` y se avisa a la coordinación (`orden_cancelada`); si no queda ninguna abierta → `409`.

### M13 · Casos (reportes y «hablar con una persona»)
| | Ruta | Notas |
| --- | --- | --- |
| ● | `POST /v1/casos` | Residente. `{tipo: queja\|ayuda, texto, codigo_pasaporte?}` → `CA-00001`. Alerta `nuevo_caso` a la coordinación del gremio de esa solicitud, o a todas si no nombra una |
| ● | `GET /v1/casos` | Coordinación (su gremio y los sin gremio) o admin. `estado?` = abierto/atendido |
| ● | `POST /v1/casos/{id}/atencion` | `{version_esperada, respuesta}` → `atendido`; la respuesta le llega al vecino (`caso_respuesta`) |

### M04 · Coordinación
| | Ruta | Notas |
| --- | --- | --- |
| ● | `GET /v1/ordenes` | Bandeja: `gremio_id?`, `estado?`, `recolector_id?`, `desde?`, `hasta?` |
| ● | `GET /v1/ordenes/{id}` | Ubicación, contacto (nombre), asignación vigente, reasignaciones, resultado |
| ● | `POST /v1/ordenes/{id}/asignacion` | `{version_esperada, recolector_id, inicio?, fin?, forma_aviso, acuerdo_canal?, acuerdo_observacion?}`. Sin franja queda `asignada` y no copia el horario anterior. `orden_reasignada` solo si cambia la persona. Con franja exige `acuerdo_canal` (`whatsapp`, `llamada`, `presencial`) y pasa a `programada` |
| ● | `POST /v1/ordenes/{id}/programacion` | Misma regla que asignar con franja. No emite un segundo evento si ya lo registró la asignación. Reprogramar a la misma persona emite `orden_reprogramada` |
| ● | `POST /v1/ordenes/{id}/resultado` | Solo si está `programada`. `{version_esperada, resultado, ocurrido_at, materiales_confirmados, motivo_rechazo_id?, observacion?}`. Recogida: UUID existentes del mismo gremio. Rechazo: lista vacía y motivo. `ocurrido_at` no puede estar en el futuro. Repetir el cierre no duplica puntos |

### M05 · Pesajes y entregas directas
| | Ruta | Notas |
| --- | --- | --- |
| ● | `POST /v1/pesajes` | Crea **borrador**. Líneas `bascula` (kg) o `conversion_balde` (cantidad + equivalencia) |
| ● | `GET /v1/pesajes`, `GET /v1/pesajes/{id}` | Coordinación del gremio; totales, valor estimado y advertencias de tiquete repetido |
| ● | `PATCH /v1/pesajes/{id}` | Solo borrador; las listas enviadas sustituyen la lista completa |
| ● | `POST /v1/pesajes/{id}/confirmacion` | Revalida y aplica precios vigentes; solo confirmados cuentan |
| ● | `POST /v1/pesajes/{id}/correcciones` | Anula y crea reemplazo confirmado (`sustituye_pesaje_id`) |
| ● | `POST /v1/entregas-directas` | `{punto_recepcion_id, unidad_id?, participante_id?, pesaje}`; puntos al confirmar |
| ● | `POST /v1/pesajes/desde-foto` | Papel Inteligente. Coordinación del gremio e `Idempotency-Key`. `{gremio_id, imagen: {mime_type: image/*, datos_base64}, recolector_id?, fecha_medicion?, orden_ids?, torre_origen_id?, unidad_medida_id?, emisor_tiquete?}`. Crea borrador `origen_captura=foto_ia`; no lo confirma ni guarda la imagen. La respuesta añade `dudosos` (`campo`, `confianza?`, `detalle`) y `materiales_descartados`. Umbral 0,6: la línea entra al borrador y queda marcada si hay kilos; sin kilos no entra. Un `GET` posterior no repite `dudosos`. Códigos fuera del catálogo del gremio se descartan. `422 TIQUETE_ILEGIBLE` si no hay ninguna línea usable. `503 IA_NO_DISPONIBLE` si la IA está apagada: no se guarda nada y el pesaje se registra a mano. La confirmación sigue en `POST /v1/pesajes/{id}/confirmacion` |

### M06 · IA (Gemini)
| | Ruta | Notas |
| --- | --- | --- |
| ● | `POST /v1/ia/interpretar` | `{texto?, media?: {mime_type: image/*\|audio/*, datos_base64}, contexto: general\|pedido}` → `intencion` (pedir, duda, estado, puntos, liga, cancelar, queja, persona, saludo, otro), `residuos` (solo códigos del catálogo, con `confianza`), `transcripcion`, `observado`, `peligros`, `respuesta` (solo para dudas), `aclaracion`. Sin efectos ni almacenamiento. `503 IA_NO_DISPONIBLE` sin clave o con el modelo saturado |

### M07 · Puntos
| | Ruta | Notas |
| --- | --- | --- |
| ● | `GET /v1/me/puntos`, `GET /v1/me/movimientos-puntos` | Saldo = suma del libro |
| ○ | Canjes (`/catalogo-canjes`, `/canjes`) | Pendiente: titularidad del saldo por validar |

No existe endpoint para «enviar puntos». Abonos: `entrega_valida` (+10, al confirmar recogida) y
`entrega_directa` (+15, al confirmar el pesaje), únicos por hecho (`clave_aplicacion`).

### M08 · Educación y avisos
| | Ruta | Notas |
| --- | --- | --- |
| ● | `GET /v1/contenidos-educativos` | Se lee sin sesión. Público: `tema` (`separacion`, `huerta`, `horarios_rutas`, `servicio`), `version`, vigencia y publicación. Filtro `tema`. Borradores (`publicado` falso) y retirados (`activo` falso o fuera de vigencia) no aparecen; un Bearer inválido sigue en `401`. Admin: `PATCH /v1/contenidos-educativos/{id}` edita título, texto, tema, publicación, activo, gremio y vigencia |
| ● | `GET /v1/contenidos-educativos/gestion` | Solo admin. El mismo contenido, incluidos borradores, retirados y fuera de vigencia. Filtro opcional `tema`. Coordinación y fundación reciben `403`. La lectura pública no cambia |
| ● | `GET /v1/ordenes/{id}/avisos` | Estado de avisos de una orden (coordinación) |
| ● | `POST /v1/canal/avisos/reservas`, `POST /v1/canal/avisos/{id}/resultado`, `GET /v1/canal/avisos` | Bot (modo pull). Modo webhook: ver integracion-bot.md |

### M09 · Liga y reportes
| | Ruta | Notas |
| --- | --- | --- |
| ● | `GET /v1/liga` | `conjunto_id, desde, hasta`. % hogares con entrega válida / viviendas vigentes; desempate por kg atribuidos |
| ● | `GET /v1/reportes/resumen` | Órdenes por estado, resultados, kg por material (báscula/estimado), valor estimado, hogares, tasas, cobertura |
| ● | `GET /v1/reportes/serie` | kg por `dia`/`semana`/`mes` local, para gráficas |
| ● | `GET /v1/reportes/certificado` | Fundación o administración. `conjunto_id` y `mes=AAAA-MM`. Responde `application/pdf` (`certificado-verde-{conjunto}-{mes}.pdf`), generado al vuelo y sin persistir la emisión. Kilos aprovechados (reciclables), compostados (orgánicos), tasa de rechazo, hogares y torres. Solo pesajes `confirmado` del mes en `America/Bogota` con torre del conjunto. Un mes sin datos devuelve PDF en ceros. Coordinación: `403`. Mes inválido: `422`. Conjunto inexistente: `404`. Apoyo documental: no determina la tarifa ni sustituye el aforo |
| ○ | Exportaciones Excel, hoja de ruta, `/trabajos/{id}` | Pendiente |

### M10 · Configuración (admin)
● `GET /v1/materiales` (admin; incluye inactivos y `version`), `POST /v1/materiales`, `PATCH /v1/materiales/{id}` (nombre y activo), `POST /v1/motivos-rechazo`,
`POST /v1/contenidos-educativos`, `POST /v1/precios-material`, `POST /v1/equivalencias`,
`POST /v1/reglas-incentivo` (parámetros v1: `{"puntos": "10"}`), `POST /v1/torres/{id}/capacidades`,
`GET /v1/configuracion?tipo=`. Una versión nueva cierra la vigente; los solapamientos dan `409`.

### M11 · Sincronización offline
● `POST /v1/sync` `{dispositivo_id, operaciones[]}`. Acciones: `crear_pesaje`,
`actualizar_borrador_pesaje`, `confirmar_pesaje`, `registrar_entrega_directa`, `asignar_orden`,
`programar_orden`, `registrar_resultado_orden`. El actor tiene que coordinar o ser el trabajador
de la operación; un trabajador solo puede `registrar_resultado_orden`. Cada operación usa las
mismas reglas que su ruta HTTP. Estados: `aplicada`, `repetida`, `conflicto`, `rechazada`,
`bloqueada`; `referencias` mapea IDs locales a IDs del servidor. Un aviso `pendiente` no es un
envío de WhatsApp.

## 4. Diferencias respecto del contrato 0.2

- El webhook de WhatsApp vive en el bot, no en la API; se añade el módulo **canal**
  (`/v1/canal/avisos/*`) y la entrega opcional por webhook firmado hacia el bot.
- `POST /v1/solicitudes` admite omitir `unidad_id` cuando el residente tiene una sola unidad.
- `GET /v1/solicitudes` añade el filtro `abiertas`; `GET /v1/reportes/serie` es nuevo.
- Los avisos incluyen `texto_sugerido` en la voz de Brisa.
- Coordinación por WhatsApp: una cuenta operadora con `celular` se autentica con el token del bot
  y `X-Canal-Celular` (mismos permisos que con JWT). Nuevo aviso `nueva_orden` hacia la coordinación
  del gremio; los avisos indican `destino.tipo` (`participante` u `operador`).
- La Liga usa una fórmula fija identificada (`participacion_hogares_v1`) y el número de viviendas
  vigente al cierre del periodo; `version_regla_liga` queda para cuando se apruebe otra fórmula.
- No implementados todavía: archivos, canjes, exportaciones Excel y hojas de ruta. El Certificado Verde sí se emite en `GET /v1/reportes/certificado` y no se persiste.
- `POST /v1/ia/interpretar` responde `503` y no llama a Gemini. `GET /v1/capacidades` informa `ia_disponible: false` y `piloto: restringido`.

## 5. Cambios incompatibles de `0.3-ecoconecta.2`

El bot y el panel tienen que dejar de enviar `preferencia_horaria` como campo de entrada.

- Enviar una sola alternativa: `preferencia_sin_restriccion: true` sin fechas, o `preferencia_inicio` y `preferencia_fin` con `fin` posterior. Las dos juntas, o ninguna, responden `422`.
- Leer `preferencia_horaria` solo como texto derivado (`Sin restricción` o la franja en `America/Bogota`). Filas anteriores a esta versión pueden venir con preferencia nula: no fue capturada.
- `tipo_generador` (`hogar` o `negocio`) es de salida. Se copia de la unidad y no otorga permisos.
- Programar exige `acuerdo_canal`. `acuerdo_observacion` es opcional. La respuesta de la asignación puede incluir `programada_por`.
- El cierre envía `materiales_confirmados` como lista de UUID del catálogo `material`. Un UUID desconocido no se guarda ni se inventa. Los kilos siguen saliendo del pesaje.
- Tratar `programada` como estado propio. `cancelada` y `rechazada` no son recogidas. Una recogida junto con un rechazo es `finalizada_con_novedades`, no `atendida`.
- Mostrar `tema` en educación y las `habilitaciones` de `GET /v1/me`.
- No usar el directorio `GET /v1/unidades` desde admin, fundación o la cuenta del trabajador. La administración lista unidades con `GET /v1/unidades/gestion`.
