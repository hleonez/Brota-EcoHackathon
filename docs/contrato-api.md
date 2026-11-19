# Contrato de API · Brota

Estado: **0.2-brota.1, implementado** en `api/` (FastAPI). Parte del contrato modular 0.2
(18-nov-2026) y del diseño de base de datos; reemplaza el borrador 0.1. Los esquemas exactos
de entrada y salida se publican en OpenAPI: `GET /docs` y `GET /openapi.json` en la API.
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
`DEPENDENCY_PENDING`, `OPERATION_TOO_OLD`, `DUPLICATE`, `INVALID_CREDENTIALS`.

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

El recolector no tiene cuenta: la coordinación registra por él. El rol `admin` no concede
bandeja ni datos personales de residentes.

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
| ● | `GET /v1/me` | `tipo_actor`, `registrado`, unidades, consentimiento vigente, permisos, capacidades |
| ● | `POST /v1/registros` | Canal: `{nombre, unidad_id, consentimiento}`; exige `aceptado` |
| ● | `POST /v1/registros/asistidos` | Coordinación/admin; puede quedar `incompleto` |
| ● | `POST /v1/me/consentimientos` | `aceptado` / `retirado` con versión vigente |
| ● | `POST`, `GET /v1/me/solicitudes-eliminacion` | `202` con seguimiento |
| ● | `GET`, `POST /v1/cuentas-operadoras`, `PATCH /v1/cuentas-operadoras/{id}` | Admin; PIN hasheado (scrypt); `celular` opcional para operar por WhatsApp (único) |

### M02 · Territorio y catálogos
| | Ruta | Notas |
| --- | --- | --- |
| ● | `GET /v1/conjuntos`, `GET /v1/conjuntos/{id}/torres` | Torres con `numero_viviendas` vigente |
| ● | `GET /v1/unidades` | Canal: solo coincidencia exacta `torre_id` + `referencia`; operadores: búsqueda |
| ● | `POST /v1/unidades` | Admin |
| ● | `GET /v1/catalogos` | Gremios, tipos de servicio, materiales, motivos, puntos de recepción, equivalencias vigentes |
| ● | `GET`, `POST /v1/recolectores`, `PATCH /v1/recolectores/{id}` | Coordinación del gremio o admin |

### M03 · Solicitudes y Pasaporte Circular
| | Ruta | Notas |
| --- | --- | --- |
| ● | `POST /v1/solicitudes` | Residente. Una orden por gremio, atómico. `unidad_id` opcional con una sola unidad |
| ● | `GET /v1/solicitudes` | `unidad_id?`, `abiertas?`. Residente: sus unidades; coordinación: su gremio |
| ● | `GET /v1/solicitudes/{id}` | `avance` con `estado_general`: `pendiente`, `en_curso`, `parcial`, `atendida` |
| ● | `GET /v1/solicitudes/{id}/pasaporte` | Eventos, pesajes de procedencia (sin reparto de kg) y puntos |

Regla de solicitud abierta (configurable, `REGLA_SOLICITUD_ABIERTA`): un servicio con orden
`nueva`/`asignada` en la misma unidad → `409 OPEN_REQUEST_EXISTS` con `codigo_pasaporte`.

### M04 · Coordinación
| | Ruta | Notas |
| --- | --- | --- |
| ● | `GET /v1/ordenes` | Bandeja: `gremio_id?`, `estado?`, `recolector_id?`, `desde?`, `hasta?` |
| ● | `GET /v1/ordenes/{id}` | Ubicación, contacto (nombre), asignación vigente, reasignaciones, resultado |
| ● | `POST /v1/ordenes/{id}/asignacion` | `{version_esperada, recolector_id, inicio?, fin?, forma_aviso}`; reasigna conservando historia; aviso `asignacion` |
| ● | `POST /v1/ordenes/{id}/resultado` | `{version_esperada, resultado, ocurrido_at, motivo_rechazo_id?, observacion?}` → `evaluacion_puntos`, `puntos_otorgados` |

### M05 · Pesajes y entregas directas
| | Ruta | Notas |
| --- | --- | --- |
| ● | `POST /v1/pesajes` | Crea **borrador**. Líneas `bascula` (kg) o `conversion_balde` (cantidad + equivalencia) |
| ● | `GET /v1/pesajes`, `GET /v1/pesajes/{id}` | Coordinación del gremio; totales, valor estimado y advertencias de tiquete repetido |
| ● | `PATCH /v1/pesajes/{id}` | Solo borrador; las listas enviadas sustituyen la lista completa |
| ● | `POST /v1/pesajes/{id}/confirmacion` | Revalida y aplica precios vigentes; solo confirmados cuentan |
| ● | `POST /v1/pesajes/{id}/correcciones` | Anula y crea reemplazo confirmado (`sustituye_pesaje_id`) |
| ● | `POST /v1/entregas-directas` | `{punto_recepcion_id, unidad_id?, participante_id?, pesaje}`; puntos al confirmar |
| ○ | `POST /v1/pesajes/desde-foto` | Papel Inteligente (M06) |

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
| ● | `GET /v1/contenidos-educativos` | Por `motivo_rechazo_id` / `material_id`, más los generales |
| ● | `GET /v1/ordenes/{id}/avisos` | Estado de avisos de una orden (coordinación) |
| ● | `POST /v1/canal/avisos/reservas`, `POST /v1/canal/avisos/{id}/resultado`, `GET /v1/canal/avisos` | Bot (modo pull). Modo webhook: ver integracion-bot.md |

### M09 · Liga y reportes
| | Ruta | Notas |
| --- | --- | --- |
| ● | `GET /v1/liga` | `conjunto_id, desde, hasta`. % hogares con entrega válida / viviendas vigentes; desempate por kg atribuidos |
| ● | `GET /v1/reportes/resumen` | Órdenes por estado, resultados, kg por material (báscula/estimado), valor estimado, hogares, tasas, cobertura |
| ● | `GET /v1/reportes/serie` | kg por `dia`/`semana`/`mes` local, para gráficas |
| ○ | Exportaciones, Certificado Verde, hoja de ruta, `/trabajos/{id}` | Pendiente |

### M10 · Configuración (admin)
● `POST /v1/materiales`, `PATCH /v1/materiales/{id}`, `POST /v1/motivos-rechazo`,
`POST /v1/contenidos-educativos`, `POST /v1/precios-material`, `POST /v1/equivalencias`,
`POST /v1/reglas-incentivo` (parámetros v1: `{"puntos": "10"}`), `POST /v1/torres/{id}/capacidades`,
`GET /v1/configuracion?tipo=`. Una versión nueva cierra la vigente; los solapamientos dan `409`.

### M11 · Sincronización offline
● `POST /v1/sync` `{dispositivo_id, operaciones[]}`. Acciones: `crear_pesaje`,
`actualizar_borrador_pesaje`, `confirmar_pesaje`, `registrar_entrega_directa`, `asignar_orden`,
`registrar_resultado_orden`. Estados por operación: `aplicada`, `repetida`, `conflicto`,
`rechazada`, `bloqueada`; `referencias` mapea IDs locales a IDs del servidor.

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
- No implementados todavía: archivos e IA (M06), canjes, exportaciones, certificados, hojas de ruta.
