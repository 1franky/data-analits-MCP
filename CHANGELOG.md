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
- Lectura cacheada de procedimientos/funciones y triggers PostgreSQL (`pg_proc`/`pg_trigger`,
  DDL real vía `pg_get_functiondef`/`pg_get_triggerdef`), integrada al mismo snapshot y refresh
  del catálogo de Sprint 2.
- Herramientas MCP `list_procedures` y `list_triggers`, con la misma garantía de solo lectura del
  snapshot cacheado que el resto de tools de exploración.
- Explicación en lenguaje natural de procedimientos y triggers vía LLM (`explain_database_object`),
  reutilizando el proveedor opcional de Sprint 5, separando explícitamente hechos verificables de
  la definición real frente a inferencias del modelo.
- Herramienta MCP `explain_database_object`, para un catálogo total de 21 tools.
- Pruebas de adaptador, catálogo, contrato MCP, prompting/parsing de explicación y del servicio de
  explicación, incluida verificación explícita de que un objeto inexistente nunca invoca al LLM y
  de que la definición y la explicación nunca aparecen en texto plano en auditoría.
- Laboratorio PostgreSQL con función y trigger de ejemplo (`resumen_ventas_cliente`,
  `trg_ventas_actualiza_stock`) y sus permisos `EXECUTE` explícitos para `mcp_readonly`.
- Documentación de procedimientos, triggers y explicación de objetos en arquitectura, catálogo y
  catálogo de herramientas MCP.
- Subsistema RAG documental desacoplado (`app/rag/`): abstracción de proveedor de embeddings
  (fábrica por registro, `OpenAiCompatibleEmbeddingProvider`), independiente del proveedor de
  generación de SQL de Sprint 5.
- Ingesta de documentación desde un directorio montado de solo lectura (`.md`, `.txt`, `.sql`,
  `.json`, `.yaml`), con derivación de `connection_id`/`domain`/`document_type`/`version` desde
  segmentos de directorio `clave=valor`, chunking configurable con overlap, e indexación idempotente
  por hash de contenido (un documento sin cambios no recalcula embeddings).
- Vector store Qdrant (`app/repositories/qdrant_vector_store.py`) con colecciones versionadas por
  fingerprint de modelo/dimensión de embeddings, evitando mezclar vectores incompatibles.
- Herramientas MCP `search_documents`, `list_indexed_documents`, `refresh_document_index` y
  `delete_indexed_document`, para un catálogo total de 25 tools.
- Reindexación periódica no bloqueante del directorio de documentos (`DocumentIndexScheduler`,
  mismo patrón que `CatalogScheduler`).
- Pruebas de embeddings, ingesta, repositorios, servicios, scheduler, contrato MCP e integración
  real contra Qdrant, incluida verificación explícita de reemplazo completo de vectores al
  reindexar (sin fragmentos huérfanos) y de que ni el contenido de documentos ni el texto de
  búsquedas aparecen en texto plano en auditoría.
- Documentación de RAG documental (`docs/rag.md`), incluido el patrón de uso combinado con el
  catálogo técnico (HU-703).
- Documentos de ejemplo en `documents/` que ejercitan la convención de organización por carpetas.
- Guía de integración con Open WebUI (`docs/openwebui-integration.md`) como cliente MCP nativo por
  Streamable HTTP, sin proxy ni bridge intermedio, incluyendo ejemplos de prompts para consultar
  PostgreSQL desde el chat y para generar DML sin ejecutarlo.
- Compose de ejemplo aislado (`examples/openwebui/`) para validar la integración localmente, sin
  acoplar el código del proyecto al contenedor de Open WebUI.
- Script `scripts/smoke_openwebui.py` que verifica de forma automatizada que Open WebUI alcanza
  `data-platform-mcp` por nombre de servicio en `ai-platform`, sin depender de un proveedor LLM real.
- Segundo adaptador SQL, MariaDB (`MariaDbAdapter`), reutilizando exactamente las mismas tools
  `validate_sql`/`execute_read_query`/`explain_query`/`list_schemas`/`list_tables`/
  `describe_table`/`list_procedures`/`list_triggers` ya existentes, sin tools nuevas.
