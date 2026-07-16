# Herramientas MCP disponibles

El catálogo contiene 21 tools y es idéntico por Streamable HTTP en `/mcp` y por STDIO mediante
`data-platform-mcp-stdio`. Los modelos se serializan como datos estructurados. Los envelopes
añadidos en Sprint 4, Sprint 5 y Sprint 6 incluyen `contract_version: "1.0.0"`; consulta la
[política de compatibilidad](mcp-contracts.md). No existe ninguna herramienta que ejecute
escrituras ni que invoque el cuerpo de un procedimiento o trigger.

## `hello_world`

Verifica que la sesión MCP puede listar e invocar herramientas.

- Parámetro: `name: str = "world"`.
- Respuesta: `{"message": "Hello, <name>!"}`.
- Acceso externo: ninguno.

## `health_check`

Verifica el proceso MCP sin depender de PostgreSQL ni del catálogo.

- Parámetros: ninguno.
- Respuesta: `contract_version`, `status`, `service` y `server_version`.
- `status` actual: `ok`.
- Acceso externo: ninguno.

```json
{
  "contract_version": "1.0.0",
  "status": "ok",
  "service": "data-platform-mcp",
  "server_version": "0.7.0"
}
```

## `list_connections`

Lista conexiones en orden por ID.

- Parámetros: ninguno.
- Respuesta por elemento: `id`, `name`, `type`, `database`, `enabled`, `readonly` y
  `capabilities`.
- Excluye: host, username, `password_env`, password y connection string.
- Una conexión deshabilitada aparece con `enabled: false` y no puede usarse.

Ejemplo conceptual:

```json
[
  {
    "id": "postgres-demo",
    "name": "PostgreSQL Demo",
    "type": "postgres",
    "database": "demo",
    "enabled": true,
    "readonly": true,
    "capabilities": {
      "query_language": "sql",
      "test_connection": true,
      "list_schemas": true,
      "list_tables": true,
      "describe_table": true,
      "primary_keys": true,
      "foreign_keys": true,
      "execute_read_query": true,
      "explain_query": true
    }
  }
]
```

## `get_connection_capabilities`

Obtiene la declaración segura y matriz de capacidades de una conexión concreta.

- Parámetro requerido: `connection_id`.
- Respuesta: `contract_version`, `connection_id` y `connection`.
- `connection` tiene la misma forma no sensible que un elemento de `list_connections`.
- Error entendible si el ID no existe; nunca resuelve ni devuelve el secreto.

## `test_connection`

Prueba una conexión habilitada mediante una sesión readonly y `SELECT 1`.

- Parámetro: `connection_id: str`.
- Respuesta: `connection_id`, `success`, `latency_ms`, `error_code` y `message`.
- Timeouts: `connect_timeout_seconds` para conectar y `query_timeout_seconds` como
  `statement_timeout` de sesión.
- Errores de dominio normalizados: `CONNECTION_NOT_FOUND`, `CONNECTION_DISABLED`,
  `SECRET_NOT_CONFIGURED`, `ADAPTER_NOT_AVAILABLE` o un código de conexión PostgreSQL.

Ejemplo de éxito:

```json
{
  "connection_id": "postgres-demo",
  "success": true,
  "latency_ms": 4.231,
  "error_code": null,
  "message": "Conexión PostgreSQL disponible."
}
```

Un error nunca incluye el secreto ni el texto completo del driver.

## `refresh_schema_cache`

Actualiza la metadata de una conexión o todas las conexiones habilitadas.

- Parámetro opcional: `connection_id`.
- Respuesta por conexión: `outcome`, fechas, hash, conteos, código y mensaje.
- Outcomes: `success`, `error`, `already_running` o `disabled`.
- Un error conserva el último snapshot válido y queda visible en el estado.

## `get_schema_cache_status`

Informa el último intento y la frescura calculada de una o todas las conexiones.

- Parámetro opcional: `connection_id`.
- Respuesta: `state`, `has_snapshot`, `stale`, fechas, hash, error y mensaje.
- Estados persistentes: `never`, `refreshing`, `success` y `error`.
- `stale` se calcula con `stale_after_minutes`; no implica eliminar el snapshot.

## `search_catalog`

Busca sobre el último snapshot válido sin conectarse a la base origen.

