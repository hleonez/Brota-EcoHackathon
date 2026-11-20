# API de Brota

FastAPI + SQLAlchemy 2 + Alembic sobre PostgreSQL 18. Contrato: [docs/contrato-api.md](../docs/contrato-api.md).
Integración del bot: [docs/integracion-bot.md](../docs/integracion-bot.md). OpenAPI en `/docs`.

## Estructura

```text
api/
├─ app/
│  ├─ main.py            Ensambla la app, CORS, request-id, despachador de avisos
│  ├─ config.py          Variables de entorno (api/.env)
│  ├─ models.py          Modelo relacional (diseño de BD 18-nov)
│  ├─ core/              Errores, autenticación, idempotencia, tipos decimales, paginación
│  ├─ modulos/           Un archivo por módulo del contrato (esquemas + servicio + rutas)
│  ├─ despachador.py     Avisos por webhook al bot + limpieza de claves de idempotencia
│  └─ seed.py            Datos semilla del piloto (valores de ejemplo)
├─ migrations/           Alembic (0001: núcleo)
└─ tests/                Recorrido completo contra una base real separada (brota_test)
```

## Ejecutar en el equipo (recomendado para desarrollar)

Requisitos: [uv](https://docs.astral.sh/uv/) y PostgreSQL levantado según el [README principal](../README.md).

```powershell
cd api
Copy-Item .env.example .env
```

Completa en `api/.env` `JWT_SECRET` (32+ caracteres aleatorios) y `BOT_SERVICE_TOKEN`.
En desarrollo, `DB_USER=brota_admin` y `DB_PASSWORD_FILE` apuntan al secreto creado en `infra/secrets/`.

```powershell
uv sync
uv run alembic upgrade head
$env:SEED_PIN = "2468"; uv run python -m app.seed
uv run uvicorn app.main:app --reload --port 8000
```

Abre `http://localhost:8000/docs`. Cuentas de la semilla (PIN = `SEED_PIN`; si no lo defines,
la semilla genera uno y lo imprime una vez): `coord-reciclaje`, `coord-huerta`, `fundacion`, `admin`.

Si el puerto 8000 está ocupado, usa otro (`--port 8010`) y ajusta la URL del bot.

## Pruebas

```powershell
uv run pytest
```

Crean y vacían la base `brota_test` en el mismo PostgreSQL (nunca la de desarrollo). Cubren:
registro por canal, solicitud mixta, idempotencia y doble toque concurrente, solicitud abierta,
permisos por gremio, asignación/reasignación, avisos pull y webhook firmado, puntos únicos,
rechazo con educación, pesaje de lote, baldes, corrección, Liga, reportes y sync offline.

## Ejecutar en Docker

Desde la raíz del repositorio (usa `api/.env` para los secretos de la API):

```powershell
docker compose --env-file infra/env/dev.env -f infra/compose.yaml -f infra/compose.dev.yaml -f infra/compose.api.yaml up -d --build --wait
```

El contenedor aplica migraciones al iniciar (`API_MIGRAR_AL_INICIAR=true`). Para sembrar,
define `API_SEMBRAR_AL_INICIAR=true` y `SEED_PIN` en `api/.env`. Puerto publicado:
`API_LOCAL_PORT` (8000 por defecto, solo localhost).

## Migraciones

Tras cambiar `app/models.py`:

```powershell
uv run alembic revision --autogenerate -m "describe el cambio"
uv run alembic upgrade head
```

Revisa el archivo generado (secuencias, índices parciales y datos no se detectan siempre).
Después de cambiar dependencias, regenera `requirements.txt` para Docker:

```powershell
uv export --no-dev --no-hashes --format requirements-txt -o requirements.txt
```

## Variables

| Variable | Uso |
| --- | --- |
| `DB_*` | Conexión a PostgreSQL; `DB_PASSWORD_FILE` como alternativa a `DB_PASSWORD` |
| `JWT_SECRET`, `JWT_MINUTOS` | Sesiones de operadores (12 h por defecto) |
| `BOT_SERVICE_TOKEN` | Token compartido con el bot |
| `AVISOS_MODO` | `pull` (el bot reserva) o `webhook` (la API empuja) |
| `BOT_WEBHOOK_URL`, `BOT_WEBHOOK_SECRET` | Modo webhook; firma HMAC-SHA256 |
| `REGLA_SOLICITUD_ABIERTA` | `true`: no duplicar solicitudes abiertas del mismo servicio |
| `POLITICA_DATOS_VERSION` | Versión de política que acepta el registro (`2026-11`) |
| `ROOT_PATH` | `/api` detrás del proxy |
| `CORS_ALLOWED_ORIGINS` | Orígenes exactos de los paneles |

## Pendiente

- Rol de PostgreSQL restringido para la API (hoy, en desarrollo, se usa el administrador).
- M06 (foto de tiquete, audio), canjes, exportaciones Excel, Certificado Verde y hoja de ruta.
- Reemplazar los valores de ejemplo de la semilla por datos reales (viviendas, precios, balde).
