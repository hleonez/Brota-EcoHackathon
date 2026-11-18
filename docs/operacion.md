# Operación en Linux y traslado

## Primer despliegue en el servidor

Desde la raíz del repositorio clonado, con Docker Engine y Compose v2 disponibles:

```bash
cp -n infra/env/server.env.example infra/env/server.env
(umask 077; set -o noclobber; openssl rand -base64 32 > infra/secrets/server-db-password.txt)
docker compose --env-file infra/env/server.env -f infra/compose.yaml -f infra/compose.server.yaml config --quiet
docker compose --env-file infra/env/server.env -f infra/compose.yaml -f infra/compose.server.yaml pull
docker compose --env-file infra/env/server.env -f infra/compose.yaml -f infra/compose.server.yaml up -d --wait --wait-timeout 120
```

No repetir la generación del secreto sobre una instalación existente. Las rutas
relativas del secreto se resuelven desde `infra/compose.yaml`, no desde el archivo
de entorno. Los ejemplos asignan `brota-server`; no usar `brota-dev` en el servidor.
Los archivos de entorno se excluyen de Git; el secreto debe tener permisos 600 y
estar disponible al usuario que ejecuta Compose. Conservarlo en un gestor seguro.

Para simplificar los comandos de esta guía, definir en Bash:

```bash
dc() { docker compose --env-file infra/env/server.env -f infra/compose.yaml -f infra/compose.server.yaml "$@"; }
dc ps
dc logs --tail 100 db
dc exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "SELECT current_database(), version();"'
```

`dc stop` detiene y `dc up -d --wait` inicia. `dc down` retira contenedores y red,
conservando datos. Nunca usar `down -v` para una parada operativa. No abrir 5432 en
el firewall. El HTTPS y la publicación web se añadirán con las aplicaciones.

## Respaldo

Los clientes se ejecutan dentro del contenedor. El archivo binario se copia con
`docker compose cp`; no pasa por redirecciones de PowerShell.

```bash
mkdir -p backups
chmod 700 backups
backup_file="backups/brota-$(date -u +%Y%m%dT%H%M%SZ).dump"
dc exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl --file=/tmp/brota.dump'
dc cp db:/tmp/brota.dump "$backup_file"
chmod 600 "$backup_file"
dc exec -T db rm /tmp/brota.dump
```

Copiar el respaldo fuera del servidor por un canal autorizado. Durante la
hackathon, hacerlo antes de cada actualización y al terminar la jornada; acordar
después frecuencia, retención y responsable con la Fundación. Un respaldo solo
se considera utilizable tras comprobar su restauración.

El dump contiene una base, no los roles globales del clúster. Recrear sus roles y
permisos desde el procedimiento de la aplicación cuando este exista. La base
vacía actual solo necesita el administrador inicial.

## Restauración de comprobación

Restaurar en una base nueva, no sobre la base activa. El ejemplo usa el mismo
servidor y requiere espacio adicional; para una copia productiva preferir otra
instancia aislada. Ejecutar en ventana controlada y elegir un nombre nuevo si existe:

```bash
dc exec -T db sh -c 'createdb -U "$POSTGRES_USER" brota_restore_check'
dc cp "$backup_file" db:/tmp/brota-restore.dump
dc exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d brota_restore_check --no-owner --no-acl --exit-on-error /tmp/brota-restore.dump'
dc exec -T db sh -c 'psql -U "$POSTGRES_USER" -d brota_restore_check -v ON_ERROR_STOP=1 -c "SELECT current_database();"'
dc exec -T db rm /tmp/brota-restore.dump
```

Con datos reales, contrastar tablas, cantidades y operaciones clave con el origen.
Eliminar `brota_restore_check` solo cuando se haya confirmado que es la copia de
comprobación y no tiene conexiones activas. La CI comprueba este flujo con un
marcador técnico en una segunda instancia temporal.

## Respaldo desde PowerShell

Para desarrollo, sin instalar clientes PostgreSQL en Windows:

```powershell
function dc { docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml @args }
New-Item -ItemType Directory -Force backups | Out-Null
$backupFile = 'backups/brota-' + (Get-Date -Format 'yyyyMMddTHHmmss') + '.dump'
dc exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl --file=/tmp/brota.dump'
if ($LASTEXITCODE -ne 0) { throw 'Falló pg_dump' }
dc cp db:/tmp/brota.dump $backupFile
if ($LASTEXITCODE -ne 0) { throw 'Falló la copia del respaldo' }
dc exec -T db rm /tmp/brota.dump
```

Para verificar la restauración, usar los mismos comandos `dc exec` y `dc cp` del
apartado anterior sustituyendo `$backup_file` por `$backupFile`. Mantener el
directorio de respaldos bajo una cuenta autorizada; las ACL de Windows reemplazan
los permisos Unix. Comprobar `$LASTEXITCODE` antes de continuar tras cada operación.

## Actualizaciones y recuperación

1. Confirmar la versión destino, compatibilidad y espacio disponible; respaldar.
2. Cambiar la etiqueta explícita en Git; ejecutar `dc pull` y `dc up -d --wait`.
3. Comprobar disponibilidad y conexión SQL; con aplicaciones, ejecutar sus pruebas de humo.

Las actualizaciones mayores de PostgreSQL requieren un procedimiento específico
de migración (por ejemplo dump/restore en un volumen nuevo). No cambiar solo la
etiqueta ni reutilizar el volumen con otra versión mayor.

Cuando existan aplicaciones, conservar la etiqueta de imagen anterior para poder
revertirla. Solo volver a esa imagen si es compatible con el esquema actual.
Una reversión de aplicación no restaura datos ni revierte migraciones. Restaurar
datos implica una decisión explícita sobre la pérdida de escrituras posteriores
al respaldo y una ventana de mantenimiento.

## Traslado entre servicios y Fundación

1. Preparar PostgreSQL destino y verificar conectividad, versión y TLS.
2. Detener las escrituras en el origen y generar un respaldo final.
3. Restaurarlo en una base nueva del destino; recrear roles y permisos requeridos.
4. Verificar datos y funcionamiento de las aplicaciones antes de habilitar escrituras.
5. Cambiar conexiones y URLs, activar el destino y conservar el origen sin escrituras.

Si falla antes de aceptar escrituras en destino, se puede volver al origen. Si ya
hay escrituras nuevas, planificar su reconciliación antes de regresar. Los archivos
subidos por usuarios, si se incorporan después, también necesitarán traslado.
