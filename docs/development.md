# Desarrollo

## Preparación

La versión de referencia es Python 3.12. El camino recomendado es usar el target Docker `test`, que
evita depender de la versión de Python instalada en el anfitrión y reproduce Linux ARM64/AMD64.

```bash
cp .env.example .env
docker network inspect ai-platform >/dev/null 2>&1 || docker network create ai-platform
```

`.env` está ignorado por Git. No añadas secretos a `.env.example`.

## Instalación local opcional

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Arranque local:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Validaciones

Construye una vez el entorno de calidad:

```bash
docker build --target test -t data-platform-mcp:test .
```

Ejecuta cada control de forma independiente:

```bash
docker run --rm data-platform-mcp:test pytest
docker run --rm data-platform-mcp:test ruff check app tests
docker run --rm data-platform-mcp:test ruff format --check app tests
docker run --rm data-platform-mcp:test mypy app tests
docker compose config --quiet
docker compose build data-platform-mcp
```

Ninguna validación debe marcarse como aprobada si el comando no se ejecutó. Los resultados reales
del último cierre de sprint se registran en `TASKS.md`.

## Prueba del servicio

```bash
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:8000/health
docker compose logs data-platform-mcp
docker compose down
```

Desde otro contenedor conectado a `ai-platform`, la URL MCP es:

```text
http://data-platform-mcp:8000/mcp
```

No uses `localhost` desde Open WebUI: dentro de su contenedor, `localhost` apunta a Open WebUI, no
al servicio MCP.

## Convenciones

- Python objetivo: 3.12; usa anotaciones de tipo para toda función pública.
- Ruff es la única herramienta de lint y formato.
- mypy se ejecuta en modo estricto sobre `app` y `tests`.
- Las pruebas unitarias no deben depender de servicios externos.
- Una función MCP debe probarse a través del cliente en memoria, además de probar su lógica cuando
  corresponda.
- No agregues una capa futura hasta que exista una historia con comportamiento y pruebas reales.
- No mezcles generación de consultas con ejecución.
- No registres secretos, cadenas de conexión ni datos sensibles.

## Dependencias

Las dependencias de runtime y desarrollo se declaran en `pyproject.toml` con rangos controlados. No
se aceptan imágenes Docker con etiqueta `latest`. Una actualización de FastMCP debe volver a probar
el lifespan ASGI, el listado de herramientas y una llamada real a `hello_world`.

## Flujo Git

El trabajo de Sprint 0 se realiza en `feature/sprint-0-bootstrap`. Antes de solicitar revisión:

```bash
git status --short
git diff --check
git diff --stat
git diff
```

No se crea ningún commit hasta recibir aprobación explícita.
