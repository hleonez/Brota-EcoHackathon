# Contrato modular de API · Brota

**Estado:** borrador 0.2 para acordar con el equipo y ajustar con el contexto de la hackathon.

**Fecha:** 18 de noviembre de 2026.

**Fuentes:** [Plan Maestro](../Brota_Plan_Maestro_NeuralSprint.md), especialmente secciones 4, 5 y 8–13; [diseño de base de datos](diseno-base-de-datos.md).

Este documento reemplaza el contrato inicial 0.1. Define interfaces propuestas; no declara endpoints implementados, no crea tablas y no selecciona framework, ORM, proveedor de IA ni mecanismo de autenticación. PostgreSQL puede ser local o gestionado sin cambiar el contrato público.

## 1. Propósito y mapa de módulos

Una API compartida sirve a WhatsApp, la web de respaldo, la tablet de coordinación y los paneles institucionales. Los residentes solicitan; los coordinadores registran por los recolectores; la IA propone y las personas confirman. Los reportes e incentivos se derivan de hechos registrados, sin exigir una aplicación al recolector.

```text
Canales → identidad y consentimiento → solicitud → órdenes por gremio
                                                    ↓
                                            asignación y resultado
                                                    ↓
Recepción directa ───────────────────────────────→ pesaje
                                                    ↓
                              puntos / educación / Liga / reportes

Archivos e IA: producen propuestas para revisión.
Offline: sincroniza las mismas acciones del dominio, con permisos y versiones.
```

| Módulo | Responsabilidad | Correspondencia con datos / plan |
| --- | --- | --- |
| M01 Identidad y acceso | Registro progresivo, consentimiento, cuentas y permisos | Participante, vínculos, consentimiento, cuenta operadora; CU-01 |
| M02 Territorio y catálogos | Unidades, gremios, servicios, recolectores, materiales y motivos | Conjunto, torre, unidad y catálogos; soporte de CU-02 a CU-08 |
| M03 Solicitudes y Pasaporte | Pedir uno o varios servicios y consultar su trazabilidad | Solicitud, selección de servicios y órdenes; CU-02, CU-04 |
| M04 Coordinación | Bandeja, asignación y confirmación o rechazo | Asignación, resultado e historia; CU-05 a CU-07 |
| M05 Pesajes y entregas directas | Borradores, kg, baldes, procedencia y correcciones | Pesaje, líneas, enlaces y entrega directa; CU-08, CU-09 |
| M06 Archivos e IA | Foto de tiquete, voz e interpretación asistida | Archivo y procesamiento IA; CU-03, CU-08 |
| M07 Puntos y canjes | Acreditación trazable, saldo y beneficios | Versiones de reglas, movimientos, aliados y catálogo; CU-10, CU-12 |
| M08 Educación y avisos | Contenido por rechazo y mensajería reintentable | Contenidos y eventos de salida; CU-11 |
| M09 Liga y reportes | Indicadores, exportación, certificados y hojas de ruta | Agregaciones de hechos confirmados; CU-13, CU-14, CU-17 |
| M10 Configuración | Precios, equivalencias y reglas con vigencia | Versiones de configuración; CU-15 |
| M11 Sincronización | Operaciones offline, dependencias y conflictos | Idempotencia, versiones y eventos; CU-16 |
| M12 Canales y salud | Webhook verificado, capacidades y disponibilidad | Adaptadores, trabajos y conexión a PostgreSQL |

El núcleo inicial comprende identidad mínima, catálogos, solicitudes, coordinación, pesaje manual, puntos por entrega validada y resumen. Foto de tiquete, baldes, Liga y offline son objetivos de demo del plan. Canjes y Ojo Verde pueden quedar como prototipo. La prioridad final se acuerda con el reto; documentar una ruta no obliga a construirla antes de conocerlo.

## 2. Convenciones comunes

### 2.1. Transporte y representación

- HTTP y JSON UTF-8, salvo carga de archivos y descargas indicadas expresamente.
- Base local: `http://localhost:8000/v1`. Base con proxy: `/api/v1`. Todas las rutas de los módulos son relativas a esa base; salud queda fuera de `/v1`.
- IDs opacos enviados como strings, generados por el servidor. Los ejemplos usan IDs ficticios. Los IDs locales offline y las claves de operación son identificadores distintos.
- Campos en `snake_case`. `?` en tablas significa opcional; los campos requeridos se enumeran sin ese signo. No se aceptan campos desconocidos en escritura.
- Instantes ISO 8601 con zona u offset; respuestas en UTC con `Z`. Periodos `[desde, hasta)`, con `desde < hasta`. El mes local se interpreta en `America/Bogota` antes de convertir sus límites a UTC.
- Kilos, puntos, precios y equivalencias se intercambian como **strings decimales con punto**, por ejemplo `"9.000"`, y se procesan con precisión decimal. No se admite coma decimal, notación exponencial, `NaN` o infinito. Escalas y máximos se publicarán en capacidades al aprobar las reglas.
- Un campo ausente no solicita modificarlo. En `PATCH`, `null` borra únicamente campos declarados anulables. No se usa cero para reemplazar un dato ilegible.
- Recursos persistidos incluyen `id`, `created_at`; los editables incluyen `version` entera creciente. Proyecciones y resultados de acciones no necesitan un ID artificial.

### 2.2. Respuestas, listas y errores

Respuesta individual y lista:

```json
{"data":{"id":"orden-demo-1","estado":"nueva","version":1}}
```

```json
{"data":[],"pagination":{"limit":20,"offset":0,"has_more":false}}
```

Listas: `limit` por defecto 20, máximo 100; `offset` no negativo. Orden por `created_at` descendente e `id` descendente, salvo Liga, que devuelve posición según su fórmula. Los filtros solo restringen lo que el actor puede consultar; nunca amplían permisos.

| Código | Significado |
| --- | --- |
| `200` | Consulta, actualización o acción completada |
| `201` | Recurso creado |
| `202` | Trabajo aceptado, aún pendiente; devuelve recurso consultable |
| `400` | JSON, parámetro técnico o clave de idempotencia ausente/inválida |
| `401` / `403` | Falta autenticación / falta permiso |
| `404` | Recurso inexistente o fuera del ámbito visible del actor |
| `409` | Conflicto de versión, transición, duplicado operativo, saldo o inventario |
| `413` / `415` | Archivo demasiado grande / tipo de archivo no admitido |
| `422` | Datos de dominio inválidos o referencias inconsistentes |
| `429` | Límite de solicitudes; incluir `Retry-After` cuando se conozca |
| `503` | Dependencia o servicio temporalmente no disponible |

