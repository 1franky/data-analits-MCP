# Operación

## Alcance

Esta guía cubre backup, restore, upgrade y rollback del stack Docker Compose de Data Platform MCP,
más un checklist de puertos y secretos previo a cualquier despliegue fuera del laboratorio local.

No cubre gestión de secretos de producción real (Vault, Docker secrets u otro gestor externo): sigue
siendo una nota de intención, ya documentada en [security.md](security.md), no una implementación de
este proyecto. Tampoco cubre coordinación entre réplicas: la arquitectura actual asume un único
proceso (ver "Persistencia y despliegue" en [architecture.md](architecture.md)).

## Volúmenes

Docker antepone el nombre del proyecto Compose (por defecto, el nombre del directorio — `mcp` en un
checkout estándar) a cada volumen nombrado. Para conocer el nombre real en tu entorno:

```bash
docker volume ls --filter name=catalog-data --filter name=postgres-data \
  --filter name=qdrant-data --filter name=mariadb-data --filter name=mongo-data
```

| Volumen | Contiene | Servicio a detener antes de respaldar |
|---|---|---|
| `catalog-data` | `catalog.db`, `audit.db` y `documents.db` (SQLite, montados en `/app/data`) | `data-platform-mcp` |
| `postgres-data` | Datos de PostgreSQL (`postgres-lab`) | `postgres-lab` |
| `mariadb-data` | Datos de MariaDB (`mariadb-lab`) | `mariadb-lab` |
| `mongo-data` | Datos de MongoDB (`mongo-lab`) | `mongo-lab` |
| `qdrant-data` | Vectores de embeddings (`qdrant`) | `qdrant` |

## Backup

Detener el servicio relevante antes de respaldar garantiza un backup consistente (evita copiar
archivos a medio escribir):

```bash
docker compose stop <servicio>
scripts/backup_volume.sh <volumen_real> [directorio_destino=./backups]
docker compose start <servicio>
```

El script (`scripts/backup_volume.sh`) usa un contenedor auxiliar de solo lectura (`alpine:3.21`)
para empaquetar el volumen completo en un `.tar.gz` con timestamp UTC, sin requerir acceso directo al
filesystem del host. Verifica que el archivo se generó (el propio script imprime la ruta al terminar).

Ejemplo, para respaldar el catálogo/auditoría antes de un upgrade:

```bash
docker compose stop data-platform-mcp
scripts/backup_volume.sh mcp_catalog-data ./backups
docker compose start data-platform-mcp
```

## Restore

**Advertencia:** `scripts/restore_volume.sh` vacía por completo el volumen destino antes de extraer el
backup — cualquier dato existente en ese volumen se pierde. Nunca lo ejecutes contra un volumen en uso
por un servicio corriendo.

```bash
docker compose stop <servicio>
scripts/restore_volume.sh <volumen_real> <archivo.tar.gz>
docker compose start <servicio>
```

Para restaurar en un volumen nuevo (por ejemplo, para inspeccionar un backup sin arriesgar el volumen
real), crea el volumen vacío primero y apunta el script a él en vez del volumen de producción.

## Upgrade

El mecanismo de versionado ya existe en `.env`/`compose.yaml` — cada servicio fija su imagen vía una
variable `*_IMAGE_TAG` (`IMAGE_TAG` para `data-platform-mcp`, `POSTGRES_IMAGE_TAG`, `QDRANT_IMAGE_TAG`,
`MARIADB_IMAGE_TAG`, `MONGO_IMAGE_TAG` para los servicios de laboratorio).

1. **Backup previo obligatorio** de los volúmenes de los servicios que se van a actualizar (ver
   sección anterior).
2. Cambiar el tag correspondiente en `.env` (por ejemplo, `IMAGE_TAG=0.10.0`).
3. Reconstruir si aplica y levantar: `docker compose build <servicio>` (solo necesario para
   `data-platform-mcp`, que se construye localmente; los servicios de laboratorio con imagen oficial
   externa no requieren build) seguido de `docker compose up -d`.
4. Verificar el resultado: `GET /health` (liveness), `GET /ready` (readiness — confirma que el
   catálogo y los schedulers de fondo arrancaron correctamente) y `scripts/smoke_mcp.py` contra el
   servidor ya arriba.

## Rollback

Mismo mecanismo a la inversa: volver el tag anterior en `.env` y `docker compose up -d`.

**Advertencia:** un rollback de versión **mayor** de un motor de base de datos (PostgreSQL, MariaDB o
MongoDB) puede no ser compatible con datos ya escritos en disco por la versión nueva — el formato
interno de los archivos de datos puede haber cambiado. En ese caso, bajar el tag e iniciar el
contenedor viejo puede fallar al arrancar o corromper datos. Si el upgrade cruzó una versión mayor del
motor, el rollback seguro requiere restaurar el backup tomado antes del upgrade, no solo revertir el
tag.

## Checklist de puertos y secretos

Ya cumplido por defecto en este repositorio (verificado contra `compose.yaml`/`.env.example`):

- [x] Todos los puertos publicados al host usan bind configurable con default `127.0.0.1` (loopback),
  vía `MCP_BIND_ADDRESS`, `POSTGRES_LAB_BIND_ADDRESS`, `MARIADB_LAB_BIND_ADDRESS`,
  `MONGO_LAB_BIND_ADDRESS`.
- [x] `qdrant` no publica ningún puerto al host — solo alcanzable dentro de la red `ai-platform`.
- [x] Todos los secretos de laboratorio (`POSTGRES_LAB_ADMIN_PASSWORD`, `POSTGRES_DEMO_PASSWORD`,
  `MARIADB_LAB_ADMIN_PASSWORD`, `MARIADB_DEMO_PASSWORD`, `MONGO_LAB_ADMIN_PASSWORD`,
  `MONGO_DEMO_PASSWORD`) son obligatorios en `compose.yaml` vía `${VAR:?mensaje}` — el stack no
  arranca sin definirlos explícitamente en `.env`.
- [x] `data-platform-mcp` corre con `read_only: true`, usuario no-root, `cap_drop: ALL` y
  `security_opt: no-new-privileges:true`.

Pendiente manual antes de cualquier despliegue fuera del laboratorio local (detalle completo en
[security.md](security.md), sección "Responsabilidades del administrador"):

- [ ] Sustituir todos los valores `local-only-*-change-me` de `.env` por secretos reales.
- [ ] Proteger el archivo `.env` y el volumen de datos con permisos de filesystem restrictivos.
- [ ] Restringir la membresía de la red `ai-platform` — no publicar el MCP ni PostgreSQL/MariaDB/
  MongoDB a Internet.
- [ ] Configurar TLS si el servidor se conecta a bases de datos remotas fuera de la red Docker.
- [ ] Definir un mecanismo real de gestión de secretos (Vault, Docker secrets u otro) si el
  despliegue lo requiere — hoy los secretos solo pasan por variables de entorno.
