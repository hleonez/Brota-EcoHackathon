# Modelo de datos · Brota (PostgreSQL)

Generado desde `api/app/models.py` (SQLAlchemy) con las migraciones hasta la **0014**. Para el detalle de
reglas, estados y decisiones, ver [diseno-base-de-datos.md](diseno-base-de-datos.md).

**44 tablas** agrupadas por dominio. `PK` llave primaria, `FK` llave foránea.

## Territorio y unidades

```mermaid
erDiagram
  conjunto {
    uuid id PK
    text nombre
    text etapa
    bool activo
    timestamptz created_at
  }
  torre {
    uuid id PK
    uuid conjunto_id FK
    text codigo
    text nombre
    bool activo
    timestamptz created_at
  }
  capacidad_torre {
    uuid id PK
    uuid torre_id FK
    int numero_viviendas
    timestamptz vigente_desde
    timestamptz vigente_hasta
    timestamptz created_at
  }
  unidad {
    uuid id PK
    text tipo
    uuid torre_id FK
    text referencia_local
    text direccion_referencia
    bool activo
    timestamptz created_at
  }
  huerta {
    uuid id PK
    text nombre
    uuid gremio_id FK
    text ubicacion
    bool activo
    int version
    timestamptz created_at
  }
  conjunto ||--o{ torre : "conjunto_id"
  torre ||--o{ capacidad_torre : "torre_id"
  torre |o--o{ unidad : "torre_id"
```

## Personas, consentimiento y piloto

```mermaid
erDiagram
  participante {
    uuid id PK
    text nombre
    text celular_normalizado
    text estado
    timestamptz created_at
    timestamptz updated_at
  }
  vinculo_unidad {
    uuid id PK
    uuid participante_id FK
    uuid unidad_id FK
    text tipo_vinculo
    timestamptz vigente_desde
    timestamptz vigente_hasta
  }
  consentimiento {
    uuid id PK
    uuid participante_id FK
    text version_politica
    text decision
    text canal
    text referencia_evidencia
    timestamptz registrado_at
  }
  solicitud_eliminacion {
    uuid id PK
    uuid participante_id FK
    text estado
    text observacion
    timestamptz created_at
  }
  habilitacion_piloto {
    timestamptz vigente_desde
    timestamptz vigente_hasta
    timestamptz revocada_at
    uuid id PK
    uuid participante_id FK
    uuid unidad_id FK
    bool activo
    uuid habilitada_por FK
    int version
    timestamptz created_at
  }
  participante ||--o{ consentimiento : "participante_id"
  participante ||--o{ solicitud_eliminacion : "participante_id"
  participante ||--o{ vinculo_unidad : "participante_id"
  participante ||--o{ habilitacion_piloto : "participante_id"
```

## Operación y permisos

```mermaid
erDiagram
  gremio {
    uuid id PK
    text codigo
    text nombre
    bool activo
  }
  cuenta_operadora {
    uuid trabajador_id FK
    uuid id PK
    text nombre
    text usuario
    text celular_normalizado
    text pin_hash
    text referencia_autenticacion
    bool activo
    int version
    timestamptz created_at
  }
  permiso_operador {
    uuid id PK
    uuid cuenta_id FK
    text rol
    uuid gremio_id FK
  }
  recolector {
    uuid huerta_id FK
    text tipo
    uuid id PK
    uuid gremio_id FK
    text nombre
    text telefono_contacto
    bool activo
    int version
    timestamptz created_at
  }
  tipo_servicio {
    uuid id PK
    text codigo
    text nombre
    uuid gremio_id FK
    bool activo
  }
  punto_recepcion {
    uuid id PK
    text codigo
    text nombre
    uuid gremio_id FK
    bool activo
  }
  gremio ||--o{ punto_recepcion : "gremio_id"
  gremio ||--o{ tipo_servicio : "gremio_id"
  gremio ||--o{ recolector : "gremio_id"
  recolector |o--o| cuenta_operadora : "trabajador_id"
  cuenta_operadora ||--o{ permiso_operador : "cuenta_id"
  gremio |o--o{ permiso_operador : "gremio_id"
```

## Solicitud, orden y cierre

