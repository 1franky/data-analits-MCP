# Data Platform MCP

Data Platform MCP es un servicio independiente del proveedor de LLM para explorar fuentes de datos
desde clientes compatibles con Model Context Protocol (MCP), incluido Open WebUI. El proyecto se
construye por sprints y actualmente implementa el **Sprint 4**: exploración MCP completa de
schemas, tablas y relaciones mediante contratos estructurados y versionados, además de las
capacidades seguras de conexión, catálogo y SQL de los sprints anteriores.

No existe todavía generación de consultas desde lenguaje natural, RAG ni ejecución de escritura.
El catálogo nunca almacena filas de negocio y la auditoría guarda metadatos de seguridad, no el SQL,
los parámetros ni los valores devueltos.

## Arquitectura actual

El mismo servidor FastMCP se expone por Streamable HTTP dentro del proceso ASGI y por STDIO para
clientes locales. La superficie pública contiene 15 herramientas:

- `GET /health`: liveness administrativo de FastAPI.
- `/mcp`: transporte MCP Streamable HTTP de FastMCP.
- `health_check`: liveness MCP con versión del servidor y del contrato.
- `hello_world`: herramienta de verificación básica.
- `list_connections`: declaraciones y capacidades sin host, usuario ni secretos.
- `get_connection_capabilities`: capacidades seguras de una conexión identificada.
- `test_connection`: prueba acotada de conectividad con latencia y error normalizado.
- `refresh_schema_cache`: actualiza la metadata de una conexión o de todas las habilitadas.
- `get_schema_cache_status`: informa estado, fecha, error y obsolescencia de cada snapshot.
- `search_catalog`: busca tablas, columnas y descripciones, e incluye relaciones FK relevantes.
- `list_schemas`: lista schemas del snapshot de una conexión.
- `list_tables`: lista tablas cacheadas, con filtro opcional por schema.
- `describe_table`: devuelve columnas, comentarios, PK, índices únicos y FK.
- `list_relationships`: devuelve origen, destino, columnas y cardinalidad inferida de cada FK.
- `validate_sql`: parsea, clasifica y explica por qué una sentencia puede o no ejecutarse.
- `execute_read_query`: ejecuta un único `SELECT` validado con límites de tiempo, filas y bytes.
- `explain_query`: devuelve el plan JSON de un `SELECT` sin utilizar `ANALYZE`.

La configuración pasa por Pydantic, el servicio resuelve secretos desde el entorno y una fábrica por
registro crea el adaptador. `CatalogService` coordina snapshots atómicos guardados en SQLite;
`QueryValidationService` aplica una política AST por dialecto y `QueryExecutionService` es la única
entrada a consultas de usuario. Consulta [la arquitectura](docs/architecture.md),
[los contratos MCP](docs/mcp-contracts.md), [la seguridad SQL](docs/query-security.md) y
[la operación del catálogo](docs/catalog.md).

## Requisitos

- Docker Engine 24 o posterior.
- Docker Compose v2.20 o posterior.
- Red Docker externa `ai-platform` creada previamente.
- Para desarrollo sin Docker: Python 3.12 y un entorno virtual.

Las imágenes `python:3.12.13-slim-bookworm` y `postgres:17.10-bookworm` disponen de variantes
Linux ARM64. El proyecto no usa rutas absolutas del anfitrión y es desplegable en Oracle Cloud Free
Tier ARM64, sujeto al dimensionamiento y monitoreo propios del entorno.

## Inicio rápido con Docker

```bash
cp .env.example .env
# Cambia ambas contraseñas de laboratorio dentro de .env.
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
  "version": "0.5.0"
}
```

El puerto MCP se publica en `127.0.0.1:8000` por defecto y PostgreSQL en
`127.0.0.1:5432`. Los contenedores de `ai-platform` usan estas URLs internas:

```text
MCP:        http://data-platform-mcp:8000/mcp
PostgreSQL: postgres-lab:5432
```

Open WebUI puede permanecer en otro proyecto Compose: solo necesita compartir `ai-platform`.

Para un cliente MCP local, el entry point instalado inicia exactamente el mismo catálogo de tools
por STDIO:

```bash
data-platform-mcp-stdio
```

Para eliminar también los datos desechables del laboratorio:

```bash
docker compose down --volumes
```

## Configuración de conexiones

`connections.yaml` contiene declaraciones sin contraseña. Cada `password_env` indica qué variable
de entorno debe proporcionar el secreto al proceso:

```yaml
connections:
  - id: postgres-demo
    name: PostgreSQL Demo
    type: postgres
    host: postgres-lab
    port: 5432
    database: demo
    username: mcp_readonly
    password_env: POSTGRES_DEMO_PASSWORD
    readonly: true
    enabled: true
    connect_timeout_seconds: 10
    query_timeout_seconds: 30
    max_rows: 500
    options:
      application_name: data-platform-mcp
      sslmode: disable
```

El archivo se monta como solo lectura, por lo que puede cambiarse sin reconstruir la imagen. El
proceso debe reiniciarse para cargar la nueva configuración. IDs duplicados, valores fuera de rango,
opciones reservadas, conexiones habilitadas sin modo readonly, motores sin adaptador o secretos
ausentes detienen el arranque con un error claro. La referencia completa está en
[conexiones](docs/connections.md).

