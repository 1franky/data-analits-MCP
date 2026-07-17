#!/bin/sh
set -eu

: "${MARIADB_DEMO_PASSWORD:?MARIADB_DEMO_PASSWORD is required}"

mariadb --user=root --password="$MARIADB_ROOT_PASSWORD" <<SQL
ALTER USER 'mcp_readonly'@'%' IDENTIFIED BY '$MARIADB_DEMO_PASSWORD';
FLUSH PRIVILEGES;
SQL