- Generalización de `QueryValidationService` para despachar dialecto SQLGlot y política de
  funciones peligrosas por motor (`postgres` → dialecto `postgres`; `mariadb` → dialecto `mysql`),
  sin cambiar el comportamiento observable de PostgreSQL.
- `MariaDbSqlPolicy` con denylist de funciones peligrosas MySQL/MariaDB (`LOAD_FILE`, `SLEEP`,
  `BENCHMARK`, `GET_LOCK`/`RELEASE_LOCK`, etc.).
- Laboratorio MariaDB (`database/init-mariadb/`) con el mismo esquema/datos demo que PostgreSQL
  (clientes/productos/ventas), procedimiento y trigger equivalentes, y rol `mcp_readonly` solo
  `SELECT`/`SHOW VIEW`.
- Primer adaptador documental, MongoDB (`MongoDbAdapter`), con una interfaz propia
  `DocumentDatabaseAdapter` que nunca declara ni implementa un método de escritura — la garantía de
  solo lectura es estructural, no una comprobación en tiempo de ejecución.
- `MongoOperatorPolicy`, allowlist fail-closed de etapas de pipeline y operadores `$...`; `$out`,
  `$merge`, `$function`, `$accumulator` y `$where` quedan bloqueados por diseño.
- `DocumentQueryValidationService` y `DocumentQueryExecutionService`, mismo principio de
  revalidación completa e independiente que `QueryExecutionService`: ninguna consulta bloqueada
  llega al adaptador.
- Herramientas MCP `list_mongo_collections`, `validate_mongo_query`, `execute_mongo_find` y
  `execute_mongo_aggregate`, para un catálogo total de 29 tools.
- Laboratorio MongoDB (`database/init-mongo/`) con colecciones demo equivalentes
  (clientes/productos/ventas con `_id` enteros simples) y usuario con rol `read` únicamente.
- Documentación de la política documental (`docs/document-security.md`), y actualización de
  `docs/connections.md`/`docs/query-security.md` con el modelo multi-dialecto.
- Pruebas de validación documental, adaptador MongoDB, contrato MCP e integración real contra
  MariaDB y MongoDB, incluida verificación explícita de que las escrituras con las credenciales
  `mcp_readonly` fallan en el servidor (no solo en el cliente) en ambos motores nuevos.
- Logs JSON estructurados (stdlib `logging`, sin dependencia nueva) para el proceso y los loggers
  de uvicorn, con `request_id` correlacionado vía middleware ASGI puro y header `X-Request-Id`.
- Logs de auditoría (`audit_event`) emitidos junto a cada registro persistido en `audit.db`,
  reutilizando solo campos no sensibles ya existentes.
- Endpoint `GET /ready`, distinto de `GET /health`, que reporta readiness real (conexiones,
  catálogo, índice documental) sin abrir conexiones nuevas en cada llamada.
- Endpoint `GET /metrics` en formato Prometheus/OpenMetrics (`prometheus_client`), con contadores,
  histogramas y gauges de solicitudes, duración, espera de capacidad y bloqueos por motor/operación,
  más métricas de memoria/CPU del proceso.
- Campo `queue_wait_seconds` en la política de consultas: el semáforo de concurrencia admite espera
  acotada configurable antes de rechazar (`QUERY_CAPACITY_EXCEEDED`); por defecto `0`, idéntico al
  comportamiento de rechazo inmediato de sprints anteriores.
- Límites de recursos Docker (`deploy.resources.limits`, cpus/memory) en los 5 servicios de
  `compose.yaml`, como punto de partida para Oracle Cloud Free Tier.
- Scripts `scripts/backup_volume.sh`/`scripts/restore_volume.sh` para respaldar y restaurar
  cualquiera de los 5 volúmenes nombrados vía un contenedor auxiliar de solo lectura.
- Guía de operación (`docs/operations.md`): procedimientos de backup, restore, upgrade y rollback
  basados en el mecanismo `*_IMAGE_TAG` ya existente, y checklist de puertos/secretos.

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
- `list_procedures`/`list_triggers` consultan exclusivamente catálogos internos de PostgreSQL de
  solo lectura (`pg_proc`, `pg_trigger`, funciones `pg_get_*def`); ninguna consulta invoca `CALL`
  ni ejecuta el cuerpo del objeto listado o explicado.
