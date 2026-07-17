# Política de consultas seguras

## Contrato

La superficie SQL soporta PostgreSQL y, desde Sprint 9, MariaDB — ambos ejecutan solo una sentencia
de lectura bajo las mismas tools. Todas las herramientas reciben `connection_id`; el dialecto
público (`"postgres"`/`"mariadb"`) se obtiene de esa conexión y no puede ser elegido libremente por
el cliente. Internamente, `QueryValidationService` despacha ese dialecto público a un dialecto de
lectura de SQLGlot y a una política de funciones peligrosas por motor (`postgres` → dialecto
SQLGlot `postgres` + `PostgresSqlPolicy`; `mariadb` → dialecto SQLGlot `mysql` +
`MariaDbSqlPolicy`, ya que SQLGlot no tiene un dialecto `"mariadb"` literal). El valor público de
`dialect` que ve el cliente y que se audita nunca cambia por esta traducción interna.

`validate_sql` puede clasificar una escritura y devolver su forma normalizada para revisión. Eso no
la convierte en ejecutable. `execute_read_query` y `explain_query` vuelven a validar el texto; no
aceptan un token o resultado de validación aportado por el cliente.

## Decisión AST

SQLGlot parsea el texto con dialecto `postgres`. La política permite una raíz `SELECT` o una operación
de conjuntos cuyo árbol completo no contenga nodos prohibidos. Se recorren todos los descendientes,
por lo que comentarios, espacios o anidamiento no evitan la clasificación.

Razones principales:

| Código | Condición |
|---|---|
| `SQL_EMPTY` | Entrada vacía. |
| `SQL_PARSE_ERROR` | Sintaxis no parseable como PostgreSQL. |
| `SQL_DIALECT_UNSUPPORTED` | Conexión sin política ejecutable. |
| `MULTIPLE_STATEMENTS` | Más de una sentencia. |
| `READ_ONLY_STATEMENT_REQUIRED` | La raíz no es de lectura. |
| `DML_NOT_ALLOWED` / `DDL_NOT_ALLOWED` | Escritura de datos o estructura. |
| `WRITE_IN_CTE` | DML dentro de un CTE. |
| `ADMIN_COMMAND_NOT_ALLOWED` | Comando fuera de la allowlist. |
| `SELECT_INTO_NOT_ALLOWED` | `SELECT` que crea una tabla. |
| `LOCKING_SELECT_NOT_ALLOWED` | Lectura que adquiere locks explícitos. |
| `DANGEROUS_FUNCTION_NOT_ALLOWED` | Función conocida con efectos/abuso. |
| `NAMED_PARAMETERS_REQUIRED` | Placeholder posicional o anónimo. |
| `QUERY_PARAMETERS_MISMATCH` | Claves entregadas distintas de las referidas. |

La respuesta agrega `statement_type`, `referenced_objects`, `parameter_names`, razones y warnings.
Los códigos son el contrato estable; los mensajes humanos pueden mejorar sin romper consumidores.

## Política MariaDB

`MariaDbSqlPolicy` bloquea funciones peligrosas específicas de MySQL/MariaDB: `LOAD_FILE`,
`SLEEP`, `BENCHMARK`, `GET_LOCK`/`RELEASE_LOCK`/`RELEASE_ALL_LOCKS`, `IS_FREE_LOCK`,
`IS_USED_LOCK`, `MASTER_POS_WAIT`, `SOURCE_POS_WAIT`, `UUID_SHORT`. Comandos administrativos
(`LOCK TABLES`, `SET GLOBAL`, `KILL`) quedan cubiertos por `ADMIN_COMMAND_NOT_ALLOWED`, el mismo
código genérico ya usado para PostgreSQL — SQLGlot los clasifica como comandos, no como
sentencias `SELECT`.

## Parámetros

Se usa el formato nombrado de Psycopg:

```sql
SELECT id, nombre
FROM clientes
WHERE id >= %(minimum_id)s
ORDER BY id
```

```json
{"minimum_id": 2}
```

