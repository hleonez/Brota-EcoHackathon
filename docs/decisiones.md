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

## Decisiones de la API (18-nov-2026)

Revisables si el reto impone otro stack el 20-nov; el dominio y el contrato se conservan.

- API en Python 3.12 + FastAPI, SQLAlchemy 2 (síncrono) + psycopg 3, migraciones Alembic,
  dependencias gestionadas con uv (`api/uv.lock`, `api/requirements.txt` para Docker).
- El bot de WhatsApp es un servicio separado: recibe el webhook del proveedor y llama a la API
  con `BOT_SERVICE_TOKEN` + `X-Canal-Celular`. El estado conversacional vive en el bot.
- Avisos al residente con bandeja de salida (`evento_salida`) en la misma transacción del hecho;
  entrega al bot por reserva (pull) o webhook firmado HMAC-SHA256 (push).
- Operadores con usuario + PIN (scrypt) y JWT HS256; permisos por gremio en la base.
- Idempotencia por actor + ruta + clave, en la misma transacción de la escritura (72 h).
- Puntos: libro inmutable con clave única por hecho; reglas versionadas (+10 entrega válida,
  +15 entrega directa) como propuesta pendiente de validar con la Fundación.
- La semilla usa valores de ejemplo (5 torres × 110 viviendas, precios, 8 kg por balde).

## Alcance pendiente

Rol de base de datos restringido para la API, archivos e IA, canjes, exportaciones,
certificados, colas externas y proxy HTTPS se definirán con el reto.

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