```json
{
  "error": {
    "code": "VERSION_CONFLICT",
    "message": "La orden cambió. Revisa su estado antes de continuar.",
    "fields": {"version_esperada": "Se esperaba la versión 3"},
    "request_id": "req-demo-1"
  }
}
```

`code` es estable; `message` es texto para la persona. `fields` es opcional. Otros códigos previstos: `VALIDATION_ERROR`, `INVALID_TRANSITION`, `OPEN_REQUEST_EXISTS`, `IDEMPOTENCY_CONFLICT`, `INSUFFICIENT_POINTS`, `OUT_OF_STOCK`, `DEPENDENCY_PENDING`, `OPERATION_TOO_OLD`, `FEATURE_DISABLED`. Los errores no incluyen contraseñas, tokens o respuestas internas de proveedores.

### 2.3. Escrituras, concurrencia y reintentos

Las escrituras de dominio por `POST` y `PATCH` requieren `Idempotency-Key`, string de 1 a 128 caracteres generado para cada operación lógica. Excepciones: el webhook se deduplica por mensaje del proveedor; el lote de sync usa claves por operación, además de su propia clave para repetir la entrega del lote.

La clave se delimita por actor y acción sobre recurso/ruta. Mismo contenido devuelve el código y cuerpo exitoso originales; contenido distinto con la misma clave produce `409 IDEMPOTENCY_CONFLICT`. Se vuelve a comprobar el acceso vigente antes de devolver una respuesta conservada. Las escrituras y el registro de la clave son atómicos también bajo concurrencia. Los errores previos a la escritura no consumen la clave.

Las modificaciones sobre recursos versionados requieren `version_esperada`; si no coincide, `409 VERSION_CONFLICT`. Un reintento idempotente exitoso se resuelve antes de volver a evaluar la versión antigua. No se sobrescriben cambios de otro operador por llegar más tarde desde una tablet desconectada.

Retención mínima de claves HTTP: 24 horas. Para offline, la retención debe cubrir la ventana anunciada por el servidor. Fuera de esa ventana se requiere revisión; no se vuelve a ejecutar a ciegas una operación cuya deduplicación ya no pueda garantizarse.

## 3. Actores, autenticación y permisos

| Actor | Acceso propuesto |
| --- | --- |
| Residente / contacto de negocio | Su perfil, vínculos, solicitudes, puntos y canjes autorizados |
| Coordinación | Órdenes, recolectores, recepciones y pesajes de su gremio; datos mínimos para prestar el servicio |
| Recolector | Actor externo sin cuenta obligatoria; coordinación registra por él |
| Fundación | Indicadores, certificados y exportaciones agregadas; sin directorio personal por defecto |
| Administrador | Catálogos, configuración y gestión de cuentas mediante capacidades explícitas; el rol no concede automáticamente lectura de todo dato personal |
| Sistema | Casos de uso internos de IA, reglas, avisos y sincronización bajo identidad y alcance comprobados |

El mecanismo de autenticación se resolverá con el reto. Este contrato no presupone JWT, contraseña para residentes ni un proveedor específico. La identidad de WhatsApp procede del adaptador verificado; el cliente no puede adquirir permisos enviando un celular o un rol en el cuerpo.

Los endpoints para personas requieren una sesión o identidad verificada del canal. El registro inicial usa una identidad provisional verificada. La web de respaldo necesitará su propio mecanismo para demostrar acceso al contacto, pendiente de elección; conocer un `unidad_id` no autoriza a actuar por ese hogar.

Las cuentas internas las habilita una persona autorizada. La API valida alcance y permisos en cada operación. La cuenta PostgreSQL de la API es independiente de estos roles de negocio.

## 4. M01 · Identidad, registro y consentimiento

| Método y ruta | Entrada o filtros | Respuesta / acceso |
| --- | --- | --- |
| `GET /me` | Identidad de la sesión o canal | Perfil, vínculos visibles y capacidades del actor; `200` |
| `POST /registros` | `nombre`, `unidad_id`, `consentimiento: {version_politica, decision}` | Participante, vínculo y estado del registro; `201`; identidad provisional verificada |
| `POST /registros/asistidos` | `nombre`, `unidad_id?`, `celular?`, `consentimiento?` | Registro progresivo; `201`; coordinación autorizada |
| `POST /me/consentimientos` | `version_politica`, `decision` | Nuevo hecho de consentimiento; `201` |
| `POST /me/solicitudes-eliminacion` | `observacion?` | Solicitud de gestión de datos con `id` y `estado: pendiente`; `202` |
| `GET /me/solicitudes-eliminacion` | Paginación | Seguimiento privado: `id`, `estado: pendiente \| en_revision \| resuelta`, fechas y respuesta de gestión si existe |
| `POST /cuentas-operadoras` | `nombre`, `referencia_autenticacion?`, `permisos[]` | Cuenta habilitada; `201`; gestión de accesos |
| `PATCH /cuentas-operadoras/{id}` | `version_esperada`, `activo?`, `permisos?` | Cuenta actualizada; gestión de accesos |

`decision` es `aceptado` o `retirado`. El servidor fija fecha, canal y evidencia. El celular del alta por WhatsApp se deriva del canal verificado; no se pide repetirlo ni se permite sustituirlo desde ese cuerpo. El consentimiento se registra con versión publicada de política. Repetir el registro de un contacto ya asociado produce `409`, sin crear otra persona.

El registro asistido puede carecer de teléfono o vínculo completo y devuelve `estado_registro: incompleto`. No inventa consentimiento ni habilita automáticamente consultas remotas. Una entrega sin persona identificada puede registrarse en M05; no obliga a crear un participante ficticio.

`GET /me` diferencia `tipo_actor: participante | operador`, `participante_id?`, `cuenta_operadora_id?`, `unidades[]` y `capacidades[]`. Cada permiso interno contiene `rol` y `gremio_id?`; el alcance institucional requiere capacidad explícita. El alta no admite que un residente elija rol de coordinación.