Solo se admiten valores escalares `str`, `int`, `float`, `bool` o `null`. No construyas nombres de
tabla/columna mediante parámetros: SQL los trata como valores. La clave exacta evita placeholders
sin valor y parámetros sobrantes que podrían ocultar errores del generador.

## Límites

Antes de ejecutar, el servicio reescribe el AST con un `LIMIT` exterior. Conserva un límite menor y
reduce uno mayor. Además aplica:

- timeout de conexión/sentencia/locks acotado por la configuración de la conexión;
- máximo de bytes serializados;
- semáforo no bloqueante de consultas y planes por proceso;
- sesión y rol readonly (PostgreSQL: `connection.read_only = True`; MariaDB:
  `SET SESSION TRANSACTION READ ONLY` + `SET SESSION max_statement_time`);
- rollback explícito y cierre después de cada operación.

El campo `truncated` es conservador: puede ser verdadero al alcanzar exactamente el límite porque el
adaptador no obtiene una fila adicional para comprobar si existe más información.

## Serialización

Los nombres de columnas conservan el orden del cursor. Los escalares JSON permanecen escalares;
`Decimal`, fecha/hora y UUID se convierten a texto; binarios se codifican Base64 con prefijo
`base64:`; otros valores de driver se convierten a JSON determinista. Las filas completas que
superarían `max_serialized_bytes` no se incluyen.

## EXPLAIN

La herramienta recibe únicamente el `SELECT`. Después de validarlo, el adaptador antepone una
plantilla constante con `FORMAT JSON` y `ANALYZE FALSE`. Nunca se ejecuta un `EXPLAIN ANALYZE` y un
comando `EXPLAIN` recibido del cliente se bloquea.

## Auditoría

Los eventos guardan ID/fecha, herramienta, conexión, operación, tipo, hash SHA-256, decisión,
códigos de bloqueo, duración, conteo, estado y error normalizado. No guardan SQL, parámetros,
columnas ni filas. El repositorio SQLite es reemplazable mediante el contrato `AuditRepository`.

## Generación asistida por LLM (Sprint 5)

`generate_sql` y `generate_and_execute_query` construyen SQL a partir de una pregunta en
lenguaje natural, usando exclusivamente el snapshot de catálogo ya cacheado (nunca filas de
negocio) como contexto. El texto que produce el proveedor LLM **nunca se trata como SQL
confiable**: pasa siempre por `QueryValidationService.validate()` igual que cualquier otro SQL de
cliente, y `generate_and_execute_query` delega la ejecución en `QueryExecutionService.execute()`
sin reutilizar la validación informativa previa, exactamente el mismo camino de revalidación
completa que ya existe para `execute_read_query`. Un `DELETE`/`INSERT`/`DDL` "generado" queda
marcado `executable: false` con las mismas razones estructuradas de esta política y nunca llega al
adaptador.

Si el modelo detecta ambigüedad (por ejemplo, un término que podría referirse a más de una tabla o
columna del contexto), la respuesta es `outcome: clarification_required` con candidatos
estructurados en vez de una suposición peligrosa. Cada candidato se valida contra el snapshot real
del catálogo antes de devolverse al cliente: cualquier tabla o columna que el modelo mencione pero
que no exista en el snapshot se descarta silenciosamente. Un resultado con aclaración nunca
contiene una ejecución.

El proveedor LLM se resuelve mediante un registry/factory análogo al de adaptadores de base de
datos (`app/generation/registry.py`); el núcleo de generación no depende de un proveedor
específico. La auditoría de generación (`AuditOperation.GENERATE`) nunca persiste la pregunta en
lenguaje natural ni el SQL generado, solo hashes SHA-256 (`prompt_hash`, `query_hash`), igual que el
resto de la auditoría de consultas.

## Ampliar la política

Al aceptar una construcción nueva:

1. comprueba cómo la representa SQLGlot para la versión fijada;
2. añade pruebas positivas, de ataque, comentarios/anidamiento y multi-sentencia;
3. demuestra con un adaptador espía que lo bloqueado no llega a ejecución;
4. ejecuta la integración contra el rol PostgreSQL real y verifica datos antes/después;
5. documenta el riesgo residual y actualiza los códigos si se introduce una decisión nueva.
