# Plan de trabajo

Estados permitidos: `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`.

Sprint 0 es el único autorizado en la rama actual. Los archivos y pruebas de sprints posteriores son
planificación, no implementaciones existentes.

## Sprint 0 — Descubrimiento, arquitectura y bootstrap

| Historia | Estado | Dependencias | Archivos afectados | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-001 Inicializar proyecto | DONE | Python 3.12, FastAPI, FastMCP | `pyproject.toml`, `app/`, `tests/` | Health, herramienta MCP, pytest, Ruff, mypy | Estructura modular; arranque local; `/health`; calidad reproducible | Ninguno |
| HU-002 Documentar arquitectura | DONE | HU-001, especificación | `README.md`, `docs/architecture.md`, `docs/development.md`, `TASKS.md` | Revisión de enlaces y alcance | Diagrama; flujo; separación generación/ejecución; decisiones MCP/RAG; límites | Ninguno |
| HU-003 Preparar Docker | DONE | HU-001, red externa `ai-platform` | `Dockerfile`, `compose.yaml`, `.env.example`, `.dockerignore` | `compose config`, build, health y usuario efectivo | Imagen construye; contenedor sano; red externa; proceso no-root | Ninguno |

## Sprint 1 — Configuración de conexiones y PostgreSQL

| Historia | Estado | Dependencias | Archivos previstos | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-101 Configurar conexiones por YAML | TODO | Sprint 0 aprobado | `connections.yaml`, `app/config/`, modelos | Config válida/inválida, duplicados, secretos, deshabilitadas | Pydantic valida; secretos desde entorno; errores claros | Espera aprobación Sprint 0 |
| HU-102 Listar conexiones | TODO | HU-101 | `app/services/`, `app/tools/`, modelos | Contrato y ausencia de secretos | ID, nombre, tipo, capacidades y estado sin credenciales | Espera HU-101 |
| HU-103 Probar conexión | TODO | HU-101, adaptador | Servicios/herramientas de conexión | Éxito, timeout y errores redactados | Latencia y error normalizado sin secretos | Requiere DB/driver real |
| HU-104 Consultar PostgreSQL | TODO | HU-101 | `app/adapters/postgres/`, interfaces base | Schemas, tablas, PK/FK, descripción | Adaptador SQL funcional y tipado | Requiere laboratorio PostgreSQL ARM64 |

## Sprint 2 — Catálogo y caché de schemas

| Historia | Estado | Dependencias | Archivos previstos | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-201 Actualizar catálogo | TODO | Sprint 1 | `app/catalog/`, `app/services/catalog.py` | Refresh individual/global, error conserva caché | Estado, fecha, errores; nunca datos de negocio | Espera adaptador PostgreSQL |
| HU-202 Consultar catálogo | TODO | HU-201 | Repositorio y herramientas de catálogo | Búsqueda, filtros, relaciones, stale | Busca tablas/columnas; indica obsolescencia | Espera HU-201 |
| HU-203 Refresh periódico | TODO | HU-201 | Scheduler y coordinación | Intervalo, exclusión mutua, fallos | Configurable, observable y sin refresh duplicado | Espera persistencia de catálogo |

## Sprint 3 — Validación y ejecución SQL segura

| Historia | Estado | Dependencias | Archivos previstos | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-301 Validar SQL | TODO | Sprint 1, parser seleccionado | `app/security/`, servicio/modelos de validación | DML, DDL, multi-sentencia, CTE de escritura, comentarios | Parser real; clasificación y razones estructuradas | Seleccionar/versionar parser |
| HU-302 Ejecutar SELECT | TODO | HU-301, HU-104 | Servicio de ejecución y auditoría | Read-only, timeout, límites, serialización | Solo SQL validado; resultado normalizado y auditado | Requiere usuario DB read-only |
| HU-303 Generar escritura sin ejecutarla | TODO | HU-301 | Caso de uso de generación | Demostrar que DML/DDL nunca llega al adaptador | SQL marcado no ejecutable con impacto | Generación LLM se define después |
| HU-304 Explicar plan | TODO | HU-301, HU-104 | Servicio/tool de explain | Solo lectura; `ANALYZE` ausente | Plan textual/normalizado seguro | Espera adaptador y validador |

## Sprint 4 — Herramientas MCP completas

| Historia | Estado | Dependencias | Archivos previstos | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-401 Explorar tablas | TODO | Sprints 1–2 | `app/tools/`, modelos MCP | Contratos, errores, conexión | `list_schemas`, `list_tables`, `describe_table` | Espera catálogo/adaptador |
| HU-402 Consultar relaciones | TODO | HU-401 | Herramienta/modelos de relaciones | FK y cardinalidad disponible | Origen, destino y columnas relacionadas | Espera metadata real |
| HU-403 Contratos versionados | TODO | HU-401–402 | Documentación MCP y modelos | Pruebas de contrato | Versionado y cambios incompatibles registrados | Espera catálogo de tools |

## Sprint 5 — Generación de consultas mediante lenguaje natural

| Historia | Estado | Dependencias | Archivos previstos | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-501 Generar SQL con metadata | TODO | Sprints 2–4 | Servicio de generación, prompts | JOIN, CTE, ventanas, agregados | Dialecto/contexto real; supuestos y objetos | Decidir contrato LLM sin acoplar proveedor |
| HU-502 Ejecutar lectura generada | TODO | HU-501, Sprint 3 | Orquestación generación/ejecución | SQL bloqueado no ejecuta; errores | Validación obligatoria y resultado completo | Espera HU-301–302 |
| HU-503 Solicitar aclaraciones | TODO | HU-501 | Modelos de ambigüedad | Nombres similares y opciones | No ejecuta sobre suposición peligrosa | Requiere catálogo poblado |

## Sprint 6 — Objetos de base de datos y explicaciones

| Historia | Estado | Dependencias | Archivos previstos | Pruebas requeridas | Criterios de aceptación | Bloqueos |
|---|---|---|---|---|---|---|
| HU-601 Leer procedimientos | TODO | Adaptador PostgreSQL | Servicio/tool de objetos | Listado/definición; cero ejecución | Parámetros/dependencias cuando existan | Espera soporte adaptador |
| HU-602 Leer triggers | TODO | Adaptador PostgreSQL | Servicio/tool de triggers | Definición y asociación a tabla | Recupera sin ejecutar | Espera soporte adaptador |
| HU-603 Explicar objetos | TODO | HU-601–602, flujo LLM | Servicio de explicación | Hechos frente a inferencias | Propósito, entradas, tablas, reglas y riesgos | Definir integración LLM |

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
