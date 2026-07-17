#!/usr/bin/env bash
# Restaura un volumen Docker nombrado desde un archivo .tar.gz creado por
# backup_volume.sh, vía un contenedor auxiliar. Vacía por completo el contenido
# actual del volumen destino antes de extraer — ver docs/operations.md.
set -euo pipefail

: "${1:?Uso: scripts/restore_volume.sh <volumen> <archivo.tar.gz>}"
: "${2:?Uso: scripts/restore_volume.sh <volumen> <archivo.tar.gz>}"
volume="$1"
archive="$2"

if [ ! -f "$archive" ]; then
  echo "Error: el archivo de backup '${archive}' no existe." >&2
  exit 1
fi

archive_dir_abs="$(cd "$(dirname "$archive")" && pwd)"
archive_basename="$(basename "$archive")"

docker run --rm \
  -v "${volume}:/target" \
  -v "${archive_dir_abs}:/backup:ro" \
  alpine:3.21 \
  sh -c "find /target -mindepth 1 -delete && tar xzf /backup/${archive_basename} -C /target"

echo "Volumen '${volume}' restaurado desde ${archive}"
