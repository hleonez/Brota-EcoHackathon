# Contrato inicial de API · Brota

Estado: **borrador 0.1 para acordar con el equipo**. Describe una primera versión
funcional del servicio; no implementa endpoints ni define tablas o un framework.
Las decisiones de negocio que siguen son propuestas revisables con el reto.

## 1. Objetivo y recorrido inicial

Una API compartida para registrar una solicitud, mostrarla a coordinación,
asignar su atención, confirmar el resultado y registrar el material recibido.
El panel de la Fundación consulta información del mismo servicio.

Recorrido propuesto:

```text
Solicitud → orden por equipo → asignación → resultado de recogida
                                               ↓
                                   pesaje del material recibido
                                               ↓
                                      resumen para paneles
```

Separar los conceptos permite cambiar canales y pantallas sin rehacer la API:

| Concepto | Significado propuesto |
| --- | --- |
| Ubicación | Referencia conocida de hogar, negocio o punto; su estructura se definirá con el reto |
| Solicitud | Una petición de atención asociada a una ubicación |
| Orden | Trabajo para un equipo dentro de una solicitud |
| Recolector | Persona que atiende la orden; no implica una cuenta de usuario |
| Pesaje | Registro confirmado de kilos recibidos, por material |
| Catálogo | Equipos, tipos de servicio, materiales y motivos disponibles |

No se fija un recurso genérico de «usuarios» que mezcle residentes, recolectores
y operadores. Identidad, registro, consentimiento y permisos necesitan validación
antes de definir sus operaciones.

## 2. Convenciones técnicas

- HTTP y JSON UTF-8; cuerpos con `Content-Type: application/json`.
- Desarrollo: `http://localhost:8000/v1`. Servidor con proxy: `/api/v1`.
  `/api` es el prefijo de despliegue; `/v1` es la versión del contrato.
- Salud fuera de la versión: `/health/live` y `/health/ready` en desarrollo;
  `/api/health/live` y `/api/health/ready` detrás del proxy.
- IDs opacos de tipo string: el cliente no interpreta su formato ni genera IDs
  de entidades del servidor. Los ejemplos usan identificadores ficticios.
- Campos JSON en `snake_case`. Fechas de auditoría ISO 8601 en UTC, con `Z`.
  Los horarios enviados incluirán zona u offset; los paneles los mostrarán en hora local.
- Respuesta individual: `{"data": {...}}`. Listas: `{"data": [], "pagination":
  {"limit": 20, "offset": 0, "has_more": false}}`.
- Listas con `limit` por defecto 20, máximo 100, y `offset` desde 0.
  Orden por `created_at` descendente, desempate por `id` descendente.
- `201` al crear, `200` al consultar o ejecutar una acción, `400` para JSON o
  parámetros inválidos, `404` si no existe el recurso, `409` para conflictos de
  estado y `422` para campos que incumplen el contrato. `503` para indisponibilidad.
- Error común: `{"error":{"code":"VALIDATION_ERROR","message":"Revisa los
  campos enviados","fields":{"ubicacion_id":"Campo obligatorio"}}}`.
  `fields` es opcional; `code` es estable y `message` puede cambiar.
- El cliente enviará únicamente campos documentados. Los nuevos campos de
  respuesta opcionales serán compatibles; los clientes ignorarán campos desconocidos.
  Los cambios incompatibles se acordarán en el contrato antes de implementarlos.

Autenticación pendiente de acordar: no se prescribe JWT, sesiones ni proveedor.
Los endpoints operativos y reportes requerirán autorización del lado servidor;
`401` indicará falta de autenticación y `403` falta de permiso. Ocultar un botón
en el panel no autoriza una operación. El mecanismo y las capacidades por actor
deberán cerrarse antes de exponer datos reales fuera del entorno de desarrollo.

## 3. Endpoints del primer recorrido

Las rutas de la tabla son relativas a `/v1`. Los campos marcados con `?` son
opcionales; si no se indica otro valor, se omiten al no tener información.
Todos los recursos incluyen `id` y `created_at` en sus respuestas.

