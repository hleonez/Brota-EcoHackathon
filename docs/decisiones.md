# Decisiones de infraestructura

## Confirmado

- PostgreSQL es la única tecnología de aplicación elegida.
- Imagen `postgres:18.7-bookworm`, versión concreta de PostgreSQL 18 publicada en
  el [catálogo oficial](https://hub.docker.com/_/postgres). Las actualizaciones
  serán cambios explícitos con respaldo y comprobación de restauración.
- Persistencia en `/var/lib/postgresql`, correspondiente a la imagen 18.
- Compose base sin puertos publicados; desarrollo añade únicamente localhost.
- `brota-dev` y `brota-server` separan redes y volúmenes por nombre de proyecto.
- El usuario inicial es administrador del clúster: `POSTGRES_USER` en la imagen
  oficial crea un superusuario. Al incorporar la API se creará un rol de ejecución
  restringido y un mecanismo de migraciones acorde con sus necesidades.
- Convenciones: carpetas y documentos en minúsculas, nombres nuevos con guiones,
  UTF-8 y LF; cada framework conservará sus convenciones internas.

## Alcance pendiente

Frameworks, esquema, autenticación, reglas de negocio, integraciones, colas,
almacenamiento de archivos, Dockerfiles y proxy HTTPS se definirán con el reto.
No se instalarán dependencias de aplicación antes de esa decisión.

## Datos que debe confirmar la Fundación

| Dato | Qué permite decidir |
| --- | --- |
| Sistema operativo y versión | Compatibilidad con Docker o alternativa de instalación |
| CPU, RAM, disco y arquitectura | Capacidad y compatibilidad de las futuras imágenes |
| Permisos y acceso SSH | Quién instala, despliega y opera |
| Docker Engine y Compose disponibles | Viabilidad del procedimiento de referencia |
| Disco persistente, espacio y política de respaldo | Ubicación, retención y recuperación de datos |
| Dominio, DNS y responsable de certificados | Proxy y HTTPS |
| Puertos entrantes, firewall y salida a internet | Acceso web, descarga de imágenes e integraciones |
| Redes privadas o VPN | Acceso a PostgreSQL desde una API externa |
| Responsable de operación y ventana de mantenimiento | Entrega, actualizaciones e incidentes |
| Destino de respaldo fuera del servidor | Recuperación ante pérdida del host |

Referencia provisional: Linux con Docker y Compose. Si Docker no está permitido,
se revisará la instalación nativa o un host autorizado con esos datos; todavía
no se declara compatibilidad con ese escenario. La aprobación del reglamento
para llevar infraestructura preparada también debe confirmarse con la organización.
