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
docker run --rm data-platform-mcp:test ruff check app tests
docker run --rm data-platform-mcp:test ruff format --check app tests
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

La suite comprueba conectividad, schemas, tablas, columnas, PK, FK y que `mcp_readonly` no puede
insertar. El valor mostrado coincide con el marcador de `.env.example`; usa el secreto real de tu
`.env` si lo cambiaste.

## Prueba manual del servicio

```bash
curl --fail http://127.0.0.1:8000/health
docker compose --env-file .env.example logs data-platform-mcp postgres-lab
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
- No agregar código de sprints futuros.

## Flujo Git

Sprint 1 se desarrolla en `feature/sprint-1-postgresql`. Antes de solicitar revisión:

```bash
git status --short
git diff --check
git diff --stat
git diff
```

No se crea un commit hasta recibir aprobación explícita.
