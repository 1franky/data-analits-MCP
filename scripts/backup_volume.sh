#!/usr/bin/env bash
# Respalda un volumen Docker nombrado a un archivo .tar.gz local, vía un contenedor
# auxiliar de solo lectura. No detiene ningún servicio por sí mismo — ver
# docs/operations.md para el procedimiento completo (detener el servicio antes de
# respaldar para garantizar consistencia).
set -euo pipefail

: "${1:?Uso: scripts/backup_volume.sh <volumen> [directorio_destino=./backups]}"
volume="$1"
dest="${2:-./backups}"

mkdir -p "$dest"
dest_abs="$(cd "$dest" && pwd)"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive_name="${volume}_${timestamp}.tar.gz"

docker run --rm \
  -v "${volume}:/source:ro" \
  -v "${dest_abs}:/backup" \
  alpine:3.21 \
  tar czf "/backup/${archive_name}" -C /source .

echo "Backup creado: ${dest_abs}/${archive_name}"
