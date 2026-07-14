# Data Platform MCP

Data Platform MCP será una plataforma independiente del proveedor de LLM para explorar y
consultar fuentes de datos desde clientes compatibles con Model Context Protocol (MCP), incluido
Open WebUI. El objetivo final es ofrecer metadatos, generación de consultas y ejecución de solo
lectura con validación, límites, auditoría y documentación recuperada mediante RAG.

Este repositorio contiene **exclusivamente el Sprint 0**: bootstrap técnico, documentación,
health check y una herramienta MCP de conectividad. Aún no se conecta a bases de datos, no valida
ni ejecuta SQL y no implementa RAG.

## Arquitectura actual

Un único proceso ASGI ejecutado por Uvicorn aloja dos interfaces:

- `GET /health`: liveness administrativo de FastAPI.
- `/mcp`: transporte MCP Streamable HTTP de FastMCP con la herramienta `hello_world`.

El contenedor `data-platform-mcp` se une a la red Docker externa `ai-platform`. Open WebUI puede
permanecer en otro proyecto Compose y alcanzar el servicio por el DNS interno
`data-platform-mcp:8000`. La arquitectura objetivo y sus límites están descritos en
[`docs/architecture.md`](docs/architecture.md).

## Requisitos

- Docker Engine 24 o posterior.
- Docker Compose v2.20 o posterior.
- Red Docker externa `ai-platform` creada previamente.
- Para desarrollo sin Docker: Python 3.12 y un entorno virtual.

La imagen base `python:3.12.13-slim-bookworm` tiene variante Linux ARM64 y es adecuada para una
instancia Oracle Cloud Free Tier ARM64. No se utilizan rutas absolutas del anfitrión.

## Inicio rápido con Docker

```bash
cp .env.example .env
docker network inspect ai-platform >/dev/null 2>&1 || docker network create ai-platform
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:8000/health
```

Respuesta esperada:

```json
{
  "status": "ok",
  "service": "data-platform-mcp",
  "version": "0.1.0"
}
```

El puerto se publica en `127.0.0.1:8000` por defecto, no en todas las interfaces. Los contenedores
de la red compartida usan `http://data-platform-mcp:8000`; un cliente MCP debe apuntar a
`http://data-platform-mcp:8000/mcp`.

Para detener el servicio:

```bash
docker compose down
```

## Desarrollo local

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Validaciones reproducibles en Python 3.12 mediante Docker:

```bash
docker build --target test -t data-platform-mcp:test .
docker run --rm data-platform-mcp:test pytest
docker run --rm data-platform-mcp:test ruff check app tests
docker run --rm data-platform-mcp:test ruff format --check app tests
docker run --rm data-platform-mcp:test mypy app tests
docker compose config --quiet
docker compose build data-platform-mcp
```

Consulta [`docs/development.md`](docs/development.md) para el flujo completo.

## Configuración

`.env.example` contiene únicamente opciones no sensibles:

| Variable | Predeterminado | Uso |
|---|---:|---|
| `AI_PLATFORM_NETWORK` | `ai-platform` | Red externa compartida con Open WebUI. |
| `MCP_BIND_ADDRESS` | `127.0.0.1` | Interfaz del anfitrión donde se publica el puerto. |
| `MCP_PORT` | `8000` | Puerto local publicado. |
| `LOG_LEVEL` | `info` | Nivel de log de Uvicorn. |
| `IMAGE_TAG` | `0.1.0` | Etiqueta local de la imagen construida. |

No agregues secretos a `.env.example`. La configuración de conexiones y secretos pertenece al
Sprint 1.

## Ejemplo MCP

La herramienta disponible en Sprint 0 es:

```text
hello_world(name: str = "world")
```

Para `name="Open WebUI"` devuelve:

```json
{"message": "Hello, Open WebUI!"}
```

La prueba automatizada usa el cliente en memoria de FastMCP y verifica tanto el registro como la
invocación real de la herramienta.

## Seguridad

- El proceso del contenedor se ejecuta con UID/GID no privilegiado `10001`.
- El filesystem raíz es de solo lectura en Compose; `/tmp` es un `tmpfs` limitado.
- Se eliminan todas las capabilities Linux y se activa `no-new-privileges`.
- La publicación HTTP escucha solo en loopback por defecto.
- No existen credenciales, conexiones de datos ni rutas persistentes en Sprint 0.
- `hello_world` no accede a red, archivos ni procesos externos.

La red `ai-platform` debe tratarse como una frontera de confianza operativa. Autenticación,
autorización, auditoría y políticas SQL son trabajo de sprints posteriores; no debe exponerse este
bootstrap directamente a Internet.

## Estado de motores

| Motor | Estado |
|---|---|
| PostgreSQL | Planificado para Sprint 1; no implementado. |
| SQL Server | Planificado para Sprint 9; no implementado. |
| MariaDB/MySQL | Planificado para Sprint 9; no implementado. |
| Informix | Planificado para Sprint 9; sujeto a disponibilidad de driver ARM64. |
| MongoDB | Planificado para Sprint 9 con interfaz documental específica. |
| Oracle | Extensión futura; no implementada. |

## Roadmap

El plan completo se mantiene en [`TASKS.md`](TASKS.md). Próximos hitos principales:

1. Sprint 1: configuración de conexiones y adaptador PostgreSQL de solo lectura.
2. Sprint 2: catálogo y caché de schemas.
3. Sprint 3: validación y ejecución SQL segura.
4. Sprints 4–10: contratos MCP, generación, objetos, RAG, Open WebUI, más motores y hardening.

No se iniciará Sprint 1 hasta que Sprint 0 sea revisado y aprobado.
