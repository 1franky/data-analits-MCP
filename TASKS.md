# Plan de trabajo

Estados permitidos: `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`.

Sprint 6 fue aprobado explícitamente, sus tres historias (HU-601 a HU-603) quedan implementadas en
la rama actual y su validación reproducible se registró más abajo. No se inicia Sprint 7 ni
historias posteriores hasta recibir aprobación explícita.

## Sprint 0 — Descubrimiento, arquitectura y bootstrap

| Historia | Estado | Dependencias | Archivos afectados | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-001 Inicializar proyecto | DONE | Python 3.12, FastAPI, FastMCP | `pyproject.toml`, `app/`, `tests/` | Health, herramienta MCP, pytest, Ruff, mypy | Estructura modular; arranque local; `/health`; calidad reproducible | Ninguno |
| HU-002 Documentar arquitectura | DONE | HU-001, especificación | `README.md`, `docs/architecture.md`, `docs/development.md`, `TASKS.md` | Revisión de enlaces y alcance | Diagrama; flujo; separación generación/ejecución; decisiones MCP/RAG; límites | Ninguno |
| HU-003 Preparar Docker | DONE | HU-001, red externa `ai-platform` | `Dockerfile`, `compose.yaml`, `.env.example`, `.dockerignore` | `compose config`, build, health y usuario efectivo | Imagen construye; contenedor sano; red externa; proceso no-root | Ninguno |

## Sprint 1 — Configuración de conexiones y PostgreSQL

| Historia | Estado | Dependencias | Archivos previstos | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-101 Configurar conexiones por YAML | DONE | Sprint 0 aprobado | `connections.yaml`, `app/config/`, modelos | Config válida/inválida, duplicados, secretos, deshabilitadas | Pydantic valida; secretos desde entorno; errores claros | Ninguno |
| HU-102 Listar conexiones | DONE | HU-101 | `app/services/`, `app/tools/`, modelos | Contrato y ausencia de secretos | ID, nombre, tipo, capacidades y estado sin credenciales | Ninguno |
| HU-103 Probar conexión | DONE | HU-101, adaptador | Servicios/herramientas de conexión | Éxito, timeout y errores redactados | Latencia y error normalizado sin secretos | Ninguno |
| HU-104 Consultar PostgreSQL | DONE | HU-101 | `app/adapters/postgres/`, interfaces base | Schemas, tablas, PK/FK, descripción | Adaptador SQL funcional y tipado | Ninguno |

## Sprint 2 — Catálogo y caché de schemas

| Historia | Estado | Dependencias | Archivos previstos | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-201 Actualizar catálogo | DONE | Sprint 1 | Modelos, `app/services/catalog.py`, repositorio SQLite | Refresh individual/global, error conserva caché | Estado, fecha, errores; nunca datos de negocio | Ninguno |
| HU-202 Consultar catálogo | DONE | HU-201 | Repositorio y herramientas de catálogo | Búsqueda, filtros, relaciones, stale | Busca tablas/columnas; indica obsolescencia | Ninguno |
| HU-203 Refresh periódico | DONE | HU-201 | Scheduler y coordinación | Intervalo, exclusión mutua, fallos | Configurable, observable y sin refresh duplicado | Ninguno |

## Sprint 3 — Validación y ejecución SQL segura

| Historia | Estado | Dependencias | Archivos previstos | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-301 Validar SQL | DONE | Sprint 1, SQLGlot 30.x | `app/security/`, servicio/modelos de validación | DML, DDL, multi-sentencia, CTE de escritura, comentarios | Parser real; clasificación y razones estructuradas | Ninguno |
| HU-302 Ejecutar SELECT | DONE | HU-301, HU-104 | Servicio de ejecución y auditoría | Read-only, timeout, límites, serialización | Solo SQL validado; resultado normalizado y auditado | Ninguno |
| HU-303 Generar escritura sin ejecutarla | DONE | HU-301 | Validación de sentencias suministradas | Demostrar que DML/DDL nunca llega al adaptador | SQL normalizado no ejecutable con advertencia de impacto | Generación en lenguaje natural permanece en Sprint 5 |
| HU-304 Explicar plan | DONE | HU-301, HU-104 | Servicio/tool de explain | Solo lectura; `ANALYZE` ausente | Plan JSON normalizado y seguro | Ninguno |

