# Changelog

Todos los cambios relevantes de este proyecto se documentan en este archivo. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa versionado semántico.

## [Unreleased]

### Added

- Bootstrap de la aplicación para Python 3.12.
- Aplicación ASGI combinada con FastAPI y FastMCP.
- Endpoint de liveness `GET /health`.
- Herramienta MCP `hello_world` sobre Streamable HTTP en `/mcp`.
- Pruebas unitarias del health check, lógica de saludo y registro/invocación MCP.
- Configuración de pytest, Ruff y mypy estricto.
- Imagen Docker multi-stage basada en `python:3.12.13-slim-bookworm` y usuario no-root.
- Compose endurecido y conectado a la red externa `ai-platform`.
- Documentación inicial, arquitectura, guía de desarrollo y plan completo de sprints.
- Carga de `connections.yaml` validada por Pydantic y secretos resueltos desde el entorno.
- Fábrica de adaptadores basada en registro y contrato SQL de metadata.
- Adaptador PostgreSQL para conectividad, schemas, tablas, columnas, PK y FK.
- Herramientas MCP `list_connections` y `test_connection` con respuestas no sensibles.
- Laboratorio PostgreSQL 17 con esquema demo, datos y rol `mcp_readonly`.
- Pruebas unitarias e integración opt-in para configuración, servicios, tools y PostgreSQL.
- Documentación de conexiones, herramientas MCP y seguridad.
- Catálogo de metadata persistente en SQLite con snapshots atómicos por conexión.
- Refresh manual global/individual, refresh periódico no bloqueante y exclusión mutua por conexión.
- Búsqueda por tablas, columnas y comentarios con filtro de conexión, relaciones FK y estado `stale`.
- Herramientas MCP `refresh_schema_cache`, `get_schema_cache_status` y `search_catalog`.
- Filtros configurables de schemas/tablas y comentarios PostgreSQL de tabla/columna.
- Pruebas de expiración, concurrencia, conservación del último caché válido e integración real.
- Validación PostgreSQL basada en el AST de SQLGlot, con clasificación, objetos, parámetros y
  razones estructuradas.
- Herramientas MCP `validate_sql`, `execute_read_query` y `explain_query`.
- Ejecución PostgreSQL readonly con parámetros nombrados, timeout, límite AST de filas, presupuesto
  de bytes, serialización normalizada y control de concurrencia.
- Planes PostgreSQL JSON mediante `EXPLAIN` con `ANALYZE FALSE`.
- Auditoría SQLite de validación/ejecución/plan con hashes y decisiones, sin contenido de consultas.
- Pruebas de ataques, bypass, aislamiento del adaptador e integración de JOIN, CTE, agregaciones,
  ventanas, límites, timeout, escritura bloqueada y planes reales.
- Documentación de política SQL segura, contratos MCP y riesgos residuales de funciones.

### Security

- Publicación del puerto limitada a loopback por defecto.
- Filesystem de contenedor de solo lectura, capabilities eliminadas y `no-new-privileges`.
- Exclusión de `.env` y artefactos locales del contexto Git/Docker.
- Sesiones PostgreSQL readonly, rol sin escritura/DDL y consultas de metadata parametrizadas.
- Allowlist de opciones PostgreSQL y rechazo de campos sensibles dentro de `options`.
- Persistencia exclusiva de metadata técnica; no se consultan ni almacenan filas de negocio.
- Allowlist de lectura sobre AST y bloqueo de DML/DDL, escritura en CTE, múltiples sentencias,
  `SELECT INTO`, locking reads, comandos y funciones PostgreSQL peligrosas conocidas.
- Verificación redundante mediante rol/sesión readonly y rollback explícito por consulta.
- Límites de filas, bytes, tiempo y concurrencia; parámetros SQL separados de los valores.
- Auditoría que omite texto SQL, parámetros, columnas y filas.

### Fixed

- El target Docker de pruebas conserva `tests/` en el contexto de build.
- La prueba HTTP usa transporte ASGI directo y no genera advertencias deprecatorias de TestClient.

### Not implemented

- RAG y generación desde lenguaje natural.
- Ejecución de escritura, procedimientos y triggers.
- Autenticación, consulta/retención administrativa de auditoría y métricas operativas.