```mermaid
erDiagram
  solicitud {
    text preferencia_horaria
    timestamptz preferencia_inicio
    timestamptz preferencia_fin
    bool preferencia_sin_restriccion
    text tipo_generador
    uuid id PK
    text codigo_pasaporte
    uuid unidad_id FK
    uuid participante_id FK
    text canal_origen
    text observacion
    text ubicacion_operativa
    int version
    timestamptz created_at
  }
  solicitud_servicio {
    uuid solicitud_id PK
    uuid tipo_servicio_id PK
    uuid orden_id FK
  }
  solicitud_residuo {
    uuid solicitud_id PK
    uuid residuo_id PK
    uuid orden_id FK
    text estado
    text cantidad
    jsonb respuestas
    text fuente
  }
  residuo {
    uuid id PK
    text codigo
    text nombre
    text emoji
    text categoria
    text acepta
    uuid gremio_id FK
    jsonb sinonimos
    text preparacion
    text evitar
    text alternativa
    jsonb verificaciones
    bool en_menu
    int orden
    bool activo
    int version
    timestamptz created_at
  }
  orden {
    uuid id PK
    uuid solicitud_id FK
    uuid gremio_id FK
    text estado
    int version
    timestamptz created_at
    timestamptz updated_at
  }
  asignacion {
    text acuerdo_canal
    text acuerdo_observacion
    uuid programada_por FK
    uuid id PK
    uuid orden_id FK
    uuid recolector_id FK
    timestamptz inicio
    timestamptz fin
    text forma_aviso
    uuid registrada_por FK
    timestamptz vigente_desde
    timestamptz vigente_hasta
  }
  resultado_orden {
    uuid trabajador_id FK
    uuid asignacion_id FK
    jsonb materiales_confirmados
    uuid id PK
    uuid orden_id FK
    text resultado
    uuid motivo_rechazo_id FK
    text observacion
    uuid confirmado_por FK
    timestamptz ocurrido_at
    timestamptz confirmado_at
  }
  resultado_material {
    uuid resultado_orden_id PK
    uuid material_id PK
  }
  motivo_rechazo {
    uuid id PK
    text codigo
    text nombre
    uuid gremio_id FK
    bool activo
  }
  solicitud ||--o{ orden : "solicitud_id"
  orden ||--o{ asignacion : "orden_id"
  residuo ||--o{ solicitud_residuo : "residuo_id"
  orden ||--o{ solicitud_residuo : "orden_id"
  solicitud ||--o{ solicitud_residuo : "solicitud_id"
  solicitud ||--o{ solicitud_servicio : "solicitud_id"
  orden ||--o{ solicitud_servicio : "orden_id"
  asignacion |o--o{ resultado_orden : "asignacion_id"
  motivo_rechazo |o--o{ resultado_orden : "motivo_rechazo_id"
  orden ||--o| resultado_orden : "orden_id"
  resultado_orden ||--o{ resultado_material : "resultado_orden_id"
```

## Material, pesaje y valor

```mermaid
erDiagram
  material {
    uuid id PK
    text codigo
    text nombre
    uuid gremio_id FK
    bool activo
    int version
  }
  pesaje {
    uuid id PK
    text codigo
    uuid gremio_id FK
    uuid recolector_id FK
    text proveedor_referencia
    timestamptz fecha_medicion
    text origen_captura
    text estado
    text numero_tiquete
    text emisor_tiquete
    uuid torre_origen_id FK
    uuid unidad_medida_id FK
    text observacion
    uuid creado_por FK
    uuid confirmado_por FK
    timestamptz confirmado_at
    uuid sustituye_pesaje_id FK
    text motivo_correccion
    int version
    timestamptz created_at
    timestamptz updated_at
  }
  linea_pesaje {
    uuid id PK
    uuid pesaje_id FK
    uuid material_id FK
    text metodo_medicion
    numeric kg_aceptados
    numeric kg_rechazados
    uuid motivo_rechazo_id FK
    numeric cantidad_aceptada
    numeric cantidad_rechazada
    uuid version_equivalencia_id FK
    numeric precio_kg_aplicado
    uuid version_precio_id FK
  }
  pesaje_orden {
    uuid pesaje_id PK
    uuid orden_id PK
  }
  entrega_directa {
    uuid id PK
    uuid pesaje_id FK
    uuid punto_recepcion_id FK
    uuid unidad_id FK
    uuid participante_id FK
    uuid recibida_por FK
    timestamptz created_at
  }
  version_precio_material {
    uuid id PK
    uuid material_id FK
    numeric precio_kg
    text moneda
    timestamptz vigente_desde
    timestamptz vigente_hasta
    timestamptz created_at
  }
  version_equivalencia {
    uuid id PK
    uuid gremio_id FK
    uuid punto_recepcion_id FK
    text recipiente
    numeric kg_por_unidad
    timestamptz vigente_desde
    timestamptz vigente_hasta
    timestamptz created_at
  }
  material ||--o{ version_precio_material : "material_id"
  pesaje |o--o{ pesaje : "sustituye_pesaje_id"
  pesaje ||--o| entrega_directa : "pesaje_id"
  material ||--o{ linea_pesaje : "material_id"
  pesaje ||--o{ linea_pesaje : "pesaje_id"
  version_precio_material |o--o{ linea_pesaje : "version_precio_id"
  version_equivalencia |o--o{ linea_pesaje : "version_equivalencia_id"
  pesaje ||--o{ pesaje_orden : "pesaje_id"
```

