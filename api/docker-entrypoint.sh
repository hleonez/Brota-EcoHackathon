#!/bin/sh
set -eu

if [ "${MIGRAR_AL_INICIAR:-false}" = "true" ]; then
    echo "Aplicando migraciones..."
    alembic upgrade head
fi
if [ "${SEMBRAR_AL_INICIAR:-false}" = "true" ]; then
    python -m app.seed
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
