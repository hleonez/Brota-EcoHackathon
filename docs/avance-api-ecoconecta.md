# Avance de implementación de la API

## Fase 1: trabajadores y piloto

Implementados los catálogos diferenciados de recicladores y huerteros (0005), habilitación explícita por participante y unidad (0006), y cuentas vinculadas a trabajadores (0007).

Para crear una cuenta de trabajador, administración usa `POST /v1/cuentas-operadoras` con `trabajador_id` y un único permiso cuyo rol sea `reciclador` o `huertero` y cuyo `gremio_id` coincida con el trabajador. Conserva usuario/PIN y celular opcional. `/v1/me` devuelve el vínculo y las capacidades `mis_asignaciones` y `resultado`.

La cuenta consulta `/v1/ordenes` y `/v1/ordenes/{id}`, y cierra su asignación vigente por `/v1/ordenes/{id}/resultado`. No puede asignar ni consultar el directorio de unidades. Un trabajador inactivo no puede autenticarse. La coordinación mantiene el registro asistido.

Administración crea habilitaciones con `POST /v1/piloto/habilitaciones` (`participante_id`, `unidad_id`), las lista con GET y activa o revoca con PATCH `/{id}` (`version_esperada`, `activo`). El vínculo con la unidad debe existir. No hay habilitación automática ni masiva: después de migrar, autorizar expresamente a los participantes que deban crear solicitudes. El seguimiento de solicitudes anteriores se conserva.

Esta primera versión usa activación/revocación, sin fechas de caducidad. Las migraciones están preparadas, pendientes de validación integrada contra PostgreSQL y aplicación en el entorno de desarrollo. No aplicar a producción sin completar esa validación.

## Fases pendientes

2. Preferencia horaria, programación y reprogramación con trazabilidad.
3. Material confirmado al cierre y explicación de puntos.
4. Publicación de contenidos, reportes actualizados y validación completa de RN-01 a RN-08.

También queda pendiente retirar Gemini de la configuración de entrega o sustituirlo por un proveedor autorizado. Los clientes web y bot deben integrar las nuevas capacidades; este trabajo corresponde al backend.
