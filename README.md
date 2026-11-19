# Brota · Base de infraestructura

Infraestructura PostgreSQL desplegable y la API central de Brota (`api/`, FastAPI
con migraciones Alembic). La API atiende al bot de WhatsApp y a los futuros paneles.
El plan maestro es una referencia de producto; el stack puede ajustarse si el reto
impone otro.

## Requisitos

- Git y Docker con el plugin Compose v2, con soporte de `up --wait` y `config --format json`.
- Windows: Docker Desktop con contenedores Linux y WSL2; PowerShell.
- Servidor: Linux con Docker Engine y Compose v2. Sus características están pendientes de confirmar.
- Acceso al registro de imágenes para la primera descarga.

Comprueba `docker version` y `docker compose version`. Ejecuta los comandos desde
la raíz de este repositorio, después de clonarlo y entrar en su carpeta.

## Cómo levantar el proyecto en Windows

Estos pasos levantan PostgreSQL. La API (FastAPI) ya existe en `api/`: después del
paso 4 sigue [api/README.md](api/README.md). Los paneles todavía son carpetas preparadas.

### 1. Abre Docker Desktop

Espera a que termine de iniciar. Debe usar contenedores Linux.

### 2. Abre PowerShell en la carpeta del proyecto

En tu equipo:

```powershell
cd "C:\Users\handr\OneDrive\Documentos\Brota-EcoHackathon"
```

Si otra persona clonó el repositorio en una ubicación diferente, debe usar la ruta
de su propia carpeta.

### 3. Prepara la configuración una sola vez

Este comando crea tu archivo de configuración local. Si ya tienes `dev.env`,
conserva el existente y omite este comando:

```powershell
Copy-Item infra/env/dev.env.example infra/env/dev.env
```

Luego pega este bloque completo para generar y guardar una contraseña aleatoria.
Si ya la generaste, omite el bloque; no necesitas repetirlo en próximos arranques:

```powershell
if (Test-Path infra/secrets/dev-db-password.txt) {
    throw 'La contraseña ya existe. No necesitas generarla otra vez.'
}

$secretBytes = New-Object byte[] 32
$secretRng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $secretRng.GetBytes($secretBytes)
} finally {
    $secretRng.Dispose()
}

[IO.File]::WriteAllText(
    (Join-Path $PWD 'infra/secrets/dev-db-password.txt'),
    [Convert]::ToBase64String($secretBytes),
    [Text.UTF8Encoding]::new($false)
)
```

### 4. Levanta PostgreSQL

```powershell
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml up -d --wait
```

Este comando significa:

| Parte | Para qué sirve |
| --- | --- |
| `--env-file infra/env/dev.env` | Lee tu configuración local |
| `-f infra/compose.yaml` | Lee la configuración base de PostgreSQL |
| `-f infra/compose.dev.yaml` | Añade el acceso local para desarrollo |
| `up` | Crea e inicia el contenedor |
| `-d` | Lo deja funcionando en segundo plano |
| `--wait` | Espera hasta que la base esté disponible |

La primera ejecución descargará PostgreSQL y puede tardar.

### 5. Comprueba que está funcionando

```powershell
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml ps
```

Deberías ver el servicio `db` con estado **healthy**. Eso indica que PostgreSQL
está disponible en `127.0.0.1:5432`. No se abrirá ninguna página web todavía.
Si el puerto 5432 está ocupado, cambia `DB_LOCAL_PORT` en `infra/env/dev.env` y
repite el paso 4; usa el nuevo puerto para conectarte.

### Para trabajar otro día

Abre Docker Desktop y PowerShell en la carpeta del proyecto. Repite únicamente
el comando del paso 4. No vuelvas a crear la configuración ni la contraseña.

### Para detenerlo

Ejecuta este comando cuando termines de trabajar y quieras apagar la base:

```powershell
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml down
```

Este comando conserva los datos. **No añadas `-v`**, porque eliminaría el volumen
que los almacena.

## Arranque local en Linux / Bash

Desde la raíz del repositorio, prepara la configuración y contraseña una sola vez:

```bash
cp -n infra/env/dev.env.example infra/env/dev.env
(umask 077; set -o noclobber; openssl rand -base64 32 > infra/secrets/dev-db-password.txt)
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml config --quiet
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml up -d --wait --wait-timeout 120
```

El secreto no se regenera en arranques posteriores. Para reiniciar basta el comando
`up` del bloque anterior. Si ya existe `dev.env`, conserva su configuración.
Si el puerto 5432 está ocupado, cambia `DB_LOCAL_PORT` en `dev.env`.
La base queda accesible en `127.0.0.1:5432` (o el puerto configurado).

## Comandos opcionales de consulta

Usa solo el comando que necesites. **Son consultas independientes**, no pasos que
debas ejecutar todos seguidos después de iniciar la base. Funcionan en PowerShell
y Bash desde la raíz del proyecto. Copia cada comando en una sola línea, sin
añadir una barra `\` al final.

### Ver si la base está funcionando

Muestra el estado del contenedor. Busca el servicio `db` con estado `healthy`:

```text
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml ps
```

### Consultar mensajes si ocurre un error

Muestra los últimos 100 mensajes de PostgreSQL. Úsalo si la base no arranca o
necesitas investigar un problema:

```text
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml logs --tail 100 db
```

### Comprobar que PostgreSQL responde a una consulta

Con la base encendida, ejecuta esta consulta de lectura. Muestra el nombre de la
base y la versión de PostgreSQL; no modifica los datos:

```text
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml exec db psql -U brota_admin -d brota -c "SELECT current_database(), version();"
```

Si cambiaste `DB_USER` o `DB_NAME` en `infra/env/dev.env`, reemplaza `brota_admin`
o `brota` en este comando por los valores que elegiste.

Para apagar la base al terminar, usa el apartado **Para detenerlo** del tutorial.

### Sobre la configuración de una base existente

Cambiar el nombre del proyecto selecciona otro volumen, no mueve los datos.
Cambiar variables de inicialización o el archivo de contraseña tampoco modifica
una base ya inicializada. Consulta la [guía de operación](docs/operacion.md) antes
de cambiar una instalación con datos.

## Guías y estructura

- [Backend](api/README.md): ejecución, pruebas, migraciones y Docker de la API.
- [Contrato de API](docs/contrato-api.md) e [integración del bot de WhatsApp](docs/integracion-bot.md).
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