## Puntos y educación

```mermaid
erDiagram
  version_regla_incentivo {
    uuid id PK
    text codigo
    text modalidad
    text ambito_tipo
    uuid ambito_id
    jsonb parametros
    timestamptz vigente_desde
    timestamptz vigente_hasta
    text aprobada_por
    timestamptz created_at
  }
  movimiento_puntos {
    jsonb detalle_calculo
    uuid id PK
    uuid participante_id FK
    uuid unidad_id FK
    uuid torre_id FK
    numeric delta
    text tipo
    uuid version_regla_id FK
    uuid resultado_orden_id FK
    uuid entrega_directa_id FK
    uuid pesaje_id FK
    uuid revierte_movimiento_id FK
    text clave_aplicacion
    timestamptz ocurrido_at
    timestamptz created_at
  }
  contenido_educativo {
    text tema
    bool publicado
    int version
    uuid gremio_id FK
    timestamptz vigente_desde
    timestamptz vigente_hasta
    uuid id PK
    text titulo
    text tipo
    text recurso
    text texto
    bool general
    bool activo
    timestamptz created_at
  }
  contenido_motivo {
    uuid contenido_id PK
    uuid motivo_rechazo_id PK
  }
  contenido_material {
    uuid contenido_id PK
    uuid material_id PK
  }
  contenido_educativo ||--o{ contenido_material : "contenido_id"
  contenido_educativo ||--o{ contenido_motivo : "contenido_id"
  movimiento_puntos |o--o{ movimiento_puntos : "revierte_movimiento_id"
  version_regla_incentivo |o--o{ movimiento_puntos : "version_regla_id"
```

## Comunicación, auditoría y operación

```mermaid
erDiagram
  caso {
    uuid id PK
    text codigo
    text tipo
    text estado
    text texto
    text canal
    uuid participante_id FK
    uuid solicitud_id FK
    uuid gremio_id FK
    text respuesta
    uuid atendido_por FK
    timestamptz atendido_at
    int version
    timestamptz created_at
  }
  evento_salida {
    uuid id PK
    text tipo
    uuid participante_id FK
    uuid cuenta_operadora_id FK
    uuid solicitud_id FK
    uuid orden_id FK
    jsonb datos
    text estado
    int intentos
    timestamptz proximo_intento_at
    text id_externo
    text ultimo_error
    timestamptz enviado_at
    timestamptz created_at
    timestamptz updated_at
  }
  evento_dominio {
    uuid id PK
    text tipo
    uuid solicitud_id FK
    uuid orden_id FK
    uuid pesaje_id FK
    text actor_tipo
    uuid actor_id
    jsonb datos
    timestamptz ocurrido_at
  }
  mensaje_conversacion {
    uuid id PK
    text celular_normalizado
    uuid participante_id FK
    text direccion
    text tipo
    text texto
    text wamid
    timestamptz created_at
  }
  parametro_programa {
    text clave PK
    text valor
    timestamptz updated_at
    uuid actualizado_por FK
  }
  operacion_idempotente {
    uuid id PK
    text actor
    text ruta
    text clave
    text huella
    text estado
    int codigo_http
    jsonb respuesta
    timestamptz created_at
    timestamptz expira_at
  }
  referencia_local {
    text actor PK
    text referencia_local PK
    text recurso_tipo
    uuid recurso_id
    timestamptz created_at
  }
```

## Relaciones entre dominios

