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
- Herramientas MCP `health_check`, `get_connection_capabilities`, `list_schemas`, `list_tables`,
  `describe_table` y `list_relationships`, para un catálogo total de 15 tools.
- Envelopes MCP `1.0.0` con conexión utilizada y frescura del snapshot para exploración de metadata.
- Descubrimiento PostgreSQL de índices únicos simples/completos e inferencia explicable de
  cardinalidad `one-to-one` o `many-to-one` para relaciones FK.
- Transporte MCP local STDIO mediante `data-platform-mcp-stdio`, conservando Streamable HTTP en
  `/mcp` para Open WebUI y otros clientes de red.
- Pruebas de catálogo, schemas JSON de entrada/salida, registro completo de tools y subproceso STDIO.
- Script `scripts/smoke_mcp.py` para validar el contrato contra un despliegue real por red.
- Política de versionado y compatibilidad MCP, catálogo de entradas/salidas y arquitectura Sprint 4.
- Generación de SQL asistida por LLM sobre el catálogo cacheado, con fábrica de proveedores por
  registro y un adaptador `OpenAiCompatibleProvider` vía HTTP genérico, sin acoplar el núcleo a un
  vendor concreto.
- Selección de contexto relevante del catálogo (rankeo por coincidencia de términos y vecinos por
  FK) y construcción de prompts que fuerzan el dialecto y los objetos reales de la conexión.
- Herramientas MCP `generate_sql` y `generate_and_execute_query`, con el SQL generado siempre
  revalidado íntegramente antes de poder ejecutarse.
- Solicitud estructurada de aclaraciones ante ambigüedad, con candidatos groundeados
  exclusivamente contra el catálogo cacheado real.
- Resolución determinística de periodos relativos («el mes pasado», «últimos 7 días», «este
  trimestre», etc.), sin intervención del LLM en el cálculo de fechas.
- Exportadores de reportes CSV, JSON, XLSX y PDF por registro, entregados en línea como bytes
  base64 con límite de tamaño configurable (truncamiento progresivo o rechazo explícito).
- Herramienta MCP `generate_report`, para un catálogo total de 18 tools.
- Pruebas de generación, orquestación, aclaración, periodos, exportadores y reportes, incluida
  verificación explícita de que el SQL bloqueado nunca ejecuta y de que la pregunta y el SQL nunca
  aparecen en texto plano en auditoría.
- Documentación de generación asistida por LLM y reportes en arquitectura y catálogo de
  herramientas MCP.

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
- Generación LLM deshabilitada por defecto; requiere configurar explícitamente
  `generation.provider` y resolver su secreto vía variable de entorno.
- El SQL generado nunca se ejecuta con la validación informativa de generación: se revalida
  íntegramente por el mismo camino que `execute_read_query`.
- Auditoría de generación y reportes con hash SHA-256 de la pregunta y del SQL, nunca su texto ni
  el archivo generado.
- Reportes entregados exclusivamente en memoria (bytes base64 en la respuesta MCP), sin
  almacenamiento temporal en disco ni volumen adicional.

### Fixed

- El target Docker de pruebas conserva `tests/` en el contexto de build.
- La prueba HTTP usa transporte ASGI directo y no genera advertencias deprecatorias de TestClient.
- La prueba periódica del scheduler espera una condición acotada en lugar de depender de una pausa
  fija sensible a carga del host.

### Not implemented

- RAG documental.
- Procedimientos, vistas, triggers y explicaciones de objetos de base de datos.
- Ejecución de escritura de cualquier tipo.
- Autenticación, consulta/retención administrativa de auditoría y métricas operativas.
