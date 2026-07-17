# Catálogo y caché de schemas

## Contenido del snapshot

Cada conexión SQL (PostgreSQL, MariaDB desde Sprint 9) tiene como máximo un snapshot válido con
fecha, hash SHA-256, schemas, tablas, comentarios de tablas/columnas, tipos, nulabilidad, defaults,
claves primarias, índices únicos simples/completos, claves foráneas, procedimientos/funciones y
triggers. El adaptador consulta exclusivamente catálogos internos de cada motor
(`pg_catalog`/`information_schema` en PostgreSQL, `information_schema` en MariaDB). No se ejecuta
`SELECT` sobre tablas de negocio, no se invoca el cuerpo de ningún procedimiento o trigger, y no se
almacenan filas de negocio. MongoDB no participa de este catálogo: es un motor documental sin
schema fijo, con sus propias tools (`list_mongo_collections`) — ver
[document-security.md](document-security.md).

Procedimientos y triggers (Sprint 6) heredan `excluded_schemas` igual que las tablas: un motor sin
capacidad declarada (`list_procedures`/`list_triggers` en `False`) simplemente no aporta esos
objetos al snapshot, sin error. Su definición SQL real (DDL vía `pg_get_functiondef`/
`pg_get_triggerdef` en PostgreSQL, `SHOW CREATE FUNCTION`/`PROCEDURE` en MariaDB) se cachea junto
al resto de metadata y es la fuente que consume `explain_database_object` para explicarlos, sin una
segunda conexión a la base.

Los índices únicos permiten inferir la cardinalidad máxima origen→destino de una FK. Coincidencia
con PK o índice único produce `one-to-one`; sin unicidad declarada produce `many-to-one`. Índices
parciales, de expresión, inválidos y columnas `INCLUDE` se excluyen de la inferencia.

## Actualización

Hay tres disparadores equivalentes:

- manual individual: `refresh_schema_cache(connection_id=...)`;
- manual global: `refresh_schema_cache()` sobre conexiones habilitadas;
- periódico: scheduler del proceso, opcionalmente también al arrancar.

El servicio adquiere un lock no bloqueante por conexión. Si ya existe una actualización de esa
conexión, responde `already_running`; no espera ni inicia otra. Tras recopilar y filtrar metadata,
calcula un hash canónico y sustituye el snapshot junto con el estado `success` en una transacción.

Si PostgreSQL, el adaptador o la recopilación fallan, el estado pasa a `error` con fecha y código
normalizado. La fila de snapshot no se modifica, por lo que búsqueda y consumidores pueden seguir
usando el último valor válido y advertir el error mediante `cache_statuses`.

## Frescura

Un snapshot es `stale` cuando no existe o su edad es mayor o igual a `stale_after_minutes`. La
caducidad es informativa: no borra metadata ni fuerza una conexión durante una búsqueda. El estado
del último intento y la frescura del último éxito son conceptos separados; por eso puede existir
`state=error`, `has_snapshot=true` y `stale=false` simultáneamente.

## Filtros

`excluded_schemas` usa nombres exactos sin distinguir mayúsculas. `include_table_patterns` y
`exclude_table_patterns` usan globs (`fnmatch`) contra `tabla` y `schema.tabla`; exclusión tiene
prioridad. Los patrones distinguen mayúsculas, coherente con identificadores PostgreSQL tal como
los devuelve el catálogo.

## Persistencia

`CATALOG_DB_PATH` elige el archivo SQLite, por defecto `/app/data/catalog.db`. Compose persiste ese
directorio en `catalog-data`. SQLite usa WAL, espera acotada ante contención y sentencias
parametrizadas. Al iniciar, un estado `refreshing` abandonado por un reinicio se convierte en
`error/REFRESH_INTERRUPTED`, sin descartar el snapshot anterior.

Para reiniciar sólo el caché en el laboratorio, detén el proyecto y elimina el volumen
`catalog-data`. `docker compose down --volumes` elimina además los datos PostgreSQL del laboratorio.

## Operación

El endpoint `/health` sólo confirma que el proceso responde. Para observar el catálogo usa
`get_schema_cache_status`; revisa `state`, `last_attempt_completed_at`, `last_refreshed_at`,
`stale`, `error_code` y `message`. El scheduler trabaja en un thread mediante `asyncio.to_thread`,
por lo que la lectura MCP/HTTP no queda bloqueada durante una conexión lenta.

`list_schemas`, `list_tables`, `describe_table` y `list_relationships` consultan el último snapshot
válido y devuelven su `cache_status`. No disparan una conexión implícita. Si no existe snapshot, el
cliente debe ejecutar `refresh_schema_cache` y volver a intentar.

Este diseño asume una instancia del servicio. Antes de escalar horizontalmente se necesita un
repositorio compartido y un lock distribuido; esa ampliación no pertenece al Sprint 2.