## Sprint 4 — Herramientas MCP completas

| Historia | Estado | Dependencias | Archivos previstos | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-401 Explorar tablas | DONE | Sprints 1–2 | `app/tools/`, modelos MCP | Contratos, errores, conexión | `list_schemas`, `list_tables`, `describe_table` | Ninguno |
| HU-402 Consultar relaciones | DONE | HU-401 | Herramienta/modelos de relaciones | FK y cardinalidad disponible | Origen, destino y columnas relacionadas | Ninguno |
| HU-403 Contratos versionados | DONE | HU-401–402 | Documentación MCP y modelos | Pruebas de contrato | Versionado y cambios incompatibles registrados | Ninguno |

## Sprint 5 — Generación de consultas mediante lenguaje natural

| Historia | Estado | Dependencias | Archivos previstos | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-501 Generar SQL con metadata | DONE | Sprints 2–4 | Servicio de generación, prompts | JOIN, CTE, ventanas, agregados | Dialecto/contexto real; supuestos y objetos | Ninguno |
| HU-502 Ejecutar lectura generada | DONE | HU-501, Sprint 3 | Orquestación generación/ejecución | SQL bloqueado no ejecuta; errores | Validación obligatoria y resultado completo | Ninguno |
| HU-503 Solicitar aclaraciones | DONE | HU-501 | Modelos de ambigüedad | Nombres similares y opciones | No ejecuta sobre suposición peligrosa | Ninguno |
| HU-504 Generar reportes desde lenguaje natural | DONE | HU-502–503 | `app/reporting/`, modelos y herramientas MCP | Periodos relativos, resultado vacío, XLSX, PDF, CSV y JSON, límites y limpieza | Una petición como «dame las ventas del mes pasado» resuelve y muestra el periodo exacto, ejecuta solo lectura validada y entrega el reporte en el formato solicitado con datos, filtros, fecha de generación y aviso de truncamiento | Ninguno |

## Sprint 6 — Objetos de base de datos y explicaciones

| Historia | Estado | Dependencias | Archivos previstos | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-601 Leer procedimientos | DONE | Adaptador PostgreSQL | Servicio/tool de objetos | Listado/definición; cero ejecución | Parámetros/dependencias cuando existan | Ninguno |
| HU-602 Leer triggers | DONE | Adaptador PostgreSQL | Servicio/tool de triggers | Definición y asociación a tabla | Recupera sin ejecutar | Ninguno |
| HU-603 Explicar objetos | DONE | HU-601–602, flujo LLM | Servicio de explicación | Hechos frente a inferencias | Propósito, entradas, tablas, reglas y riesgos | Ninguno |

## Sprint 7 — RAG documental

| Historia | Estado | Dependencias | Archivos previstos | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-701 Indexar documentación | TODO | Abstracción embeddings/vector store | `app/rag/`, ingesta, Qdrant | Formatos, idempotencia, reindex/delete | Chunks y metadatos configurables | Seleccionar embeddings y versión Qdrant ARM64 |
| HU-702 Buscar documentación | TODO | HU-701 | Servicio/tool de búsqueda | Score, origen y filtros | Resultados citados por conexión/dominio | Espera índice real |
| HU-703 Combinar RAG y catálogo | TODO | HU-702, Sprint 2 | Constructor de contexto | Conflictos y prioridad catálogo | Distingue contexto técnico/funcional | Espera ambos subsistemas |

## Sprint 8 — Integración con Open WebUI

| Historia | Estado | Dependencias | Archivos previstos | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-801 Conectar Open WebUI | TODO | Servidor MCP completo, `ai-platform` | Guía de integración y smoke test | DNS/red y sesión MCP real | Acceso por nombre sin exposición pública | Validar versión/configuración Open WebUI |
| HU-802 Consultar PostgreSQL desde chat | TODO | HU-801, Sprints 1–5 | Pruebas E2E | JOIN completo chat→MCP→DB | SQL válido, validado, ejecutado y explicado | Requiere entorno Open WebUI |
| HU-803 Generar DML sin ejecutarlo | TODO | HU-801, HU-303 | E2E de seguridad | Datos antes/después sin cambios | DELETE visible, bloqueado y auditado | Requiere entorno completo |