La sección raíz `catalog` controla si el caché está activo, el refresh al arrancar, el intervalo,
la edad para marcarlo obsoleto y los filtros de schemas/tablas. El ejemplo usa 60 minutos entre
actualizaciones y marca el snapshot como `stale` a partir de 120 minutos. SQLite se persiste en el
volumen nombrado `catalog-data`; `docker compose down --volumes` también lo elimina.

Las secciones `query` y `audit` controlan los límites globales y la bitácora de seguridad:

```yaml
query:
  global_max_rows: 1000
  max_serialized_bytes: 1000000
  max_concurrent_queries: 4

audit:
  enabled: true
```

La ejecución utiliza el menor límite entre la solicitud, la conexión y la política global. Los
placeholders deben ser nombrados, por ejemplo `%(cliente_id)s`, y el diccionario de parámetros debe
coincidir exactamente. La auditoría se persiste en `/app/data/audit.db` dentro del mismo volumen.

Variables Compose incluidas en `.env.example`:

| Variable | Predeterminado de ejemplo | Uso |
|---|---:|---|
| `AI_PLATFORM_NETWORK` | `ai-platform` | Red externa compartida con Open WebUI. |
| `MCP_BIND_ADDRESS` | `127.0.0.1` | Interfaz local del MCP/API. |
| `MCP_PORT` | `8000` | Puerto local del MCP/API. |
| `LOG_LEVEL` | `info` | Nivel de log de Uvicorn. |
| `IMAGE_TAG` | `0.5.0` | Etiqueta local de la imagen. |
| `CATALOG_DB_PATH` | `/app/data/catalog.db` | SQLite persistente de metadata técnica. |
| `AUDIT_DB_PATH` | `/app/data/audit.db` | SQLite persistente de eventos SQL sin contenido sensible. |
| `POSTGRES_IMAGE_TAG` | `17.10` | Etiqueta local del laboratorio PostgreSQL. |
| `POSTGRES_LAB_ADMIN_PASSWORD` | valor local no secreto | Administrador del laboratorio. |
| `POSTGRES_DEMO_PASSWORD` | valor local no secreto | Rol `mcp_readonly` y adaptador. |
| `POSTGRES_LAB_BIND_ADDRESS` | `127.0.0.1` | Interfaz local de PostgreSQL. |
| `POSTGRES_LAB_PORT` | `5432` | Puerto local de PostgreSQL. |

Los valores de `.env.example` son marcadores para desarrollo local, no credenciales aptas para
producción.

## Desarrollo y validación

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Validaciones reproducibles mediante Docker:

```bash
docker build --target test -t data-platform-mcp:test .
docker run --rm data-platform-mcp:test pytest
docker run --rm data-platform-mcp:test ruff check app tests scripts
docker run --rm data-platform-mcp:test ruff format --check app tests scripts
docker run --rm data-platform-mcp:test mypy app tests
docker compose --env-file .env.example config --quiet
docker compose --env-file .env.example build data-platform-mcp
```

Con el stack activo, el smoke test de red refresca el catálogo y llama las herramientas de
exploración reales:

```bash
docker run --rm --network ai-platform \
  data-platform-mcp:test \
  python scripts/smoke_mcp.py --url http://data-platform-mcp:8000/mcp
```

Las pruebas de integración requieren el laboratorio y se habilitan explícitamente; consulta
[desarrollo](docs/development.md).

## Seguridad

- El MCP utiliza `mcp_readonly`, nunca el superusuario del laboratorio.
- El rol tiene `SELECT` y `default_transaction_read_only=on`; no recibe escritura ni DDL.
- El adaptador fuerza además sesiones de solo lectura.
- SQLGlot parsea PostgreSQL y solo permite una raíz de lectura; bloquea DML, DDL, escritura en CTE,
  sentencias múltiples, bloqueos, comandos administrativos y funciones peligrosas conocidas.
- La ejecución revalida siempre, usa parámetros nombrados y aplica límites de timeout, filas, bytes
  serializados y concurrencia.
- `EXPLAIN` fija `ANALYZE FALSE`; una solicitud no puede inyectar sus propias opciones de plan.
- La auditoría guarda hash SHA-256, decisión, razones, duración y conteo, nunca SQL o resultados.
- El caché persiste únicamente schemas, tablas, columnas, comentarios, PK, índices únicos y FK.
- Contraseñas y cadenas completas no aparecen en herramientas ni errores normalizados.
- El runtime usa UID/GID `10001`, raíz de solo lectura, sin capabilities y sin privilegios nuevos.
- Los puertos se publican solo en loopback por defecto.

Esta defensa en profundidad no sustituye autenticación MCP ni segmentación de red. No expongas el
servicio directamente a Internet. Consulta [seguridad](docs/security.md).

## Estado de motores

| Motor | Estado |
|---|---|
| PostgreSQL | Sprint 4: exploración MCP versionada, catálogo, SELECT validado y EXPLAIN seguro. |
| SQL Server | Planificado para Sprint 9. |
| MariaDB/MySQL | Planificado para Sprint 9. |
| Informix | Planificado para Sprint 9; driver ARM64 por validar. |
| MongoDB | Planificado para Sprint 9 con interfaz documental. |
| Oracle | Extensión futura. |

## Roadmap

El plan se mantiene en [TASKS.md](TASKS.md). El siguiente hito, que no se iniciará sin aprobación,
es Sprint 5: generación de consultas mediante lenguaje natural usando metadata real. Después siguen
objetos, RAG, Open WebUI, motores adicionales y hardening.