| Método y ruta | Entrada o filtros | Respuesta |
| --- | --- | --- |
| `GET /catalogos` | Sin filtros | Catálogos vigentes para construir selectores |
| `POST /solicitudes` | `ubicacion_id`, `tipo_servicio_ids[]`, `observacion?` | Solicitud y órdenes creadas, `201` |
| `GET /solicitudes` | `ubicacion_id?`, paginación | Lista de solicitudes con sus órdenes |
| `GET /solicitudes/{id}` | ID | Solicitud con sus órdenes |
| `GET /ordenes` | `equipo_id?`, `estado?`, `recolector_id?`, paginación | Bandeja de órdenes |
| `POST /ordenes/{id}/asignacion` | `recolector_id`, `inicio?`, `fin?` | Orden actualizada |
| `POST /ordenes/{id}/resultado` | `resultado`, `motivo_id?`, `observacion?` | Orden actualizada |
| `POST /pesajes` | Datos de pesaje descritos abajo | Pesaje confirmado, `201` |
| `GET /pesajes` | `recolector_id?`, `desde?`, `hasta?`, paginación | Lista de pesajes |
| `GET /reportes/resumen` | `desde`, `hasta`, `equipo_id?` | Conteos de órdenes y kilos por material |

### Catálogos

`GET /catalogos` devuelve `data` con arrays `tipos_servicio`, `equipos`,
`recolectores`, `materiales` y `motivos_rechazo`. Cada entrada incluye `id`,
`nombre` y `activo`. Los tipos de servicio, recolectores y materiales incluyen
`equipo_id`. Los tipos representan atención por un solo equipo; seleccionar
varios permite una solicitud mixta. La configuración de los catálogos se resolverá
al implementar; no se propone todavía un CRUD de administración.

Los IDs de ubicación vendrán de datos de demostración o del futuro flujo de
registro. Este borrador no ofrece un directorio público de hogares o teléfonos.

### Solicitudes y órdenes

Crear una solicitud acepta uno o más tipos de servicio activos, sin duplicados.
El servidor crea una orden por equipo distinto y devuelve todo en una operación
atómica. Un tipo inexistente o inactivo produce `422`, sin creación parcial.
El origen se deriva del adaptador que recibe la petición, no de un campo usado
para conceder permisos. WhatsApp o una web podrán invocar el mismo caso de uso.

Ejemplo de creación:

```http
POST /v1/solicitudes
Content-Type: application/json
Idempotency-Key: 7621d141-dc53-42c3-b740-b19fb7d68f59
```

```json
{
  "ubicacion_id": "ubicacion-demo-1",
  "tipo_servicio_ids": ["reciclables", "organicos"],
  "observacion": "Hay cartón y restos de cocina"
}
```

```json
{
  "data": {
    "id": "solicitud-demo-1",
    "created_at": "2026-11-20T15:00:00Z",
    "ubicacion_id": "ubicacion-demo-1",
    "tipo_servicio_ids": ["reciclables", "organicos"],
    "observacion": "Hay cartón y restos de cocina",
    "ordenes": [
      {
        "id": "orden-demo-1",
        "created_at": "2026-11-20T15:00:00Z",
        "solicitud_id": "solicitud-demo-1",
        "equipo_id": "equipo-reciclaje",
        "estado": "nueva"
      },
      {
        "id": "orden-demo-2",
        "created_at": "2026-11-20T15:00:00Z",
        "solicitud_id": "solicitud-demo-1",
        "equipo_id": "equipo-huerta",
        "estado": "nueva"
      }
    ]
  }
}
```

Estados propuestos de **orden**, no de la solicitud completa:

```text
nueva → asignada → recogida
                ↘ rechazada
```

La asignación exige un recolector activo del equipo de la orden. Se puede
reasignar mientras esté `asignada`; se reemplaza la asignación vigente. Si se
indica horario, se envían ambos extremos y `fin` debe ser posterior a `inicio`.
La orden devuelve `asignacion` con esos datos.

El resultado solo se registra desde `asignada`: `resultado` será `recogida` o
`rechazada` y se convierte en su estado final. El rechazo requiere un motivo
activo. Se devuelve además `resultado` con `motivo_id?` y `observacion?`.
Modificar una orden finalizada produce `409`; correcciones, cancelación y rechazo
parcial se acordarán si el reto los requiere. La solicitud conserva sus órdenes
para que un resultado de reciclaje no cierre indebidamente el de orgánicos.