La gestión de cuentas no permite conceder capacidades o ámbitos que la persona administradora no esté autorizada expresamente a delegar. Se auditan actor, destinatario y cambios de permisos.

La selección de unidad en el registro procede de opciones guiadas del canal o búsqueda autorizada de M02. Mudanzas, cambio de número, recuperación de identidad y verificación de vínculos quedan pendientes de protocolo; no se resuelven con una edición libre del perfil.

Una solicitud de eliminación no promete borrado instantáneo: devuelve seguimiento privado y aplica el procedimiento de conservación acordado sobre contactos, archivos, propuestas de IA y copias. Retirar consentimiento no borra silenciosamente hechos operativos ni permite continuar finalidades que ya no estén autorizadas.

## 5. M02 · Territorio y catálogos

| Método y ruta | Entrada o filtros | Respuesta |
| --- | --- | --- |
| `GET /conjuntos` | Paginación | Conjuntos habilitados sin datos personales |
| `GET /conjuntos/{id}/torres` | Paginación | Torres y referencias para registro |
| `GET /unidades` | `torre_id?`, `tipo?`, `referencia?`, paginación | Búsqueda restringida a registro asistido/operación autorizada |
| `POST /unidades` | `tipo`, `torre_id?`, `referencia_local`, `direccion_referencia?` | Unidad; `201`; registro territorial autorizado |
| `GET /catalogos` | `gremio_id?` | `gremios`, `tipos_servicio`, `materiales`, `motivos_rechazo`; solo información operativa visible |
| `GET /recolectores` | `gremio_id?`, `activo?`, paginación | Recolectores del ámbito autorizado |
| `POST /recolectores` | `gremio_id`, `nombre`, `telefono_contacto?` | Recolector sin cuenta; `201`; gestión autorizada |
| `PATCH /recolectores/{id}` | `version_esperada`, `nombre?`, `telefono_contacto?`, `activo?` | Actualiza contacto o actividad; conserva historia |

`tipo` de unidad: `hogar | negocio`. Un hogar de torre requiere `torre_id`; un negocio del corredor puede no tenerlo. Las opciones guiadas no publican nombres, teléfonos o directorios completos de apartamentos.

Entradas de catálogo: `id`, `codigo`, `nombre`, `activo`; servicios y materiales incluyen `gremio_id`, motivos pueden ser generales o de gremio. El catálogo inicial contiene reciclables y orgánicos. «Los dos» es una selección de servicios, no un tercer gremio.

Los recolectores se separan del catálogo general para no entregar sus contactos a residentes. Cambiar de gremio no es una edición ordinaria: requiere procedimiento que conserve la pertenencia histórica.

## 6. M03 · Solicitudes y Pasaporte Circular

| Método y ruta | Entrada o filtros | Respuesta |
| --- | --- | --- |
| `POST /solicitudes` | `unidad_id`, `tipo_servicio_ids[]`, `observacion?`, `archivo_ids?`, `propuesta_ia_id?` | Solicitud y órdenes creadas atómicamente; `201` |
| `GET /solicitudes` | `unidad_id?`, paginación | Solicitudes propias; coordinación recibe solo datos de su ámbito |
| `GET /solicitudes/{id}` | ID | Solicitud, órdenes visibles y resumen de avances |
| `GET /solicitudes/{id}/pasaporte` | ID | Historia autorizada, resultados, referencias a pesajes y efectos en puntos |

Se exige al menos un servicio activo sin duplicados y un vínculo autorizado con la unidad, salvo representación asistida explícita. El servidor deriva participante y canal y conserva la referencia de ubicación del momento. Crea una orden por gremio distinto y registra qué servicios corresponden a cada orden.

Ejemplo mixto:

```http
POST /v1/solicitudes
Content-Type: application/json
Idempotency-Key: 7621d141-dc53-42c3-b740-b19fb7d68f59
```

```json
{
  "unidad_id": "unidad-demo-402",
  "tipo_servicio_ids": ["servicio-reciclables", "servicio-organicos"],
  "observacion": "Cartón y restos de cocina"
}
```

```json
{
  "data": {
    "id": "solicitud-demo-18",
    "created_at": "2026-11-20T15:00:00Z",
    "version": 1,
    "codigo_pasaporte": "BR-00018",
    "unidad_id": "unidad-demo-402",
    "canal_origen": "whatsapp",
    "tipo_servicio_ids": ["servicio-reciclables", "servicio-organicos"],
    "avance": {"ordenes_totales": 2, "ordenes_finalizadas": 0},
    "ordenes": [
      {"id":"orden-demo-r","gremio_id":"gremio-asorescatar","estado":"nueva","version":1},
      {"id":"orden-demo-h","gremio_id":"gremio-ecorazon","estado":"nueva","version":1}
    ]
  }
}
```

El ejemplo representa una llamada del adaptador WhatsApp; el cuerpo no puede imponer ese origen. Una propuesta de IA solo se consume al confirmar la persona y no puede reutilizarse para crear solicitudes repetidas.

El Pasaporte no es una credencial pública. Coordinación no obtiene detalles del otro gremio por navegar desde una solicitud mixta; el residente sí consulta el avance de sus servicios. En respuestas restringidas, `avance` refleja el ámbito visible y lo indica con `alcance: propio | gremio`.

La prevención de solicitudes abiertas duplicadas es una regla provisional del plan: una vez habilitada, se comprueba transaccionalmente por unidad y servicio activo, con `409 OPEN_REQUEST_EXISTS` y referencia a la solicitud visible. Deben acordarse excepciones comerciales antes de imponerla. No se confunde con idempotencia de un mismo intento.

Cancelar antes de confirmar una interpretación de Brisa descarta la propuesta y no crea trabajo. Cancelar una orden ya creada o reabrirla requiere las reglas pendientes de la sección 17; no se ofrece un borrado de solicitudes.

## 7. M04 · Coordinación y resultado humano

| Método y ruta | Entrada o filtros | Respuesta |
| --- | --- | --- |
| `GET /ordenes` | `gremio_id?`, `estado?`, `recolector_id?`, `desde?`, `hasta?`, paginación | Bandeja; rango sobre creación |
| `GET /ordenes/{id}` | ID | Orden, asignación vigente, resultado y versión |
| `POST /ordenes/{id}/asignacion` | `version_esperada`, `recolector_id`, `inicio?`, `fin?`, `forma_aviso` | Orden con asignación vigente y nueva versión; `200` |
| `POST /ordenes/{id}/resultado` | `version_esperada`, `resultado`, `ocurrido_at`, `motivo_rechazo_id?`, `observacion?` | Orden finalizada y estado de evaluación de puntos; `200` |