- Parámetros: `query`, `connection_id` opcional y `max_results` entre 1 y 100.
- Busca nombres y descripciones de tablas, y nombres/descripciones de columnas.
- Todos los términos deben aparecer dentro de la tabla candidata.
- Devuelve columnas coincidentes, score y relaciones FK entrantes/salientes.
- Incluye `cache_statuses` para que el cliente advierta resultados obsoletos o errores recientes.

La búsqueda vacía, un límite inválido o una conexión inexistente generan errores de dominio
explícitos. Una búsqueda válida sin snapshot devuelve cero resultados y estado `never`/`stale`.

## `list_schemas`

Lista los schemas visibles del último snapshot válido de una conexión.

- Parámetro requerido: `connection_id`.
- Respuesta: `contract_version`, `connection_id`, `schemas` y `cache_status`.
- No se conecta a PostgreSQL durante la llamada; lee SQLite.
- Sin snapshot devuelve un error que indica ejecutar `refresh_schema_cache`.

## `list_tables`

Lista tablas cacheadas con un resumen estable.

- Parámetro requerido: `connection_id`.
- Parámetro opcional: `schema`, coincidencia exacta y máximo 128 caracteres.
- Respuesta: `contract_version`, `connection_id`, `schema_filter`, `tables` y `cache_status`.
- Cada tabla incluye `schema`, `name`, `kind`, `description`, `column_count` y `primary_key`.
- Un filtro válido sin coincidencias devuelve `tables: []`.

## `describe_table`

Devuelve el detalle técnico de una tabla cacheada.

- Parámetros requeridos: `connection_id`, `schema` y `table`.
- Respuesta: `contract_version`, `connection_id`, `table` y `cache_status`.
- `table` incluye `schema`, `name`, `kind`, comentario, columnas ordenadas, PK, índices únicos
  completos y FK.
- Cada columna incluye posición, nombre, tipo PostgreSQL, nulabilidad, default y comentario.
- Si el objeto no existe o no es visible, el error identifica el nombre calificado solicitado.

Ejemplo abreviado:

```json
{
  "contract_version": "1.0.0",
  "connection_id": "postgres-demo",
  "table": {
    "schema": "public",
    "name": "clientes",
    "kind": "table",
    "primary_key": ["id"],
    "unique_keys": [
      {"name": "clientes_correo_key", "columns": ["correo"]}
    ],
    "foreign_keys": []
  }
}
```

El ejemplo omite `columns`, `description` y `cache_status` solo para hacerlo legible; la respuesta
real siempre respeta el output schema publicado.

## `list_relationships`

Lista relaciones FK desde el origen que contiene la FK hacia la tabla referenciada.

- Parámetro requerido: `connection_id`.
- Parámetros opcionales: `schema` y `table`; cada filtro coincide con origen o destino.
- Respuesta: `contract_version`, `connection_id`, filtros efectivos, `relationships` y
  `cache_status`.
- Cada relación incluye nombre, schema/tabla/columnas de origen y destino, `cardinality` y
  `cardinality_inference`.
- `one-to-one` se infiere cuando las columnas origen son PK o índice único completo;
  `many-to-one` cuando no tienen unicidad declarada.
- No se infiere desde filas ni se afirma opcionalidad; la evidencia queda explícita en
  `cardinality_inference`.

## `validate_sql`

Parsea una sentencia para el dialecto de la conexión sin ejecutarla.

- Parámetros: `connection_id` y `sql`.
- Devuelve: `valid`, `read_only`, `executable`, tipo, SQL normalizado, objetos referenciados,
  placeholders, razones de bloqueo y advertencias.
- Acepta para ejecución una única raíz `SELECT`, incluidas CTE de lectura y operaciones de conjuntos.
- DML/DDL válido conserva `normalized_sql`, pero devuelve `executable: false`, una razón estructurada
  y una advertencia de impacto. Esto permite revisión manual sin habilitar escritura.
- Registra un evento de auditoría con hash, nunca con el texto SQL.

Ejemplo conceptual de escritura bloqueada:

```json
{
  "valid": false,
  "read_only": false,
  "executable": false,
  "statement_type": "DELETE",
  "normalized_sql": "DELETE FROM ventas",
  "blocked_reasons": [
    {"code": "READ_ONLY_STATEMENT_REQUIRED", "message": "..."},
    {"code": "DML_NOT_ALLOWED", "message": "..."}
  ],
  "warnings": [
    {"code": "WRITE_IMPACT_WARNING", "message": "..."}
  ]
}
```