### Pesajes

`POST /pesajes` recibe `recolector_id`, `orden_ids` (array, puede estar vacío),
`fecha` (instante con zona), `lineas` y `observacion?`. Cada línea contiene
`material_id`, `kg_aceptados`, `kg_rechazados` y `motivo_id?`.

Los kilos son números finitos no negativos; una línea debe tener algún peso
mayor que cero. No se repiten materiales. Si hay kilos rechazados, se exige
motivo. Debe existir al menos una línea. Materiales y recolector pertenecen al
mismo equipo. Las órdenes vinculadas deben estar `recogida`, corresponder a ese
equipo y tener asignado ese recolector. IDs duplicados o inconsistentes dan `422`.

Un registro puede representar un lote de varias órdenes, o material sin órdenes
individualizadas (`orden_ids: []`). **Vincular órdenes no reparte los kilos entre
ellas**. La API no atribuye peso a un apartamento sin una medición individual.
Para esa atribución, el equipo deberá confirmar un contrato adicional de pesaje
individual. Registrar kilos no cambia automáticamente el estado de las órdenes.
La respuesta devuelve los datos aceptados, su ID y fecha de creación.

El registro de esta versión es manual y confirmado por el operador autorizado.
La futura lectura por IA producirá un borrador para revisión, no un pesaje
confirmado. Edición y ajustes de pesajes quedan pendientes de definir.

### Resumen

`desde` es inclusivo y `hasta` exclusivo, ambos instantes con zona. Se exige
`desde < hasta`. Para órdenes se filtra por `created_at`; para pesajes, por `fecha`.
La respuesta incluye `periodo`, `ordenes_por_estado` (todos los estados, incluso
con cero) y `materiales` con `material_id`, `kg_aceptados` y `kg_rechazados`.
Sin registros devuelve ceros y un array de materiales vacío. No calcula puntos,
ingresos ni rankings; tampoco suma peso por hogar a partir de lotes.

## 4. Reintentos y errores

Los POST de creación y acciones exigirán `Idempotency-Key` (string único generado
por el cliente para cada operación lógica). Reutilizarlo en un reintento devuelve
el mismo código y cuerpo exitoso, sin repetir la escritura. La clave se delimita
por actor autenticado y ruta; cambiar el cuerpo con la misma clave produce `409`.
Sin clave se responde `400`. Las escrituras y el registro de la clave serán
atómicos; se conservarán al menos 24 horas. Los errores de validación no consumen
la clave. Esto evita duplicar pesajes por doble clic o pérdida de una respuesta;
no constituye un protocolo de sincronización offline.

El cliente conserva el formulario ante error de red y reintenta con la misma
clave. No muestra éxito antes de recibir confirmación. Los `409` requieren
recargar el recurso para que el operador revise su estado actual.

## 5. Salud y criterios para implementar

- `GET /health/live`: `200`, `{"status":"ok"}` si el proceso atiende.
- `GET /health/ready`: `200`, `{"status":"ready"}` si conecta a PostgreSQL;
  `503`, `{"status":"unavailable"}` si no está disponible. Sin detalles internos.

Al implementar, comprobar el recorrido mixto, filtros y paginación, reasignación,
rechazo con motivo, transición inválida, registro de lote sin atribución de kilos,
resumen sin datos, límites del periodo y reintentos sin duplicación. Verificar
también que un operador sin permisos no pueda consultar o modificar recursos de
otro ámbito. Las pruebas vivirán con la aplicación y su framework elegido.

## 6. Qué confirmar con el contexto del reto

Antes de implementar el dominio, validar ubicación e identidad, actores y permisos,
catálogos reales, estados finales y correcciones, solicitud mixta y pesajes por
lote. Si cambian, actualizar primero este documento y sus ejemplos con el equipo.

WhatsApp, IA, incentivos, canjes, educación, archivos, certificados y offline no
forman parte del primer recorrido. Se añadirán mediante contratos propios cuando
se prioricen. Los paneles dependerán de esta interfaz, no del framework ni de las
tablas internas. Después de aprobarla se podrá traducir a OpenAPI para generar
documentación y facilitar mocks, sin mantener dos contratos distintos a mano.
