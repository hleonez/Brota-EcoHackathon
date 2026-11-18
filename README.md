# Brota · Base de infraestructura

Infraestructura PostgreSQL desplegable y guía para incorporar la API y los paneles
cuando se conozcan los frameworks del reto. La base se inicia vacía: todavía no
hay aplicaciones, tablas de negocio ni migraciones. El plan maestro es una
referencia de producto, no una selección definitiva de tecnologías.

## Requisitos

- Git y Docker con el plugin Compose v2, con soporte de `up --wait` y `config --format json`.
- Windows: Docker Desktop con contenedores Linux y WSL2; PowerShell.
- Servidor: Linux con Docker Engine y Compose v2. Sus características están pendientes de confirmar.
- Acceso al registro de imágenes para la primera descarga.

Comprueba `docker version` y `docker compose version`. Ejecuta los comandos desde
la raíz de este repositorio, después de clonarlo y entrar en su carpeta.

## Arranque local

PowerShell (la generación se detiene si el secreto ya existe):

```powershell
Copy-Item infra/env/dev.env.example infra/env/dev.env
if (Test-Path infra/secrets/dev-db-password.txt) { throw 'El secreto ya existe' }
$secretBytes = New-Object byte[] 32
$secretRng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $secretRng.GetBytes($secretBytes) } finally { $secretRng.Dispose() }
[IO.File]::WriteAllText((Join-Path $PWD 'infra/secrets/dev-db-password.txt'), [Convert]::ToBase64String($secretBytes), [Text.UTF8Encoding]::new($false))
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml config --quiet
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml up -d --wait --wait-timeout 120
```

Linux / Bash:

```bash
cp -n infra/env/dev.env.example infra/env/dev.env
(umask 077; set -o noclobber; openssl rand -base64 32 > infra/secrets/dev-db-password.txt)
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml config --quiet
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml up -d --wait --wait-timeout 120
```

El secreto no se regenera en arranques posteriores. Para reiniciar basta el comando
`up`. Si el puerto 5432 está ocupado, cambia `DB_LOCAL_PORT` en `dev.env`.
La base queda accesible en `127.0.0.1:5432` (o el puerto configurado).

## Operación local

Los siguientes comandos funcionan en PowerShell y Bash:

```text
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml ps
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml logs --tail 100 db
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml exec db psql -U brota_admin -d brota -c "SELECT current_database(), version();"
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml down
```

Si cambiaste `DB_USER` o `DB_NAME`, ajusta también el comando SQL. `down` conserva
el volumen; `down -v` lo elimina. Cambiar el nombre del proyecto selecciona otro
volumen, no mueve los datos. Cambiar variables de inicialización o el archivo de
contraseña tampoco modifica una base ya inicializada.

## Guías y estructura

- [Backend](api/README.md): instrucciones de incorporación y `.env.example` local.
- [Paneles](web/README.md): espacios provisionales de coordinación y Fundación,
  con puertos de desarrollo 3000 y 3001; API compartida en el puerto 8000.
- `infra/`: Compose, ejemplos de entorno y validaciones.
- [Integración de aplicaciones y despliegue separado](docs/integracion.md).
- [Servidor, respaldos, traslado y recuperación](docs/operacion.md).
- [Decisiones y datos pendientes de la Fundación](docs/decisiones.md).
- [Validación y estado de las comprobaciones](docs/validacion.md).

GitHub Actions valida la configuración y prueba PostgreSQL en entornos temporales.
No publica imágenes ni despliega. Nunca ejecutes las pruebas de infraestructura
contra los proyectos `brota-dev` o `brota-server`.
