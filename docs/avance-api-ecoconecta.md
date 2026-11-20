# Estado de la API EcoConecta

Contrato: `0.3-ecoconecta.1`. Implementación en `feat/implementar-api-update`.

## Funciones implementadas

- Recicladores y huerteros diferenciados, cuentas vinculadas y acceso a asignaciones propias.
- Catálogo de huertas: GET/POST `/v1/huertas` y PATCH `/v1/huertas/{id}`. Cada huerta tiene ubicación y gremio. Crear un huertero requiere `huerta_id`; editarlo permite vincular registros históricos.
- Piloto por participante/unidad, con activación, revocación e intervalos `vigente_desde`/`vigente_hasta`. Crear solicitudes exige vínculo, consentimiento y habilitación vigente.
- Solicitudes nuevas exigen `preferencia_horaria` no vacía. Puede contener la elección explícita «Sin restricción». La preferencia no programa la visita.
- Asignación con horario exige `acuerdo_canal`: whatsapp, llamada o presencial. Sin horario queda asignada. POST `/v1/ordenes/{id}/programacion` exige inicio, fin y acuerdo; conserva historia y aviso al reprogramar.
- Cierre exige orden programada y `materiales_confirmados`: lista no vacía de UUID de materiales para recogida; lista vacía para rechazo. Registra trabajador ejecutor, operador registrador y asignación de origen.
- Puntos conservan cálculo, regla y versión por hecho. Los valores son propuestas del equipo sujetas a validación FSD.
- Contenidos por tema y publicación, reportes con estados completos y resumen que distingue canceladas, rechazadas y combinaciones finales.
- Sync incluye `programar_orden` y usa las mismas políticas y validaciones del servicio HTTP.
- Gemini desactivado: interpretar devuelve 503 sin llamar al proveedor. Catálogo y flujo guiado siguen disponibles.

## Migraciones

0005 distingue trabajadores; 0006 crea piloto; 0007 vincula cuentas; 0008 incorpora programación; 0009 conserva evidencias y cálculo; 0010 publica contenidos; 0011 añade huertas, vigencias, ejecutor, asignación y canal del acuerdo.

Las filas históricas conservan datos desconocidos como nulos. Para asignar huerteros antiguos, administración debe crear la huerta y vincularla mediante PATCH del trabajador. No se inventa pertenencia histórica. Los materiales confirmados se conservan como JSONB de UUID validados por servicio; el pesaje sigue siendo el origen de kilos y no se deducen kilos de esa lista.

## Integración de clientes

Bot y panel deben enviar los nuevos campos obligatorios y aceptar los estados `programada`, `cancelada`, `rechazada` y `finalizada_con_novedades` en sus proyecciones. Actualizar los clientes antes de desplegar este contrato. Las rutas históricas `/recolectores` se mantienen deprecadas para preservar referencias técnicas.

## Validación

17 pruebas locales de permisos y contratos aprobadas. SQL de toda la cadena 0001–0011 generado y sintaxis Python comprobada. Hay pruebas integradas para ambos recorridos oficiales y la suite anterior fue ajustada al contrato obligatorio.

La validación integrada está bloqueada por falta de conexión/configuración PostgreSQL en este entorno: `127.0.0.1:5432` agota el tiempo de espera. No se aplicaron migraciones a una base real ni se certificó la suite completa. Pendiente: ejecutar sobre PostgreSQL de pruebas, corregir cualquier fallo y verificar actualización de una copia de la base anterior. Nube y cambios de interfaz están fuera de esta implementación de backend.
