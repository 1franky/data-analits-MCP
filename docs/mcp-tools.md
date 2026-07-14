# Herramientas MCP disponibles

El transporte es Streamable HTTP en `/mcp`. Los modelos de respuesta se serializan como datos
estructurados. Ninguna herramienta de Sprint 2 acepta SQL ni devuelve filas de negocio.

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
      "foreign_keys": true
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