```text
nueva → asignada → recogida
                ↘ rechazada
```

Asignar exige un recolector activo del mismo gremio. `forma_aviso: llamada | recado`; describe la comunicación humana con el recolector, distinta del aviso automático al residente. El horario puede omitirse; si se envía, exige ambos extremos y `fin > inicio`. Se puede reasignar mientras siga asignada, cerrando la asignación anterior y conservando su historia.

`resultado: recogida | rechazada` se registra desde `asignada` por coordinación. El rechazo requiere motivo vigente compatible con el gremio; una recogida no admite motivo de rechazo total. El servidor registra `confirmado_por` y `confirmado_at`; `ocurrido_at` permite indicar cuándo sucedió la entrega y no puede situarse en el futuro del servidor.

Ejemplo de validación:

```json
{
  "version_esperada": 2,
  "resultado": "recogida",
  "ocurrido_at": "2026-11-20T16:30:00-05:00"
}
```

La respuesta incluye `estado`, `resultado`, `version` y `evaluacion_puntos: pendiente | acreditada | no_aplica | requiere_revision`. Si la evaluación es asíncrona, el evento durable se registra junto con el resultado. La ausencia de una respuesta de mensajería no revierte la validación.

Un rechazo total da cero puntos y programa educación; no descuenta saldo. Una orden finalizada no acepta otro resultado con otra clave: `409 INVALID_TRANSITION`. El reintento con su misma clave devuelve el resultado original.

## 8. M05 · Pesajes, baldes y entregas directas

### 8.1. Rutas y estados

| Método y ruta | Entrada | Respuesta |
| --- | --- | --- |
| `POST /pesajes` | Cabecera y líneas de abajo | Borrador manual o de baldes; `201` |
| `GET /pesajes` | `gremio_id?`, `recolector_id?`, `estado?`, `desde?`, `hasta?`, paginación | Pesajes del ámbito; rango sobre `fecha_medicion` |
| `GET /pesajes/{id}` | ID | Detalle, procedencia, evidencia, estado y versión |
| `PATCH /pesajes/{id}` | `version_esperada` y campos editables | Borrador actualizado; `200` |
| `POST /pesajes/{id}/confirmacion` | `version_esperada` | Registro oficial, autor y fecha; `200` |
| `POST /pesajes/{id}/correcciones` | `version_esperada`, `motivo`, `pesaje_reemplazo` | Nuevo pesaje confirmado que sustituye al anterior; `201`; permiso de corrección |
| `POST /entregas-directas` | Datos de recepción y `pesaje` | Entrega y borrador de pesaje relacionados; `201` |

```text
borrador → confirmado → anulado por corrección
```

Todos los orígenes pasan por confirmación explícita, incluida la digitación manual. Esto unifica tablet, foto y offline. Solo cuentan en informes los confirmados no anulados.

### 8.2. Cabecera y líneas

Crear un pesaje recibe `gremio_id`, `fecha_medicion`, `origen_captura`, `orden_ids`, `lineas`, y opcionalmente `recolector_id`, `proveedor_referencia`, `numero_tiquete`, `emisor_tiquete`, `torre_origen_id`, `unidad_medida_id`, `archivo_ids`, `observacion`.

`origen_captura: manual | baldes`; `foto_ia | dictado` se derivan del procesamiento revisado de M06. En el borrador, `PATCH` admite fecha, proveedor, referencias de tiquete, procedencia, órdenes, líneas, archivos y observación; las listas enviadas sustituyen la lista completa. Gremio y origen no se cambian para reutilizar el registro con otro propósito.

Cada línea contiene `material_id`, `metodo_medicion` y una de estas representaciones:

| Método | Datos de entrada | Cálculo / salida |
| --- | --- | --- |
| `bascula` | `kg_aceptados`, `kg_rechazados`, `motivo_rechazo_id?` | Conserva medición real |
| `conversion_balde` | `cantidad_aceptada`, `cantidad_rechazada`, `version_equivalencia_id`, `motivo_rechazo_id?` | Servidor calcula kg y devuelve cantidad original, equivalencia y resultado marcado como estimación |

No se mezclan ambas representaciones dentro de una línea. Se exige al menos una línea, sin materiales repetidos; cantidades no negativas y algún valor mayor que cero. Kilos o cantidades rechazadas exigen motivo. Se aceptan fracciones de balde como `"0.5"`; no se impone un peso universal por balde.

Precios, versiones aplicadas y valor estimado se resuelven en el servidor según la fecha de medición y configuración vigente. Si falta un precio, se devuelve `null`, no cero. Si falta equivalencia, no se confirma una conversión. La confirmación vuelve a comprobar catálogo, procedencia y configuración y devuelve las versiones efectivamente aplicadas.

Ejemplo de lote:

```json
{
  "gremio_id": "gremio-asorescatar",
  "recolector_id": "recolector-demo-rosa",
  "fecha_medicion": "2026-11-20T17:00:00-05:00",
  "origen_captura": "manual",
  "orden_ids": ["orden-demo-402", "orden-demo-403"],
  "torre_origen_id": "torre-demo-3",
  "numero_tiquete": "38298",
  "lineas": [
    {"material_id":"material-carton","metodo_medicion":"bascula","kg_aceptados":"9.000","kg_rechazados":"0.000"},
    {"material_id":"material-pet","metodo_medicion":"bascula","kg_aceptados":"3.000","kg_rechazados":"0.000"}
  ]
}
```

### 8.3. Procedencia, entrega directa y corrección

- Las órdenes vinculadas deben estar recogidas y corresponder al gremio y recolector del lote. Para un lote de ruta sin órdenes individualizadas se permite `orden_ids: []`; la modalidad de ruta exige recolector identificado.
- Vincular órdenes **no reparte kilos**. Los 12 kg del ejemplo pertenecen al lote, no se convierten en 6 kg por hogar.
- `torre_origen_id` exige procedencia comprobada y coherente con todas las órdenes enlazadas. Si mezcla torres sin medición separada, se omite y el informe lo muestra sin atribución.
- `unidad_medida_id` es el hogar o negocio cuyo material completo se midió individualmente. No es una unidad física de medida. Todas las órdenes enlazadas deben corresponder a esa unidad; no se admite para un lote mezclado.
- El tiquete no tiene unicidad global asumida. Una coincidencia puede producir una advertencia de revisión, no un reparto ni descarte automático de evidencia.