| Desde | Campo | Hacia |
|---|---|---|
| `contenido_educativo` | `gremio_id` | `gremio` |
| `huerta` | `gremio_id` | `gremio` |
| `material` | `gremio_id` | `gremio` |
| `mensaje_conversacion` | `participante_id` | `participante` |
| `motivo_rechazo` | `gremio_id` | `gremio` |
| `residuo` | `gremio_id` | `gremio` |
| `contenido_material` | `material_id` | `material` |
| `contenido_motivo` | `motivo_rechazo_id` | `motivo_rechazo` |
| `recolector` | `huerta_id` | `huerta` |
| `version_equivalencia` | `punto_recepcion_id` | `punto_recepcion` |
| `version_equivalencia` | `gremio_id` | `gremio` |
| `solicitud` | `unidad_id` | `unidad` |
| `solicitud` | `participante_id` | `participante` |
| `vinculo_unidad` | `unidad_id` | `unidad` |
| `caso` | `solicitud_id` | `solicitud` |
| `caso` | `participante_id` | `participante` |
| `caso` | `gremio_id` | `gremio` |
| `caso` | `atendido_por` | `cuenta_operadora` |
| `habilitacion_piloto` | `habilitada_por` | `cuenta_operadora` |
| `habilitacion_piloto` | `unidad_id` | `unidad` |
| `orden` | `gremio_id` | `gremio` |
| `parametro_programa` | `actualizado_por` | `cuenta_operadora` |
| `pesaje` | `recolector_id` | `recolector` |
| `pesaje` | `gremio_id` | `gremio` |
| `pesaje` | `confirmado_por` | `cuenta_operadora` |
| `pesaje` | `creado_por` | `cuenta_operadora` |
| `pesaje` | `unidad_medida_id` | `unidad` |
| `pesaje` | `torre_origen_id` | `torre` |
| `asignacion` | `recolector_id` | `recolector` |
| `asignacion` | `programada_por` | `cuenta_operadora` |
| `asignacion` | `registrada_por` | `cuenta_operadora` |
| `entrega_directa` | `punto_recepcion_id` | `punto_recepcion` |
| `entrega_directa` | `recibida_por` | `cuenta_operadora` |
| `entrega_directa` | `participante_id` | `participante` |
| `entrega_directa` | `unidad_id` | `unidad` |
| `evento_dominio` | `orden_id` | `orden` |
| `evento_dominio` | `solicitud_id` | `solicitud` |
| `evento_dominio` | `pesaje_id` | `pesaje` |
| `evento_salida` | `orden_id` | `orden` |
| `evento_salida` | `solicitud_id` | `solicitud` |
| `evento_salida` | `cuenta_operadora_id` | `cuenta_operadora` |
| `evento_salida` | `participante_id` | `participante` |
| `linea_pesaje` | `motivo_rechazo_id` | `motivo_rechazo` |
| `pesaje_orden` | `orden_id` | `orden` |
| `solicitud_servicio` | `tipo_servicio_id` | `tipo_servicio` |
| `resultado_orden` | `trabajador_id` | `recolector` |
| `resultado_orden` | `confirmado_por` | `cuenta_operadora` |
| `movimiento_puntos` | `pesaje_id` | `pesaje` |
| `movimiento_puntos` | `entrega_directa_id` | `entrega_directa` |
| `movimiento_puntos` | `resultado_orden_id` | `resultado_orden` |
| `movimiento_puntos` | `unidad_id` | `unidad` |
| `movimiento_puntos` | `participante_id` | `participante` |
| `movimiento_puntos` | `torre_id` | `torre` |
| `resultado_material` | `material_id` | `material` |

## Reglas que protege la base

- **RN-01 separación de flujos:** cada `solicitud_servicio` apunta a un `tipo_servicio` de un `gremio`; cada `orden` pertenece a un solo gremio.
- **RN-02 programación:** la API solo pasa una `orden` a `programada` con `POST /v1/ordenes/{id}/programacion`, que exige día, hora y persona; `asignacion` guarda `inicio`/`fin` con CHECK de horario completo y ordenado.
- **RN-03 asignación:** `asignacion` une la orden con el `recolector` y la cuenta que asignó.
- **RN-04 trazabilidad:** identificador (`codigo_pasaporte`), estado y `evento_dominio` por cada cambio.
- **RN-05 cierre / RN-06 puntos:** cada `movimiento_puntos` apunta al `resultado_orden` o `pesaje` que lo originó, a la `version_regla_incentivo` usada y guarda `detalle_calculo`; la API solo abona al registrar la recolección.
- **RN-07 privacidad:** el celular vive en `participante` y solo se expone a quien atiende; `mensaje_conversacion` se borra a los 30 días.
- **RN-08 piloto:** `habilitacion_piloto` por persona y unidad, con vigencia; nadie queda habilitado por defecto.
