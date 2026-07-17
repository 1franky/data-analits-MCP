# Configuración de conexiones

## Archivo y ciclo de carga

`connections.yaml` declara conexiones sin secretos. Compose lo monta en
`/app/connections.yaml:ro`; `CONNECTIONS_FILE` permite elegir otra ruta dentro del contenedor. El
archivo se valida al arrancar y queda en memoria durante la vida del proceso. Reinicia el servicio
después de modificarlo; no es necesario reconstruir la imagen.

## Formato

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

catalog:
  enabled: true
  refresh_interval_minutes: 60
  refresh_on_startup: true
  stale_after_minutes: 120
  excluded_schemas: [information_schema, pg_catalog]
  include_table_patterns: ["*"]
  exclude_table_patterns: []

query:
  global_max_rows: 1000
  max_serialized_bytes: 1000000
  max_concurrent_queries: 4

audit:
  enabled: true
```

| Campo | Regla |
|---|---|
| `id` | Único; minúsculas, números y guiones; 1–63 caracteres. |
| `name` | Nombre visible no vacío. |
| `type` | Motor conocido. `postgres` y `mariadb` tienen adaptador SQL; `mongodb` tiene adaptador documental. |
| `host` | DNS/IP visible desde el contenedor. |
| `port` | Entero entre 1 y 65535. |
| `database` | Base objetivo. |
| `username` | Rol de base de datos; debe ser externo y readonly. |
| `password_env` | Nombre de variable en mayúsculas que contiene el secreto. |
| `readonly` | Debe ser `true` para conexiones habilitadas. |
| `enabled` | Si es `false`, se lista pero no se puede utilizar. |
| `connect_timeout_seconds` | 1–300; sí se aplica a la conexión. |
| `query_timeout_seconds` | 1–3600; máximo para `statement_timeout`, locks y solicitudes. |
| `max_rows` | 1–10000; máximo por conexión para resultados de lectura. |
| `options` | Opciones allowlist específicas del driver. |

Los tipos declarables son `postgres`, `sqlserver`, `mariadb`, `informix`, `mongodb` y `oracle`.
Una conexión habilitada falla al arrancar si su adaptador aún no existe. Esto permite documentar
conexiones futuras como `enabled: false` sin afirmar soporte funcional. `sqlserver` e `informix`
quedan `enabled: false` por diseño en este laboratorio: SQL Server no publica una imagen Docker
ARM64 nativa e Informix no tiene soporte ARM64 confirmado para versiones modernas (ver
`TASKS.md`, Sprint 9, historias `BLOCKED`).

`mongodb` es un motor **documental**, no SQL: no usa `validate_sql`/`execute_read_query`/
`explain_query` ni aparece en el catálogo técnico de Sprint 2 (`list_tables`/`describe_table`).
Usa su propio conjunto de tools — `list_mongo_collections`, `validate_mongo_query`,
`execute_mongo_find`, `execute_mongo_aggregate` — documentadas en
[mcp-tools.md](mcp-tools.md) y con su propio modelo de seguridad en
[document-security.md](document-security.md).

## Secretos

`password_env` contiene el **nombre**, no el valor. En Compose añade el valor a `.env` y pásalo
explícitamente en `environment`. En producción puede inyectarse con el mecanismo de secretos del
orquestador siempre que termine como variable de entorno del proceso.

Nunca coloques contraseñas en:

- `connections.yaml`;
- `.env.example` con valores reales;
- argumentos de comandos compartidos;
- logs o nombres de recursos.

## Opciones por motor

El allowlist de PostgreSQL acepta:

```text
application_name, keepalives, keepalives_count, keepalives_idle,
keepalives_interval, sslcert, sslkey, sslmode, sslrootcert,
target_session_attrs
```

El allowlist de MariaDB acepta:

```text
charset, connect_timeout, ssl_ca, ssl_cert, ssl_key, ssl_verify_cert
```

El allowlist de MongoDB acepta:

```text
authSource, tls, tlsAllowInvalidCertificates, directConnection, appName, readPreference
```

En los tres casos, los campos centrales (`host`, `port`, `database`, `user`/`username`) y cualquier
forma de secreto o cadena completa (`password`, `passfile`, `sslpassword`, `conninfo`, `dsn`, `uri`)
están prohibidos dentro de `options`. Opciones desconocidas se rechazan antes de conectar.

El laboratorio PostgreSQL usa `sslmode: disable` porque opera dentro de Docker local. Para un
servidor remoto, usa la política TLS exigida por el servidor, por ejemplo `verify-full`, y monta
certificados por una ruta configurable del contenedor. MariaDB/MongoDB siguen el mismo criterio con
sus propias opciones `ssl_*`/`tls*`.

## Añadir una conexión

1. Crea un rol de base de datos estrictamente readonly (`SELECT`/`SHOW VIEW` en MariaDB, rol `read`
   en MongoDB — nunca `readWrite`/`dbAdmin`).
2. Añade una entrada con ID único.
3. Define un nombre de variable en `password_env`.
4. Inyecta esa variable en el contenedor sin versionar su valor.
5. Reinicia `data-platform-mcp`.
6. Invoca `list_connections` y después `test_connection`.

`postgres` y `mariadb` pueden habilitarse con las tools SQL existentes; `mongodb` puede habilitarse
con sus propias tools documentales. `sqlserver` e `informix` deben permanecer `enabled: false`
hasta resolver su soporte ARM64 (ver más arriba).

## Política del catálogo

| Campo | Regla |
|---|---|
| `enabled` | Desactiva refresh y scheduler sin afectar las herramientas de conexión. |
| `refresh_interval_minutes` | Entre 1 y 10080; intervalo fijo del scheduler. |
| `refresh_on_startup` | Lanza un refresh en background al iniciar. |
| `stale_after_minutes` | Entre 1 y 43200; edad a partir de la cual un snapshot es obsoleto. |
| `excluded_schemas` | Nombres exactos, sin blancos ni duplicados. |
| `include_table_patterns` | Globs sobre `tabla` o `schema.tabla`; requiere al menos uno si está activo. |
| `exclude_table_patterns` | Globs aplicados después de inclusión. |

Los filtros se evalúan antes de describir una tabla. Un cambio en esta política requiere reiniciar
el servicio y ejecutar un refresh. Consulta [catálogo](catalog.md) para estados y operación.

## Política de consultas y auditoría

| Campo | Regla |
|---|---|
| `query.global_max_rows` | 1–10000; tope global que nunca amplía el `max_rows` de una conexión. |
| `query.max_serialized_bytes` | 1024–100000000; corta la respuesta antes de exceder el presupuesto. |
| `query.max_concurrent_queries` | 1–64; capacidad simultánea por proceso para execute/explain. |
| `audit.enabled` | Si es `true`, persiste decisiones de validate/execute/explain sin contenido SQL. |

Una solicitud puede pedir menos filas o menos tiempo, nunca ampliar los límites configurados. Los
cambios se cargan al reiniciar. `AUDIT_DB_PATH` elige la ruta del SQLite de auditoría y debe apuntar a
una ubicación escribible; Compose usa `/app/data/audit.db` dentro del volumen persistente.

## Solución de problemas

| Síntoma/código | Causa habitual | Acción |
|---|---|---|
| `CONFIG_READ_ERROR` | Ruta o montaje incorrecto. | Revisa `CONNECTIONS_FILE` y el volumen. |
| `CONFIG_YAML_ERROR` | Sintaxis YAML inválida. | Valida indentación y tipos escalares. |
| `CONFIG_VALIDATION_ERROR` | Duplicado, rango o campo inválido. | Corrige el detalle Pydantic mostrado. |
| `SECRET_NOT_CONFIGURED` | Variable ausente/vacía. | Inyecta el nombre indicado por `password_env`. |
| `ADAPTER_NOT_AVAILABLE` | Motor aún no implementado. | Deshabilita la conexión o añade un adaptador probado. |
| `CONNECTION_DISABLED` | `enabled: false`. | Habilita solo cuando el motor y secreto estén listos. |
| `DATABASE_CONNECTION_ERROR` | DNS, puerto, TLS o credencial. | Verifica red, servidor, rol y opciones SSL. |

Si se cambia `POSTGRES_DEMO_PASSWORD` después de crear el volumen del laboratorio, PostgreSQL
conserva la contraseña inicial. Elimina el volumen de laboratorio para reinicializarlo o cambia la
clave de forma administrativa.
