#!/usr/bin/env bash
# Only disposable instances created by this script; never accepts an existing project.
set -euo pipefail
cd "$(dirname "$0")/.."
workspace=$(mktemp -d)
project="brota-ci-$(date +%s)-$$"
restore_project="${project}-restore"
export DB_NAME=brota_ci DB_USER=brota_ci_admin
export DB_PASSWORD_FILE="$workspace/password"
export DB_LOCAL_PORT=15432
openssl rand -hex 32 > "$DB_PASSWORD_FILE"
chmod 600 "$DB_PASSWORD_FILE"
touch "$workspace/ci.env"

dc() {
  docker compose --env-file "$workspace/ci.env" -p "$project" \
    -f infra/compose.yaml -f infra/compose.server.yaml "$@"
}
restore_dc() {
  docker compose --env-file "$workspace/ci.env" -p "$restore_project" \
    -f infra/compose.yaml -f infra/compose.server.yaml "$@"
}
cleanup() {
  local status=$?
  if (( status != 0 )); then
    dc logs --tail 80 db || true
    restore_dc logs --tail 80 db || true
  fi
  dc down -v --remove-orphans || true
  restore_dc down -v --remove-orphans || true
  rm -rf -- "$workspace"
}
trap cleanup EXIT

python3 infra/check-config.py "$workspace/ci.env"
dc up -d --wait --wait-timeout 120

# TCP authentication uses the mounted secret, not local socket trust.
sql() {
  dc exec -T db sh -c 'export PGPASSWORD="$(cat /run/secrets/db_password)"; exec psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -Atc "$1"' sh "$1"
}
sql 'SELECT 1;' | grep -qx 1
sql "CREATE SCHEMA infra_probe; CREATE TABLE infra_probe.marker (value text); INSERT INTO infra_probe.marker VALUES ('persistent');"
dc up -d --force-recreate --wait --wait-timeout 120
sql 'SELECT value FROM infra_probe.marker;' | grep -qx persistent

dc exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-acl -f /tmp/probe.dump'
dc cp db:/tmp/probe.dump "$workspace/probe.dump"
restore_dc up -d --wait --wait-timeout 120
restore_dc cp "$workspace/probe.dump" db:/tmp/probe.dump
restore_dc exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl --exit-on-error /tmp/probe.dump'
restore_dc exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -Atc "SELECT value FROM infra_probe.marker;"' | grep -qx persistent
echo 'Connection, persistence and isolated restore: OK'
