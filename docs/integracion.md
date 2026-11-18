# Integrar API y paneles

Para rutas, entradas y respuestas del primer recorrido propuesto, consulta el
[contrato inicial de API](contrato-api.md). Esta guía cubre su integración técnica.

## Contrato mínimo

Cada aplicación tendrá una imagen con comando de inicio propio, puerto configurable,
escucha en `0.0.0.0`, registros por stdout/stderr y cierre ordenado ante SIGTERM.
Su Dockerfile y dependencias se incorporarán al confirmar el framework. No fijar
`container_name`: permite varias instalaciones sin colisiones.

La API expondrá `GET /health/live` (200 cuando el proceso atiende) y
`GET /health/ready` (200 con conexión a PostgreSQL, 503 si todavía no está lista).
No incluir detalles de credenciales ni errores internos en esas respuestas.
La aplicación reintentará conexiones transitorias: el healthcheck inicial no
resuelve caídas de la base durante la operación.

## Conexión a datos

`infra/env/app.env.example` describe el contrato de la futura API:

| Variable | Desde el equipo | Dentro de Compose | PostgreSQL externo |
| --- | --- | --- | --- |
| `DB_HOST` | `127.0.0.1` | `db` | Host del proveedor o red privada |
| `DB_PORT` | `DB_LOCAL_PORT` | `5432` | Puerto del destino |
| `DB_NAME` | Nombre configurado | Nombre configurado | Nombre del destino |
| `DB_USER` | Usuario autorizado | Rol de aplicación futuro | Rol del destino |
| `DB_PASSWORD` | Secreto local | Secreto inyectado al proceso | Secreto del destino |
| `DB_SSLMODE` | `disable` local | `disable` en red Docker del mismo host | `verify-full` con CA confiable |

Estas variables se adaptarán al controlador elegido. `DB_PASSWORD_FILE` es la ruta
que usa **Compose** para montar el secreto; no sustituye automáticamente
`DB_PASSWORD` en una API. La API deberá leer el secreto montado o recibir la
contraseña mediante el mecanismo del servicio de despliegue. No copiarla al código.
El usuario administrador inicial se reserva para operación; crear el rol limitado
cuando se conozcan permisos y migraciones. No conectar el navegador a PostgreSQL.

## Servidor único

Añadir un archivo Compose de aplicaciones una vez que existan imágenes reales.
Ejemplo orientativo (no es un archivo ejecutable de la base actual):

```yaml
services:
  api:
    image: ${API_IMAGE:?Specify an existing image and version}
    environment:
      PORT: "8000"
      DB_HOST: db
      DB_PORT: "5432"
      DB_NAME: ${DB_NAME}
      DB_USER: ${APP_DB_USER}
      DB_SSLMODE: disable
      # The future API must implement reading this file.
      DB_PASSWORD_FILE: /run/secrets/app_db_password
    secrets:
      - app_db_password
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
  panel:
    image: ${PANEL_IMAGE:?Specify an existing image and version}
    restart: unless-stopped
secrets:
  app_db_password:
    file: ${APP_DB_PASSWORD_FILE:?Specify the application's secret}
```

El proxy futuro publicará solo HTTP/HTTPS, enviará `/api` a la API y el resto al
panel. Se conservará el prefijo `/api` y la API se configurará para servir bajo él.
Los contenedores internos no necesitan publicar puertos del host. Cada panel
adicional tendrá servicio y ruta o subdominio propios, definidos al conocer el reto.

Una web estática puede necesitar la URL pública de API durante su compilación:
documentar si cada framework la consume en compilación o en ejecución. Para el
servidor único se recomienda `/api`, que evita incorporar un dominio al bundle.

## Servicios separados

Construir y desplegar cada imagen de aplicación por separado; configurar conexión
a PostgreSQL y URL pública de API en el destino. Si se utiliza PostgreSQL gestionado,
no levantar el servicio `db` de este repositorio en ese entorno.

El navegador deberá usar una URL HTTPS de API resoluble públicamente. Configurar
CORS con los orígenes exactos de los paneles. El hostname Docker `db` solo funciona
dentro de su red Compose. Para conectar una API externa con la base de la Fundación,
confirmar VPN/red privada y TLS antes de habilitar el acceso; la configuración
actual no publica PostgreSQL. Las variables públicas del frontend no contendrán
contraseñas ni claves privadas.

Cambiar de destino exige trasladar los datos por respaldo/restauración; no basta
con modificar variables. Consulta [operación](operacion.md).
