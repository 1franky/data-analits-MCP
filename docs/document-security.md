# Política documental segura (MongoDB)

## Contrato

MongoDB es un motor documental, no SQL: `find`/agregación no son texto parseable, así que este
modelo de seguridad es distinto en su base al de [query-security.md](query-security.md) — no usa
SQLGlot ni AST. `validate_mongo_query`, `execute_mongo_find` y `execute_mongo_aggregate` operan
sobre estructuras (`filter: dict`, `pipeline: list[dict]`) ya recibidas como JSON, nunca sobre
texto a parsear.

`execute_mongo_find`/`execute_mongo_aggregate` **siempre revalidan internamente** antes de tocar
el adaptador — igual principio que `execute_read_query`: nunca aceptan un resultado de
`validate_mongo_query` aportado por el cliente como si ya fuera seguro.

## Allowlist fail-closed

`MongoOperatorPolicy` (`app/security/mongo.py`) define explícitamente qué etapas de pipeline y qué
operadores `$...` están permitidos. Cualquier nombre que no esté en la allowlist queda bloqueado
— incluidos nombres inventados que no están ni en la allowlist ni en la lista de bloqueo explícita.
No es una denylist con excepciones: es un "solo lo reconocido explícitamente se ejecuta".

Etapas de pipeline permitidas: `$match`, `$project`, `$group`, `$sort`, `$limit`, `$skip`,
`$unwind`, `$lookup`, `$addFields`, `$set`, `$count`, `$facet`, `$bucket`, `$bucketAuto`,
`$sample`, `$replaceRoot`, `$replaceWith`, `$sortByCount`, `$unset`, `$geoNear`.

Operadores permitidos (dentro de `filter`/etapas): comparación (`$eq`, `$ne`, `$gt`, `$gte`, `$lt`,
`$lte`, `$in`, `$nin`), lógicos (`$and`, `$or`, `$nor`, `$not`), estructurales (`$exists`, `$type`,
`$regex`, `$options`, `$mod`, `$all`, `$elemMatch`, `$size`, `$expr`, `$text`, `$search`),
acumuladores (`$sum`, `$avg`, `$min`, `$max`, `$first`, `$last`, `$push`, `$addToSet`), y
expresiones de proyección/fecha comunes (`$cond`, `$ifNull`, `$switch`, `$concat`, `$substr`,
`$toUpper`, `$toLower`, `$dateToString`, `$year`, `$month`, `$dayOfMonth`, `$multiply`, `$divide`,
`$add`, `$subtract`).

Bloqueados explícitamente (con razón nombrada, no genérica): `$out`, `$merge`, `$function`,
`$accumulator`, `$where` (JavaScript del lado del servidor), `$currentOp`, `$collStats`,
`$indexStats`, `$planCacheStats`, `$eval`.

Razones estructuradas:

| Código | Condición |
|---|---|
| `COLLECTION_NAME_INVALID` | Nombre de colección vacío o con `$`/`.` inicial. |
| `STAGE_SHAPE_INVALID` | Una etapa del pipeline no tiene exactamente una clave. |
| `STAGE_NOT_ALLOWED` | Etapa fuera de la allowlist (bloqueada explícita o desconocida). |
| `OPERATOR_NOT_ALLOWED` | Operador `$...` anidado fuera de la allowlist. |
| `NESTING_TOO_DEEP` | El payload excede 32 niveles de anidamiento. |

## Garantía de cero escritura: dos capas independientes

1. **Capa de código**: `DocumentDatabaseAdapter` (`app/adapters/base/document.py`) declara
   únicamente `capabilities`, `test_connection`, `list_collections`, `execute_find` y
   `execute_aggregation`. No existe `insert_one`/`update_many`/`delete_one`/`bulk_write` en la
   interfaz ni en `MongoDbAdapter` — no es una llamada bloqueada en tiempo de ejecución, es
   superficie de código que nunca se escribió.
2. **Capa de servidor**: el usuario configurado en `connections.yaml` debe tener únicamente el rol
   `read` de MongoDB (`db.createUser({..., roles: [{role: "read", db: "..."}]})`), nunca
   `readWrite`/`dbAdmin`. Aunque un bug hipotético expusiera un método de escritura, el servidor lo
   rechazaría igual.

Ambas capas se verifican con pruebas de integración reales: una consulta bloqueada nunca invoca al
adaptador (contador de llamadas en cero), y un intento de escritura directo con las credenciales
`mcp_readonly` contra el servidor real falla con un error de autorización de MongoDB.

## Límites

- `max_rows`/`timeout_seconds` se acotan igual que en SQL: mínimo entre lo solicitado, el límite de
  la conexión y la política global (`query.global_max_rows`, `query.max_serialized_bytes`).
- `execute_mongo_aggregate` añade `{"$limit": max_rows}` al final del pipeline validado antes de
  ejecutar, como defensa adicional independiente de la validación previa — mismo principio que el
  `LIMIT` exterior que `apply_row_limit` aplica a SQL.
- Semáforo de concurrencia propio (`DocumentQueryExecutionService`), independiente del semáforo de
  `QueryExecutionService`, para que las consultas Mongo nunca agoten la capacidad reservada a SQL.

## Auditoría

`AuditService.record_document_query` reutiliza el esquema de auditoría existente sin migraciones,
reutilizando además `AuditOperation.VALIDATE`/`EXECUTE` (no se crean operaciones nuevas). Nunca se
persiste el `filter`/`pipeline` en texto plano — solo un hash SHA-256 del payload serializado
(`json.dumps(..., sort_keys=True)`), igual principio que el resto del proyecto.

## Ampliar la política

Al aceptar una etapa u operador nuevo:

1. confirma que MongoDB lo trata como lectura pura (sin efectos secundarios ni I/O externo);
2. añádelo a `MongoOperatorPolicy._ALLOWED_PIPELINE_STAGES`/`_ALLOWED_OPERATORS`;
3. añade pruebas positivas y de ataque (payload anidado, nombre inventado similar);
4. ejecuta la integración real contra el laboratorio y confirma que el rol `read` sigue sin poder
   escribir;
5. documenta el cambio aquí.