`POST /entregas-directas` recibe `punto_recepcion`, `unidad_id?`, `participante_id?` y `pesaje` con la estructura anterior, sin órdenes. Crea recepción y borrador en una transacción; el recolector es opcional. El punto se valida contra la configuración del ámbito. Si se identifica participante, se comprueba su vínculo con la unidad; si se desconoce, se registra el material sin otorgar puntos personales.

La entrega directa se valida operativamente al confirmar su pesaje; ese hecho puede originar su incentivo específico si hay beneficiario y regla aprobada. No se crean solicitud y asignación ficticias. El pesaje individual exige que `unidad_medida_id` coincida con la unidad de recepción.

La corrección recibe un reemplazo completo con el mismo esquema de cabecera y líneas y motivo obligatorio. En una transacción anula el anterior, confirma el reemplazo, enlaza `sustituye_pesaje_id` y registra los efectos o eventos de reversión de incentivos aplicables. El historial no se borra y los reportes excluyen el anterior. Anular sin reemplazo, corregir resultados de orden y resolver cambios de periodo certificado requieren política adicional antes de habilitarse.

## 9. M06 · Archivos, Papel Inteligente e interpretación

| Método y ruta | Entrada | Respuesta |
| --- | --- | --- |
| `POST /archivos` | `multipart/form-data`: `archivo`, `proposito` | Metadatos y `archivo_id`; `201` |
| `POST /pesajes/desde-foto` | `archivo_id`, `gremio_id` | Procesamiento asíncrono de tiquete; `202` |
| `POST /interpretaciones` | `tipo` (solicitud, dictado_pesaje o clasificacion_residuo), `texto?`, `archivo_id?`, `gremio_id?` | Procesamiento de IA; `202` |
| `GET /procesamientos-ia/{id}` | ID | Estado, propuesta, campos dudosos y error recuperable si existe |
| `POST /procesamientos-ia/{id}/revision` | `decision` (aceptada, corregida o descartada), `datos_confirmados?`, `version_esperada` | Propuesta revisada; para tiquete/dictado crea borrador de pesaje; `200` |

`proposito: tiquete | audio_solicitud | dictado | foto_residuo`. Tamaños máximos, MIME admitidos y retención se anuncian en capacidades. El servidor comprueba contenido y pertenencia del archivo, sin aceptar una URL arbitraria de almacenamiento enviada por el cliente. Los adjuntos obtenidos de WhatsApp los importa su adaptador.

Estados de procesamiento: `pendiente | procesando | listo | fallido | revisado | descartado`. `GET` devuelve `tipo`, `estado`, `version`, `propuesta?`, `campos_revision[]` y `error?`. Un valor ilegible aparece como `null` en la propuesta; confirmar exige resolver los campos obligatorios. La confianza no sustituye la revisión humana.

Para tiquete/dictado, `datos_confirmados` contiene la estructura válida de M05; el origen se deriva del trabajo y el actor debe ser coordinación del gremio. La revisión devuelve `pesaje_borrador_id`. Repetirla no crea más borradores. Solo `POST /pesajes/{id}/confirmacion` produce un pesaje oficial.

Para solicitud, la interpretación devuelve `tipo_servicio_ids`, `materiales_sugeridos`, `observacion` y un texto corto de confirmación. Tras revisión del residente, M03 crea la solicitud usando `propuesta_ia_id`. Revisar por sí solo no crea órdenes. Ojo Verde devuelve una sugerencia y tampoco crea órdenes, pesajes ni puntos.

Los audios pueden pasar por un servicio de transcripción antes del modelo de lenguaje. No se fija Claude, Whisper u otro proveedor en este contrato. No se envía a un proveedor externo el directorio de participantes ni más información de la necesaria para la tarea. Si la IA falla, el flujo manual sigue disponible.

## 10. M07 · Puntos, saldo y canjes

| Método y ruta | Entrada o filtros | Respuesta |
| --- | --- | --- |
| `GET /me/puntos` | Identidad | `saldo`, `titularidad`, estado de evaluación pendiente |
| `GET /me/movimientos-puntos` | `desde?`, `hasta?`, paginación | Movimientos con `delta`, tipo, regla y referencia de origen visible |
| `GET /catalogo-canjes` | `aliado_id?`, paginación | Ítems activos, costo, disponibilidad e inventario si se controla |
| `POST /canjes` | `item_id`, `cantidad` | Canje, costo aplicado, débito y saldo resultante; `201` |
| `POST /canjes/asistidos` | `participante_id`, `item_id`, `cantidad` | Canje representado por operador autorizado; `201` |
| `GET /me/canjes` | `estado?`, paginación | Canjes propios |
| `POST /canjes/{id}/entrega` | `version_esperada` | Canje entregado; `200`; operador autorizado |

La acreditación de puntos es un caso de uso interno disparado por resultado humano o entrega directa confirmada, y por medición individual cuando la modalidad lo permita. **No se expone un endpoint público para enviar una cantidad de puntos a acreditar.**

Reglas del contrato:

1. Se premia lo validado, no lo solicitado. Rechazo: cero, sin penalización monetaria o de puntos.
2. Modalidad por entrega válida como propuesta inicial; por kg solo con pesaje individual confirmado y configuración del conjunto.
3. No se asume acumulación entre modalidades. La regla aprobada determina sustitución o complemento.
4. Cada abono conserva versión de regla, origen, beneficiario y atribución territorial del hecho. La unicidad del beneficio se mantiene aunque cambie la versión de regla.
5. Correcciones generan reversión y movimientos nuevos. Un movimiento histórico no se edita ni elimina.
6. La titularidad provisional del saldo es personal; debe validarse antes de construir canjes. La contribución a una torre no crea automáticamente un segundo saldo canjeable de torre.

Movimientos: `abono | debito_canje | reversion | reintegro`. `delta` puede ser negativo por consumo o reversión, no por castigo ante rechazo. El saldo es la suma del libro; si una corrección afecta puntos ya gastados, el tratamiento del saldo requiere aprobación antes de habilitar ese escenario.

