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
la semilla genera uno y lo imprime una vez): `coord-reciclaje`, `coord-huerta`, `fundacion`, `admin`, `huertero-demo`, `reciclador-demo`.

Si el puerto 8000 está ocupado, usa otro (`--port 8010`) y ajusta la URL del bot.

## Pruebas

```powershell
uv run pytest
```

Crean y vacían solo `brota_test` en el PostgreSQL local (nunca `brota`, `postgres`, `template0` ni `template1`). El host tiene que ser loopback, salvo `BROTA_ALLOW_REMOTE_TEST=1`. Cubren registro por canal, solicitud mixta, idempotencia, permisos por gremio, los dos recorridos oficiales, piloto, privacidad, programación, puntos únicos, educación, pesaje, Liga, reportes y sync.

`python -m tests.verificar_migracion` aplica `upgrade head` en `brota_vacia_test` y, aparte, sube una copia del esquema `0004` con filas históricas en `brota_migrate_test`. Compara columnas y claves foráneas con el modelo y borra esas dos bases al terminar. La suite lo ejecuta como `test_upgrade_vacio_y_desde_el_esquema_anterior`.

Con el Compose de desarrollo, PostgreSQL queda en `127.0.0.1:5432` dentro de WSL. Si Windows no alcanza ese puerto, corre pytest desde la misma WSL con `DB_HOST`, `DB_PORT`, `DB_USER` y `DB_SSLMODE` de `infra/env/dev.env`, y la contraseña leída de `DB_PASSWORD_FILE` sin imprimirla. No definas `DB_NAME`: el fixture fuerza `brota_test`.

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
- Canjes, exportaciones Excel y hoja de ruta. Papel Inteligente (`POST /v1/pesajes/desde-foto`) y Certificado Verde (`GET /v1/reportes/certificado`) ya están. `POST /v1/ia/interpretar` sigue apagado.
- Reemplazar los valores de ejemplo de la semilla por datos reales (viviendas, precios, balde).


## Actualización EcoConecta

Contrato `0.3-ecoconecta.1`: consultar [campos obligatorios, rutas y migraciones](../docs/avance-api-ecoconecta.md). Antes de actualizar una base existente, crear respaldo y probar migraciones sobre copia. Este cambio requiere actualizar los clientes: preferencia horaria, canal de acuerdo y materiales confirmados al cierre. Gemini está desactivado en la API. La migración vigente es 0011.