## `execute_read_query`

Valida de nuevo y ejecuta un único `SELECT` en una sesión PostgreSQL readonly.

- Parámetros requeridos: `connection_id` y `sql`.
- Parámetros opcionales: `parameters`, `max_rows` y `timeout_seconds`.
- Los placeholders son nombrados (`%(minimum_id)s`) y las claves deben coincidir exactamente.
- Devuelve validación, SQL realmente ejecutado, columnas, filas, conteo, límite, truncamiento, bytes
  serializados, duración, código de error y mensaje.
- El límite efectivo es el menor entre solicitud, conexión y política global; el timeout solicitado
  tampoco puede ampliar el de la conexión.
- Decimal, fecha/hora y UUID se devuelven como texto; binarios con prefijo `base64:`; `NULL` como
  `null`.
- Una sentencia bloqueada devuelve `executed: false` y nunca obtiene el adaptador de ejecución.

El parámetro `executed_sql` permite revisar el `LIMIT` exterior aplicado. No debe copiarse como
evidencia de auditoría: el registro durable usa únicamente su hash de correlación.

## `explain_query`

Valida un `SELECT` y devuelve su plan PostgreSQL JSON sin ejecutar la consulta explicada.

- Parámetros: `connection_id`, `sql`, `parameters` opcional y `timeout_seconds` opcional.
- Devuelve `explained`, `analyze: false`, validación, SQL limitado, plan, duración y error.
- El cliente no entrega `EXPLAIN`; la opción fija se añade dentro del adaptador después de validar.
- DML, DDL, múltiples sentencias y un `EXPLAIN` suministrado directamente se bloquean.

## `generate_sql`

Genera una sentencia SQL desde una pregunta en lenguaje natural usando el catálogo cacheado como
contexto, sin ejecutarla.

- Parámetros: `connection_id` y `question` (1 a 4000 caracteres).
- Respuesta: `contract_version`, `connection_id`, `question`, `outcome`, `generated`,
  `clarification`, `error_code` y `message`.
- `outcome` es `generated`, `clarification_required` o `generation_failed`.
- `generated.validation` es el mismo `SqlValidationResult` que produce `validate_sql`: un SQL
  generado que resulte DML/DDL queda con `executable: false` y las razones de bloqueo habituales.
- `clarification.candidates` solo incluye tablas y columnas que existen literalmente en el
  snapshot cacheado de la conexión; el servidor descarta cualquier objeto inventado por el modelo.
- Requiere `generation.enabled: true` y un proveedor configurado; si no, devuelve
  `GENERATION_NOT_CONFIGURED`.
- Registra un evento de auditoría con hash de la pregunta y del SQL, nunca su texto.

## `generate_and_execute_query`

Genera SQL y, solo si resulta ejecutable, lo ejecuta bajo la misma revalidación completa que
`execute_read_query`.

- Parámetros: `connection_id`, `question`, `max_rows` y `timeout_seconds` opcionales.
- Respuesta: igual que `generate_sql`, más un campo `execution` con la forma de
  `QueryExecutionResult` cuando el SQL generado fue ejecutable.
- Si `outcome` es `clarification_required` o `generation_failed`, `execution` es siempre `null` y
  no se invoca al adaptador de base de datos.
- El SQL generado nunca se ejecuta con la validación informativa de `generate_sql`: se revalida
  íntegramente dentro de `execute_read_query`, por lo que un SQL de escritura queda bloqueado con
  `SQL_VALIDATION_BLOCKED` igual que si lo hubiera escrito un cliente humano.

## `generate_report`

Genera SQL desde una pregunta en lenguaje natural, la ejecuta bajo la misma revalidación completa
que `generate_and_execute_query`, y entrega el resultado como un archivo descargable.

- Parámetros: `connection_id`, `question`, `format` (`csv`, `json`, `xlsx` o `pdf`) y `max_rows`
  opcional (1 a 10000).
- Respuesta: `contract_version`, `connection_id`, `question`, `format`, `outcome`, `period`,
  `applied_filters`, `generated_at`, `row_count`, `is_empty`, `truncation`, `payload`,
  `clarification`, `error_code` y `message`.