Crear canje deriva el participante de la identidad, fija el precio vigente y descuenta existencias y saldo en una sola transacción. `cantidad` es entero positivo. Dos canjes concurrentes no pueden consumir el mismo saldo ni la última existencia. `409 INSUFFICIENT_POINTS` o `OUT_OF_STOCK` no dejan débito parcial. Estados propuestos: `reservado → entregado`; el saldo se debita al reservar. Cancelación y reintegro requieren política pendiente y no se ofrecen como edición libre.

## 11. M08 · Educación y avisos

| Método y ruta | Entrada o filtros | Respuesta |
| --- | --- | --- |
| `GET /contenidos-educativos` | `material_id?`, `motivo_rechazo_id?`, paginación | Título, tipo y recurso publicado |
| `GET /ordenes/{id}/avisos` | Paginación | Estado de avisos propios del gremio; coordinación autorizada |

Un resultado rechazado selecciona contenido por motivo y material cuando se conozca. Si no existe correspondencia, se usa contenido general configurado o se deja pendiente de revisión; no se inventa un video. Un rechazo de kilos en un lote mezclado no permite culpar ni enviar un rechazo personal automático a cada hogar enlazado.

La asignación y los puntos generan sus propios avisos. Los eventos de salida se guardan junto con el hecho que los origina y se envían después del commit, con reintentos. Estados visibles: `pendiente | enviado | fallido`; «enviado» no equivale a leído. El sistema usa los identificadores del proveedor para reconciliar confirmaciones sin repetir el efecto de negocio.

No se expone una ruta de envío arbitrario para que cualquier cliente escriba a un teléfono. SMS, llamada automática y proveedor de WhatsApp son adaptadores sustituibles y dependen de su configuración y autorización.

## 12. M09 · Liga, panel, reportes y documentos

| Método y ruta | Entrada o filtros | Respuesta |
| --- | --- | --- |
| `GET /liga` | `conjunto_id`, `desde`, `hasta` | Ranking agregado, fórmula aplicada y cobertura de datos |
| `GET /reportes/resumen` | `desde`, `hasta`, `gremio_id?`, `conjunto_id?`, `torre_id?`, `unidad_id?`, `material_id?`, `recolector_id?` | Indicadores permitidos por el alcance del actor |
| `POST /reportes/exportaciones` | `tipo: resumen`, mismos filtros, `formato` (csv o xlsx) | Trabajo de exportación; `202`; acceso institucional o coordinación según ámbito |
| `POST /reportes/certificados` | `conjunto_id`, `mes` en `YYYY-MM` | Emisión mensual de Certificado Verde; `202`; permiso institucional |
| `POST /reportes/hojas-ruta` | `fecha` local `YYYY-MM-DD`, `gremio_id`, `recolector_id?` | Documento de asignaciones; `202`; coordinación |
| `GET /trabajos/{id}` | ID | `estado` (pendiente, procesando, listo o fallido), metadatos y enlace de descarga autorizado cuando esté listo |

`GET /liga` devuelve `conjunto_id`, `periodo`, `version_regla_liga_id`, `calculado_at`, `torres[]`. Cada torre contiene `posicion`, `torre_id`, `hogares_participantes`, `viviendas_base`, `porcentaje_participacion`, `kg_aceptados_atribuidos`; sin nombres, celulares o apartamentos. Fórmula provisional: hogares distintos con entrega válida / viviendas vigentes × 100. Los kg se muestran separados y solo con procedencia comprobada.

Sin regla aprobada o denominador válido, la Liga devuelve `409` con código `LIGA_NOT_CONFIGURED`; no publica una clasificación engañosa. Desempates y cambios de capacidad dentro del periodo se fijan en la versión de regla antes de publicar. La Liga solo se expone públicamente cuando se habilite esa capacidad.

El resumen devuelve `periodo`, `corte_datos`, `ordenes_por_estado`, `materiales[]`, `tasa_rechazo_peso`, `tasa_rechazo_ordenes`, `valor_estimado?` y `cobertura`. Para órdenes se filtra por creación; tasas de resultado por `ocurrido_at`; pesajes por `fecha_medicion`. Cada bloque indica su criterio temporal para no comparar cohortes distintas como si fueran iguales.

Reglas de cálculo y privacidad:

- Solo pesajes confirmados no anulados; cada línea se suma una vez, aunque tenga varias órdenes enlazadas.
- Separar kg de báscula y estimados por conversión. Mostrar kg sin torre identificada y precios desconocidos.
- Tasa por peso: kg rechazados / kg totales recibidos. Tasa por órdenes: rechazadas / órdenes con resultado final. Sin denominador, valor `null` y estado `sin_datos`.
- Filtros por hogar solo atribuyen kilos cuando existe `unidad_medida_id`. Un enlace con una orden del hogar no permite asignarle kilos del lote.
- Las agregaciones territoriales cuentan una sola vez el lote medido; los lotes sin procedencia comprobada no se incorporan artificialmente al conjunto filtrado. `cobertura` explicita el criterio y la exclusión.
- Valor por recolector es estimación con precios aplicados, no un pago certificado ni ingreso efectivamente recibido. El detalle nominal requiere permiso adicional.
- Sin registros, conteos y kg son cero, tasas sin denominador son `null` y se incluyen estados conocidos aunque tengan conteo cero.

Los trabajos pertenecen al actor/ámbito que los creó; conocer su ID o URL no autoriza a descargar. Las descargas requieren autenticación o un enlace temporal autorizado y devuelven el MIME del documento. Las hojas de ruta contienen datos operativos mínimos y no se entregan a la Liga pública.

Cada certificado conserva periodo, corte, fórmula y versión de emisión; una corrección produce una nueva emisión identificable. Apoya la gestión de tarifa multiusuario, sin sustituir el aforo ni prometer reducción automática. La política de conservación y el soporte documental exacto se validarán con la Fundación.

## 13. M10 · Administración y configuración versionada

Todas las rutas requieren capacidad de configuración. Consultar versiones aplicadas históricamente no significa poder modificarlas.

