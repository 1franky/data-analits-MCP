#!/bin/sh
set -eu

: "${POSTGRES_DEMO_PASSWORD:?POSTGRES_DEMO_PASSWORD is required}"

psql \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --set=readonly_password="$POSTGRES_DEMO_PASSWORD" <<'SQL'
ALTER ROLE mcp_readonly WITH PASSWORD :'readonly_password';
SQL
