# Herramientas MCP disponibles

El transporte es Streamable HTTP en `/mcp`. Los modelos de respuesta se serializan como datos
estructurados. Sprint 3 incorpora una superficie SQL PostgreSQL estrictamente de lectura; no existe
ninguna herramienta que ejecute escrituras.

## `hello_world`

Verifica que la sesión MCP puede listar e invocar herramientas.

- Parámetro: `name: str = "world"`.
- Respuesta: `{"message": "Hello, <name>!"}`.
- Acceso externo: ninguno.

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