| Método y ruta | Entrada principal | Comportamiento |
| --- | --- | --- |
| `POST /materiales` | `codigo`, `nombre`, `gremio_id` | Crea material de catálogo; `201` |
| `PATCH /materiales/{id}` | `version_esperada`, `nombre?`, `activo?` | Conserva referencias históricas |
| `POST /motivos-rechazo` | `codigo`, `nombre`, `gremio_id?` | Crea motivo; `201` |
| `POST /contenidos-educativos` | `titulo`, `tipo`, `recurso`, `material_ids`, `motivo_rechazo_ids` | Crea asociación educativa; `201` |
| `POST /precios-material` | `material_id`, `precio_kg`, `moneda`, `vigente_desde`, `vigente_hasta?` | Nueva versión de precio |
| `POST /equivalencias` | `gremio_id`, `punto_recepcion?`, `recipiente`, `kg_por_unidad`, vigencia | Nueva versión de conversión |
| `POST /reglas-incentivo` | `codigo`, `modalidad`, `ambito`, `parametros`, vigencia | Nueva versión validada de regla |
| `POST /modalidades-conjunto` | `conjunto_id`, `modalidad`, vigencia | Activa modalidad por conjunto |
| `POST /reglas-liga` | `conjunto_id`, `formula`, `parametros`, vigencia | Nueva versión de fórmula y desempate |
| `POST /torres/{id}/capacidades` | `numero_viviendas`, vigencia | Histórico del denominador; entero positivo |
| `GET /configuracion` | `tipo`, `gremio_id?`, `conjunto_id?`, `fecha?` | Versiones visibles y vigencias; no contiene secretos de proveedores |

En esta tabla `vigencia` significa los campos `vigente_desde`, `vigente_hasta?`; todas las creaciones devuelven recurso/version y `201`. `ambito` es `{tipo: global | gremio | conjunto, id?}`; `id` es obligatorio salvo global y se valida contra el tipo. `parametros` tiene un esquema acotado por modalidad/fórmula y una versión, no código arbitrario.

Los precios admiten cero; equivalencias y viviendas deben ser positivas. Las vigencias no se solapan en el mismo concepto y ámbito. Reemplazar una versión abierta cierra su intervalo y crea la nueva atómicamente; requiere `version_anterior_id` cuando exista. Cambiar configuración nunca recalcula automáticamente los hechos ni vuelve a premiarlos.

No se fijan como obligatorios los ejemplos de +10 o +15 puntos. Rachas, acumulación de beneficios y la transcripción ambigua del multiplicador del plan quedan pendientes. Sin configuración válida no se inventa una equivalencia ni una recompensa; el hecho operativo se conserva y su evaluación queda pendiente o requiere revisión.

## 14. M11 · Operación offline y sincronización

| Método y ruta | Entrada | Respuesta |
| --- | --- | --- |
| `POST /sync` | `dispositivo_id`, `operaciones[]` | `200` con resultado por operación, incluso si algunas entran en conflicto |

El dispositivo debe estar asociado a la cuenta autenticada; no concede permisos propios. Cada operación incluye `operacion_id` como clave de idempotencia estable, `accion`, `recurso_id?`, `referencia_local?`, `depende_de[]`, `datos` y `creada_local_at`. Las fechas del dispositivo no sustituyen la auditoría del servidor.

Acciones iniciales permitidas: `crear_pesaje`, `actualizar_borrador_pesaje`, `confirmar_pesaje`, `registrar_entrega_directa`, `asignar_orden`, `registrar_resultado_orden`. Usan exactamente las validaciones, versiones y permisos de M04/M05. No se acepta una URL o SQL arbitrario dentro del lote; canjes y administración no se sincronizan offline en esta propuesta.

Ejemplo abreviado de dependencias:

```json
{
  "dispositivo_id": "tablet-demo-huerta",
  "operaciones": [
    {
      "operacion_id": "op-demo-1",
      "accion": "crear_pesaje",
      "referencia_local": "local-pesaje-1",
      "depende_de": [],
      "creada_local_at": "2026-11-20T16:00:00-05:00",
      "datos": {
        "gremio_id": "gremio-ecorazon",
        "recolector_id": "recolector-demo-huerta",
        "fecha_medicion": "2026-11-20T16:00:00-05:00",
        "origen_captura": "baldes",
        "orden_ids": [],
        "lineas": [{"material_id":"material-organicos","metodo_medicion":"conversion_balde","cantidad_aceptada":"1.5","cantidad_rechazada":"0","version_equivalencia_id":"equivalencia-demo-1"}]
      }
    },
    {
      "operacion_id": "op-demo-2",
      "accion": "confirmar_pesaje",
      "recurso_id": "local-pesaje-1",
      "depende_de": ["op-demo-1"],
      "creada_local_at": "2026-11-20T16:01:00-05:00",
      "datos": {"version_esperada": 1}
    }
  ]
}
```

El servidor procesa dependencias en orden válido. Una referencia local solo se resuelve dentro del contexto del actor/dispositivo y su operación original. La respuesta incluye `resultados[]` con `operacion_id`, `estado: aplicada | repetida | conflicto | rechazada | bloqueada`, `codigo_http`, `data?`, `error?`, y `referencias` con correspondencia local → servidor.

Cada operación tiene su propia transacción; el lote completo no es atómico. Si una dependencia falla, las dependientes quedan `bloqueada`, sin ejecutar. Un ciclo, IDs repetidos o lote mal formado se rechaza con `400` antes de aplicar operaciones. Un reintento puede incluir solo pendientes si sus dependencias ya fueron confirmadas y siguen identificables.

Sincronizar de nuevo la creación o confirmación no repite kilos ni puntos. Con una nueva clave para una corrección se exige versión actual y revisión del operador. Los conflictos conservan el trabajo local; no se modifica automáticamente la versión esperada para forzar éxito.

`GET /capacidades` anuncia máximo de operaciones por lote, ventana offline y retención de deduplicación; deben estar configurados antes de habilitar este módulo. Fuera de ventana: `OPERATION_TOO_OLD` por operación. El cliente muestra «pendiente de sincronizar» hasta recibir aceptación del servidor. Esos datos no cuentan en reportes oficiales antes de confirmar y sincronizar.

## 15. M12 · WhatsApp, capacidades y salud