## Sprint 9 — Adaptadores adicionales

| Historia | Estado | Dependencias | Archivos previstos | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-901 SQL Server | TODO | Contratos de adaptador estables | `app/adapters/sqlserver/` | Suite de contrato e integración | Capacidades declaradas, sin condicionales centrales | Imagen/driver ARM64 por validar |
| HU-902 MariaDB | TODO | Contratos de adaptador estables | `app/adapters/mariadb/` | Suite de contrato e integración | Dialecto y metadata documentados | Laboratorio por definir |
| HU-903 Informix | TODO | Contratos de adaptador estables | `app/adapters/informix/` | Suite donde driver sea viable | Fallo aislado si driver no disponible | Riesgo alto de driver ARM64 |
| HU-904 MongoDB | TODO | Interfaz documental y políticas | `app/adapters/mongodb/` | find/agregación; `$out`/`$merge` bloqueados | Capacidades documentales, sin interfaz SQL forzada | Diseñar validador específico |

## Sprint 10 — Hardening y operación

| Historia | Estado | Dependencias | Archivos previstos | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-1001 Observabilidad | TODO | Flujos completos | Logs, métricas, endpoints | Latencia, errores, bloqueos, request ID | JSON logs y health/readiness diferenciados | Métricas requieren flujos reales |
| HU-1002 Control de concurrencia | TODO | Ejecución real | Pool, semáforos/backpressure | Carga básica, timeout y límites | Consumo controlado en Free Tier | Dimensionar con mediciones |
| HU-1003 Despliegue seguro | TODO | Sistema completo | Guías/checklists/Compose | Backup, upgrade y rollback | Puertos/secretos mínimos; operación documentada | Requiere persistencias definitivas |

## Evidencia de validación de Sprint 0

Validación ejecutada el 2026-07-14 sobre Docker Desktop ARM64:

```text
Python del target test: PASS — Python 3.12.13, linux/arm64
pytest: PASS — 5 passed in 1.03s
ruff check app tests: PASS — All checks passed
ruff format --check app tests: PASS — 13 files already formatted
mypy app tests: PASS — no issues found in 13 source files
docker compose config --quiet: PASS
docker build --target test: PASS — image sha256:d1121a191bbd...
docker compose build data-platform-mcp: PASS — image sha256:58bb63be2444...
container health: PASS — healthy; GET /health devuelve HTTP 200
MCP sobre ai-platform: PASS — hello_world devuelve Hello, Open WebUI!
runtime user: PASS — uid=10001(app), gid=10001(app)
runtime restrictions: PASS — raíz read-only, red ai-platform
runtime platform: PASS — linux/arm64, 234216757 bytes
```

## Evidencia de validación de Sprint 1

Validación ejecutada el 2026-07-14 sobre Docker Desktop ARM64:

```text
Python del target test: PASS — Python 3.12.13, linux/arm64
pytest: PASS — 29 passed, 2 integration skipped in 2.21s
pytest integration PostgreSQL: PASS — 2 passed, 29 deselected in 2.17s
ruff check app tests: PASS — All checks passed
ruff format --check app tests: PASS — 38 files already formatted
mypy app tests: PASS — no issues found in 38 source files
docker compose config --quiet: PASS
docker build --target test: PASS — image sha256:8c730253dfd...
docker compose build: PASS — MCP sha256:528603875747..., PostgreSQL sha256:76ccd18b65ee...
container health: PASS — ambos servicios healthy; GET /health devuelve versión 0.2.0
MCP sobre ai-platform: PASS — hello_world, list_connections y test_connection disponibles
PostgreSQL metadata: PASS — public; clientes, productos, ventas; columnas, PK y dos FK de ventas
PostgreSQL readonly: PASS — SELECT=true, INSERT=false y escritura bloqueada por integración
runtime user: PASS — uid=10001(app), gid=10001(app)
runtime restrictions: PASS — raíz read-only, red externa ai-platform
runtime platform: PASS — MCP y laboratorio linux/arm64
```

## Evidencia de validación de Sprint 2

Validación ejecutada el 2026-07-14 sobre Docker Desktop ARM64:

```text
Python del target test: PASS — Python 3.12.13, linux/arm64
pytest unitario: PASS — 45 passed, 3 integration deselected in 1.26s
pytest integración PostgreSQL: PASS — 3 passed, 45 deselected in 0.99s
ruff check app tests: PASS — All checks passed
ruff format --check app tests: PASS — 52 files already formatted
mypy app tests: PASS — no issues found in 52 source files
docker compose config --quiet: PASS
docker build --target test: PASS — image sha256:8f7b3f339604...
docker compose build: PASS — MCP sha256:07ee78b2bc1d..., PostgreSQL sha256:61e2fab33e4d...
container health: PASS — ambos servicios healthy; GET /health devuelve versión 0.3.0
MCP sobre ai-platform: PASS — seis tools disponibles; refresh startup y búsqueda reales exitosos
catálogo metadata-only: PASS — clientes/productos/ventas presentes; valores de filas ausentes
persistencia: PASS — volumen catalog-data escribible sobre raíz read-only
runtime user: PASS — uid=10001(app), gid=10001(app)
runtime restrictions: PASS — raíz read-only, cap_drop ALL, no-new-privileges, ai-platform
runtime platform: PASS — MCP y laboratorio linux/arm64
```

## Evidencia de validación de Sprint 3

Validación ejecutada el 2026-07-14 sobre Docker Desktop ARM64:

```text
Python del target test: PASS — Python 3.12.13, linux/arm64
pytest unitario: PASS — 80 passed, 11 integration deselected in 5.45s
pytest integración PostgreSQL: PASS — 11 passed, 80 deselected in 5.31s
ruff check: PASS — All checks passed
ruff format --check: PASS — 68 files already formatted
mypy app tests: PASS — no issues found in 68 source files
docker compose config --quiet: PASS
docker build --target test: PASS — image sha256:45c84310a6bc...
docker compose build/up: PASS — MCP sha256:dd014f539e93..., ambos servicios healthy
seguridad SQL: PASS — DML, DDL, multi-sentencia, CTE de escritura y funciones peligrosas bloqueadas
aislamiento: PASS — sentencias bloqueadas no invocan el adaptador y no alteran filas PostgreSQL
ejecución: PASS — JOIN, CTE, agregación, ventana, parámetros, límites y serialización reales
EXPLAIN: PASS — plan JSON real con ANALYZE desactivado
auditoría: PASS — hash/decisión persistidos; SQL, parámetros y filas ausentes de SQLite
runtime restrictions: PASS — UID 10001, raíz read-only, cap_drop ALL, no-new-privileges
runtime platform: PASS — MCP y laboratorio linux/arm64 sobre red externa ai-platform
```

## Evidencia de validación de Sprint 4

Validación ejecutada el 2026-07-14 sobre Docker Desktop ARM64:

```text
Python del target test: PASS — Python 3.12.13, linux/arm64
pytest unitario/contratos/STDIO: PASS — 92 passed, 11 integration deselected in 15.16s
pytest integración PostgreSQL: PASS — 11 passed, 92 deselected in 8.18s
ruff check: PASS — All checks passed
ruff format --check: PASS — 76 files already formatted
mypy app tests: PASS — no issues found in 75 source files
docker compose config --quiet: PASS
docker build --target test: PASS — image sha256:5dc42ec8f91c...
docker compose build/up: PASS — MCP sha256:4ea1cd7a8f92..., ambos servicios healthy
MCP HTTP smoke: PASS — 15 tools, contrato 1.0.0, refresh y metadata PostgreSQL reales
MCP STDIO: PASS — subproceso lista tools e invoca health_check 0.5.0
metadata: PASS — schemas, tablas, comentarios, PK, índices únicos, FK y cardinalidad inferida
runtime restrictions: PASS — UID 10001, raíz read-only, cap_drop ALL, no-new-privileges
runtime platform: PASS — MCP linux/arm64 sobre red externa ai-platform
```

## Evidencia de validación de Sprint 5

Validación ejecutada el 2026-07-16 sobre Docker Desktop ARM64:

```text
Python del target test: PASS — Python 3.12.13, linux/arm64
pytest unitario/contratos/STDIO: PASS — 180 passed, 11 integration deselected in 4.45s
pytest integración PostgreSQL: PASS — 11 passed, 180 deselected (ejecutado en la red ai-platform)
ruff check: PASS — All checks passed
ruff format --check: PASS — 114 files already formatted
mypy app tests: PASS — no issues found in 114 source files
docker compose config --quiet: PASS
docker build --target test: PASS — image sha256:5f1a07b129ed...
docker compose build/up: PASS — MCP sha256:19a5d1feae70..., ambos servicios healthy, versión 0.6.0
MCP HTTP smoke: PASS — 18 tools (scripts/smoke_mcp.py ampliado), contrato 1.0.0, refresh y metadata
  PostgreSQL reales
MCP STDIO: PASS — subproceso lista tools e invoca health_check
generación SQL: PASS — GenerationService nunca ejecuta sin revalidación completa; SQL generado tipo
  DELETE/INSERT verificado con adapter espía (execute_calls == 0)
aclaraciones: PASS — candidatos inventados por el LLM fuera del catálogo cacheado se descartan;
  clarification nunca coexiste con execution poblado
auditoría de generación/reportes: PASS — ni la pregunta en lenguaje natural ni el SQL aparecen en
  texto plano; solo hash SHA-256 (prompt_hash, query_hash)
reportes: PASS — CSV/JSON/XLSX/PDF exportados en memoria (sin disco); resultado vacío no es error;
  truncamiento por tamaño reduce filas hasta caber; rechazo explícito si ni 0 filas caben
runtime restrictions: PASS — UID 10001, raíz read-only, cap_drop ALL, no-new-privileges
runtime platform: PASS — MCP y laboratorio linux/arm64 sobre red externa ai-platform

Nota: generation.enabled y reporting.enabled quedan en false por defecto (sin proveedor LLM en el
laboratorio local); generate_sql, generate_and_execute_query y generate_report se validan por
contrato MCP (presencia, input/output schema) y por su suite unitaria con FakeLlmProvider, no con
una llamada real a un proveedor LLM en este entorno.
```

## Evidencia de validación de Sprint 6

Validación ejecutada el 2026-07-16 sobre Docker Desktop ARM64:

```text
Python del target test: PASS — Python 3.12.13, linux/arm64
pytest unitario/contratos/STDIO: PASS — 205 passed, 12 integration deselected in 5.97s
pytest integración PostgreSQL: PASS — 12 passed, 205 deselected (ejecutado en la red ai-platform)
ruff check: PASS — All checks passed
ruff format --check: PASS — 122 files already formatted
mypy app tests: PASS — no issues found in 122 source files
docker compose config --quiet: PASS
docker build --target test: PASS — image sha256:4afc835f8472...
docker compose down -v / up: PASS — laboratorio recreado desde volumen vacío para aplicar el seed
  de procedimientos/triggers (database/init/05-demo-objects.sql); ambos servicios healthy, versión
  0.7.0 (imagen sha256:0007a2080b2a...)
MCP HTTP smoke: PASS — 21 tools (scripts/smoke_mcp.py ampliado), contrato 1.0.0
procedimientos/triggers reales: PASS — list_procedures devuelve actualizar_stock_producto y
  resumen_ventas_cliente; list_triggers devuelve trg_ventas_actualiza_stock (AFTER INSERT →
  actualizar_stock_producto), verificado con un cliente MCP real contra el snapshot recién
  refrescado
cero ejecución: PASS — list_procedures/list_triggers solo leen pg_proc/pg_trigger/
  pg_get_functiondef/pg_get_triggerdef; ninguna consulta invoca CALL ni ejecuta el cuerpo del
  objeto; sesión y rol readonly sin cambios
explicación de objetos: PASS — objeto inexistente en el catálogo cacheado nunca llama al proveedor
  LLM (provider.calls == []); trigger solicitado sin table se rechaza antes de tocar catálogo o LLM
auditoría de explicación: PASS — ni la definición SQL real ni el purpose/facts devueltos por el LLM
  aparecen en texto plano en la base de auditoría; solo hash SHA-256 (prompt_hash, query_hash)
runtime restrictions: PASS — UID 10001, raíz read-only, cap_drop ALL, no-new-privileges
runtime platform: PASS — MCP y laboratorio linux/arm64 sobre red externa ai-platform

Nota: generation.enabled queda en false por defecto (sin proveedor LLM real en el laboratorio
local); explain_database_object se valida por contrato MCP y por su suite unitaria con
FakeLlmProvider, igual que generate_sql/generate_report en Sprint 5.
```