- Filtro por privilegio (`has_function_privilege`/`has_table_privilege`) sobre procedimientos y
  triggers, coherente con el resto de metadata cacheada.
- `explain_database_object` reutiliza `generation.provider`/`generation.enabled` de Sprint 5 (sin
  segunda superficie de configuración de secretos) y audita solo hash SHA-256 de la definición y
  de la explicación generada, nunca su texto.
- RAG deshabilitado por defecto; requiere configurar explícitamente `rag.embedding_provider` y
  resolver su secreto vía variable de entorno, independiente del secreto de `generation.provider`.
- Directorio de documentos montado de solo lectura (`./documents:/app/documents:ro`); ningún tool
  MCP escribe en ese volumen.
- `upsert_chunks` reemplaza siempre el conjunto completo de vectores de un documento (borrado por
  `document_id` antes de insertar), evitando fragmentos huérfanos de una versión anterior más larga.
- Auditoría de indexación y búsqueda con hash SHA-256 del contenido/pregunta, nunca su texto ni los
  fragmentos recuperados.
- Si `rag.enabled=true` y Qdrant no responde al arrancar, el proceso falla el arranque completo
  (mismo criterio fail-fast que la validación de conexiones PostgreSQL).
- Open WebUI se conecta al MCP sin autenticación propia (limitación conocida ya documentada); la
  red `ai-platform` sigue siendo la única frontera de confianza, y el compose de ejemplo no expone
  el MCP públicamente.
- Rol MariaDB `mcp_readonly` con `SELECT`/`SHOW VIEW` únicamente, sesión `SET SESSION TRANSACTION
  READ ONLY` y `max_statement_time` acotado; verificado con un intento de escritura real que el
  servidor rechaza, no solo el cliente.
- Rol MongoDB `mcp_readonly` con el rol `read` únicamente (nunca `readWrite`/`dbAdmin`), combinado
  con que `DocumentDatabaseAdapter` nunca declara un método de escritura — doble garantía
  independiente, verificada con un intento de escritura real que el servidor rechaza.
- `execute_mongo_aggregate` añade `{"$limit": max_rows}` al pipeline validado antes de ejecutar,
  como defensa adicional independiente de la validación previa.
- Auditoría de consultas documentales con hash SHA-256 del filtro/pipeline serializado, nunca su
  contenido.
- SQL Server e Informix permanecen sin adaptador ni imagen de laboratorio: SQL Server no publica
  imagen Docker ARM64 nativa e Informix no tiene soporte ARM64 confirmado para versiones modernas.
- `GET /metrics` y `GET /ready` no tienen autenticación propia, mismo modelo de confianza que
  `GET /health` y las tools MCP: la red `ai-platform` sigue siendo la única frontera.

### Fixed

- El target Docker de pruebas conserva `tests/` en el contexto de build.
- La prueba HTTP usa transporte ASGI directo y no genera advertencias deprecatorias de TestClient.
- La prueba periódica del scheduler espera una condición acotada en lugar de depender de una pausa
  fija sensible a carga del host.

### Not implemented

- Vistas y vistas materializadas como objetos explorables o explicables.
- Ejecución de escritura de cualquier tipo.
- Autenticación y consulta/retención administrativa de auditoría (las métricas operativas ya se
  cubren desde Sprint 10 vía `GET /metrics`).
- Pool de conexiones real a base de datos (cada operación sigue abriendo y cerrando su propia
  conexión) y gestión nativa de secretos de producción (Vault, Docker secrets).
- Embeddings locales, formatos de documento adicionales (PDF y otros) más allá de
  `.md`/`.txt`/`.sql`/`.json`/`.yaml`.
- Demostración end-to-end automatizada de HU-802/HU-803 (requiere un proveedor LLM real dentro de
  Open WebUI; queda como runbook manual en `docs/openwebui-integration.md`).
- SQL Server e Informix (Sprint 9, `BLOCKED`): sin imagen Docker ARM64 nativa confirmada.
- Explicación LLM de objetos y generación de SQL asistida por LLM para MongoDB (motor documental,
  fuera del pipeline SQL de Sprint 5/6). MariaDB sí funciona con ambas capacidades sin cambios de
  código: `GenerationService`/`ObjectExplanationService` ya eran genéricos sobre `connection.type`.
