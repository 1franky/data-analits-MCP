# Desarrollo

## Preparación

Python 3.12 es la referencia. El target Docker `test` reproduce el entorno Linux del runtime y evita
depender de la versión instalada en el anfitrión.

```bash
cp .env.example .env
# Sustituye los marcadores locales de contraseña.
docker network inspect ai-platform >/dev/null 2>&1 || docker network create ai-platform
```

`.env` está ignorado por Git. Nunca añadas secretos a `.env.example` o `connections.yaml`.

## Instalación local opcional

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
POSTGRES_DEMO_PASSWORD='valor-local' uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

El arranque local necesita que `connections.yaml` pueda resolverse y que PostgreSQL sea alcanzable
por el host configurado. Para el flujo completo se recomienda Compose.

## Validaciones unitarias y estáticas

```bash
docker build --target test -t data-platform-mcp:test .
docker run --rm data-platform-mcp:test pytest -m 'not integration'
docker run --rm data-platform-mcp:test ruff check app tests scripts
docker run --rm data-platform-mcp:test ruff format --check app tests scripts
docker run --rm data-platform-mcp:test mypy app tests
docker compose --env-file .env.example config --quiet
docker compose --env-file .env.example build data-platform-mcp
docker compose --env-file .env.example build postgres-lab
```

## Pruebas de integración PostgreSQL

Crea el laboratorio desde cero para que todos los scripts de inicialización se apliquen:

```bash
docker compose --env-file .env.example down --volumes --remove-orphans
docker compose --env-file .env.example up -d --build
docker compose --env-file .env.example ps
```

Ejecuta la suite desde la imagen de pruebas en la red compartida:

```bash
docker run --rm \
  --network ai-platform \
  -e RUN_POSTGRES_INTEGRATION=1 \
  -e POSTGRES_DEMO_PASSWORD=local-only-readonly-change-me \
  data-platform-mcp:test pytest -m integration
```

La suite comprueba conectividad, schemas, tablas, comentarios, columnas, PK, FK, refresh/búsqueda
contra PostgreSQL real y que `mcp_readonly` no puede insertar. Desde Sprint 3 también cubre JOIN,
CTE, agregaciones, ventanas, parámetros, límites de filas/bytes, timeout, serialización, auditoría,
`EXPLAIN` JSON y pruebas que confirman que DML/DDL/bypass no cambian los datos. El valor mostrado
coincide con el marcador de `.env.example`; usa el secreto real de tu `.env` si lo cambiaste.

Sprint 4 añade aserciones reales de índices únicos, tools de metadata y cardinalidad inferida.

## Validación de transportes MCP

La suite unitaria abre un cliente en memoria para los schemas de contrato y un subproceso real para
STDIO. Para una prueba manual local del mismo transporte:

```bash
data-platform-mcp-stdio
# Alternativa equivalente:
python -m app.tools.server
```

Con Compose activo, ejecuta el smoke de Streamable HTTP desde la red externa:

```bash
docker run --rm \
  --network ai-platform \
  data-platform-mcp:test \
  python scripts/smoke_mcp.py \
  --url http://data-platform-mcp:8000/mcp \
  --connection-id postgres-demo
```

El script exige las 15 herramientas, ejecuta `health_check`, refresca el catálogo y recorre schemas,
tablas, descripción y relaciones. Termina con código distinto de cero ante un error de transporte,
tool faltante o fallo del servidor.

## Prueba manual del servicio

```bash
curl --fail http://127.0.0.1:8000/health
docker compose --env-file .env.example logs data-platform-mcp postgres-lab
docker compose --env-file .env.example exec data-platform-mcp \
  python -c "from app.container import get_catalog_service; print(get_catalog_service().get_cache_status())"
docker compose --env-file .env.example exec data-platform-mcp \
  python -c "from app.container import get_audit_repository; print(len(get_audit_repository().list_records()))"
```

Desde Open WebUI u otro contenedor conectado a `ai-platform`:

```text
http://data-platform-mcp:8000/mcp
```

No uses `localhost` desde Open WebUI: apunta al propio contenedor de Open WebUI.

## Convenciones

- Anotaciones de tipo en toda función y mypy estricto sobre `app` y `tests`.
- Ruff es la única herramienta de lint y formato.
- Pruebas unitarias sin servicios externos; integración marcada y opt-in.
- Builders de adaptadores registrados por tipo, sin cadenas `if/elif` centrales.
- Errores en fronteras de transporte normalizados y sin detalles sensibles.
- Consultas de catálogos parametrizadas; nunca interpolar nombres recibidos.
- Toda consulta de usuario pasa por SQLGlot y `QueryExecutionService`; no invoques directamente el
  método de ejecución del adaptador desde una herramienta.
- Usa placeholders PostgreSQL nombrados (`%(nombre)s`) y exige coincidencia exacta de parámetros.
- Añade casos de bloqueo y una prueba de integración que demuestre ausencia de cambios para toda
  ampliación de la política SQL.
- Snapshots de catálogo metadata-only; un fallo nunca reemplaza el último snapshot válido.
- La auditoría no puede guardar texto SQL, parámetros ni filas devueltas.
- No agregar código de sprints futuros.

## Flujo Git

Sprint 4 se desarrolla en `feature/sprint-4-mcp-contracts`. Antes de solicitar revisión:

```bash
git status --short
git diff --check
git diff --stat
git diff
```

El commit y push se realizan sólo cuando fueron solicitados explícitamente.