- Los periodos relativos ("el mes pasado", "últimos 7 días", "este trimestre", etc.) se resuelven de
  forma **determinística en Python**, nunca por el LLM; `period.label` y `period.start_date`/
  `end_date` muestran siempre el rango exacto usado.
- Un resultado con cero filas no es un error: `is_empty: true` y el archivo se genera igual, vacío.
- `payload` entrega el archivo **en línea**, codificado en `content_base64`, sin usar disco ni
  almacenamiento temporal. Si excede `reporting.max_inline_bytes`, la política
  `on_size_exceeded` trunca filas (`truncation.truncated: true`) o rechaza la solicitud con
  `REPORT_TOO_LARGE`.
- Si `outcome` no es `generated`, o el SQL generado resulta bloqueado, `payload` es siempre `null` y
  no se exporta nada.
- Requiere `reporting.enabled: true` y el formato solicitado dentro de `reporting.allowed_formats`;
  si no, devuelve `REPORTING_NOT_CONFIGURED` o `REPORT_FORMAT_NOT_SUPPORTED`.
- Registra un evento de auditoría con hash de la pregunta y del SQL, nunca su texto ni el archivo
  generado.

## `list_procedures`

Lista funciones y procedimientos PostgreSQL cacheados, leyendo exclusivamente catálogos internos
(`pg_proc`) sin ejecutar el cuerpo del objeto.

- Parámetro requerido: `connection_id`.
- Parámetro opcional: `schema`, coincidencia exacta.
- Respuesta: `contract_version`, `connection_id`, `schema_filter`, `procedures` y `cache_status`.
- Cada procedimiento incluye `schema`, `name`, `kind` (`function` o `procedure`), `language`,
  `arguments` (firma cruda de PostgreSQL), `return_type`, `comment` y `definition` (DDL real vía
  `pg_get_functiondef`).
- Un motor con overloads declara varias entradas con el mismo `(schema, name)` y distinta firma;
  no se resuelve ambigüedad aquí.
- No se conecta a PostgreSQL durante la llamada; lee el último snapshot válido, igual que
  `list_tables`.

## `list_triggers`

Lista triggers PostgreSQL cacheados, asociados a su tabla y función, leyendo exclusivamente
catálogos internos (`pg_trigger`) sin ejecutar el trigger.

- Parámetro requerido: `connection_id`.
- Parámetros opcionales: `schema` y `table`.
- Respuesta: `contract_version`, `connection_id`, filtros efectivos, `triggers` y `cache_status`.
- Cada trigger incluye `schema`, `name`, `table`, `timing` (`BEFORE`/`AFTER`/`INSTEAD OF`),
  `events` (`INSERT`/`UPDATE`/`DELETE`/`TRUNCATE`), `function_schema`, `function_name`, `comment`
  y `definition` (DDL real vía `pg_get_triggerdef`).
- No se conecta a PostgreSQL durante la llamada; lee el último snapshot válido.

## `explain_database_object`

Explica en lenguaje natural un procedimiento o trigger ya cacheado, a partir de su definición SQL
real, separando explícitamente hechos verificables de inferencias del modelo.

- Parámetros: `connection_id`, `schema`, `object_type` (`procedure` o `trigger`), `name`, y `table`
  (obligatorio solo cuando `object_type` es `trigger`).
- Respuesta: `contract_version`, `connection_id`, `schema`, `table`, `object_type`, `name`,
  `outcome` (`explained` o `explanation_failed`), `purpose`, `facts`, `inferences`,
  `referenced_tables`, `risks`, `definition_truncated`, `error_code` y `message`.
- `facts` solo contiene elementos verificables presentes literalmente en la definición;
  `inferences` contiene interpretaciones de negocio del modelo. Nunca se mezclan.
- Si el objeto no existe en el catálogo cacheado, devuelve un error de dominio sin llamar al
  proveedor LLM.
- Si la definición excede `generation.max_definition_chars`, se trunca y `definition_truncated`
  queda en `true`.
- Requiere `generation.enabled: true` y un proveedor configurado (misma sección que `generate_sql`
  de Sprint 5); si no, devuelve `GENERATION_NOT_CONFIGURED`.
- Registra un evento de auditoría con hash de la definición, nunca su texto ni la explicación
  generada.