| Método y ruta | Finalidad | Resultado |
| --- | --- | --- |
| `GET /webhook/whatsapp` | Verificación inicial del proveedor | Desafío validado según su protocolo; no usa envoltura JSON común |
| `POST /webhook/whatsapp` | Mensajes y estados de entrega | Acuse rápido según protocolo después de recepción durable |
| `GET /capacidades` | Contrato activo para clientes | Módulos habilitados, versión de contrato, límites de archivo/decimales/sync y política pública de registro |

El webhook valida firma, proveedor y destino; deduplica por proveedor e ID externo. Los campos concretos pertenecen al adaptador de Meta o al proveedor elegido, no se inventa aquí un payload común. Una firma inválida no puede crear solicitudes. El acuse de recepción no significa que la IA o la operación de negocio ya terminaron.

Los botones llaman directamente a los casos de uso. Texto libre, audio y foto pasan por interpretación y confirmación cuando corresponda. El estado conversacional separa registro, consentimiento, menú y revisión; no sustituye el estado de las órdenes. La notificación al residente se emite una vez sincronizada la acción, no al guardarla solo en la tablet.

Salud, fuera de `/v1`:

- `GET /health/live`: `200`, `{"status":"ok"}` si el proceso atiende.
- `GET /health/ready`: `200`, `{"status":"ready"}` si conecta a PostgreSQL; `503`, `{"status":"unavailable"}` si falla.

Detrás del proxy quedan `/api/health/live` y `/api/health/ready`. No muestran credenciales ni mensajes internos. Que falle IA o WhatsApp no obliga a declarar caída la API si el flujo manual y PostgreSQL están disponibles; las capacidades distinguen módulos habilitados de incidencias temporales.

## 16. Recorridos y criterios de aceptación

| Recorrido | Evidencia esperada al implementar |
| --- | --- |
| Registro y permisos | Residente sin contraseña de operador, consentimiento con versión; imposible adjudicarse otro hogar o rol |
| Solicitud mixta | Una solicitud y dos órdenes atómicas; el resultado de un gremio no cierra el otro ni revela sus datos al coordinador equivocado |
| Recolector sin cuenta | Coordinación asigna y registra el reporte verbal; conserva reasignaciones |
| Rechazo | Motivo obligatorio, cero puntos, aviso educativo reintentable sin duplicar efectos |
| Lote compartido | Varias órdenes, un solo total de kg; sin reparto ficticio por apartamento ni duplicación al consultar |
| Peso individual | Solo habilita incentivo por kg con unidad, medición confirmada y modalidad aprobada |
| Entrega directa | Sin orden ni recolector obligatorios; material anónimo aceptado sin inventar beneficiario |
| Baldes | Medio balde y equivalencia histórica reproducibles; actualización de conversión no cambia kg anteriores |
| Foto de tiquete | IA produce propuesta revisable; valores ilegibles no se convierten en ceros; no cuenta hasta confirmación |
| Puntos | Mismo hecho no se acredita dos veces por reintento, concurrencia o cambio de versión de regla |
| Corrección | Pesaje anterior preservado y excluido del total; reemplazo y efectos derivados trazables |
| Canje | Saldo e inventario protegidos frente a dos consumos concurrentes |
| Offline | Reintento sin duplicar; dependencia fallida bloquea confirmación; conflicto no sobrescribe cambios recientes |
| Liga y certificado | Fórmula y corte identificables, viviendas reales como denominador, sin datos personales públicos ni promesa automática de ahorro |

Estas comprobaciones se implementarán con el framework y las migraciones elegidos. Revisar este Markdown no equivale a haber ejecutado pruebas de una API todavía inexistente.

## 17. Decisiones abiertas y compatibilidad

| Decisión pendiente | Propuesta actual / condición para habilitar |
| --- | --- |
| Autenticación, recuperación y prueba de vínculo | Identidad verificada por canal y cuentas operadoras habilitadas; protocolo pendiente antes de datos reales |
| Titularidad de puntos | Personal; validar hogar/negocio antes de canjes |
| Reglas de incentivo | Versionadas; montos, acumulación y rachas por aprobar |
| Solicitudes abiertas duplicadas y recurrencia comercial | Regla configurable con control transaccional; excepciones por acordar |
| Cancelación, reapertura y resultado parcial | No habilitados en las rutas actuales; definir efecto en órdenes, avisos, puntos y reportes antes de ampliarlas |
| Reversión de beneficios ya gastados | Pendiente; bloquear el escenario que no tenga tratamiento aprobado |
| Denominador y desempate de Liga | Participación de hogares como base; regla explícita para cambios de viviendas y empate |
| Equivalencias y precios reales | Confirmar con huerta y Asorescatar; conservar versión aplicada |
| Offline y límites de decimales/archivos | Valores publicados y pruebas de campo antes de habilitar |
| Retención, eliminación y documentos | Acordar finalidad, plazos, responsables, respaldos y nueva emisión de certificados |
| Rutas fijas de negocios, Sello Verde y cosecha | Extensiones con contrato propio; no mezclar producción de cosecha con residuos recibidos |
| IA externa, mensajería y stack obligatorio | Confirmar reglamento; adaptadores reemplazables y flujo manual disponible |

Cambios respecto del contrato 0.1:

- `ubicacion_id` pasa a `unidad_id`; `equipo_id` pasa a `gremio_id`, alineados con el diseño. No se aceptan ambos nombres indistintamente.
- Los decimales se representan como strings; cambian también las entradas de registro, pesajes y filtros documentados.
- `POST /pesajes` crea borrador y exige confirmación posterior. El registro directo confirmado de la versión anterior queda reemplazado.
- Asignación y resultado requieren versión esperada y conservan historia. Las acciones siguen perteneciendo a una orden concreta, evitando ambigüedad en solicitudes mixtas.
- Se incorporan registro, consentimiento, incentivos, archivos/IA, educación, Liga, configuración y protocolo offline, con alcance y validaciones explícitos.

Al no existir una API implementada, este reemplazo no requiere mantener aliases de compatibilidad. Si ya hubiera consumidores externos, la adopción de estos cambios debe versionarse y coordinarse antes del despliegue. Los campos de respuesta opcionales podrán añadirse de forma compatible; los cambios de significado o de campos obligatorios se documentarán antes de implementarlos.

El equipo debe aprobar el núcleo y las reglas que se activen, actualizar este contrato y traducirlo a OpenAPI cuando se elija el framework. El objetivo es conservar una interfaz verificable para canales y paneles mientras el contexto de negocio termina de definirse.
