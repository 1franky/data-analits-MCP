# Prompts de prueba para Open WebUI

Guía complementaria a [openwebui-integration.md](openwebui-integration.md): prompts en lenguaje
natural para escribir directamente en el chat de Open WebUI, uno por cada una de las 29 tools
expuestas por `data-platform-mcp`, más una sección dedicada a ejercitar el esquema extendido del
laboratorio PostgreSQL (tablas, procedimientos y triggers nuevos).

## Prerrequisitos

- Sigue primero [openwebui-integration.md](openwebui-integration.md): Open WebUI conectado al
  servidor MCP (`http://data-platform-mcp:8000/mcp`), con las 29 tools visibles en **Admin
  Settings → External Tools**.
- Un modelo con tool-calling habilitado en la conversación (icono de herramientas activo).
- El laboratorio completo levantado (`docker compose up -d`): PostgreSQL, MariaDB, MongoDB y Qdrant.
- **Generación LLM** (`generate_sql`, `generate_and_execute_query`, `generate_report`,
  `explain_database_object`) y **RAG documental** (`search_documents`, `list_indexed_documents`,
  `refresh_document_index`, `delete_indexed_document`) están **deshabilitados por defecto**
  (`generation.enabled: false` / `rag.enabled: false` en `connections.yaml`). Si no configuraste un
  proveedor real, esas 8 tools existen y aparecen en la lista, pero al invocarlas el modelo recibirá
  un error de herramienta explícito: *"La generación de SQL por lenguaje natural no está configurada
  o habilitada"* / *"El RAG documental no está configurado o habilitado"* — verificado directamente
  contra el servidor real. Es el comportamiento esperado, no un fallo; confirma que el modelo lo
  comunica en vez de inventar una respuesta. Para probarlas de extremo a extremo, habilita
  `generation.provider`/`rag.embedding_provider` con un proveedor real primero.
- Todos los prompts asumen las conexiones de laboratorio ya existentes: `postgres-demo`,
  `mariadb-demo`, `mongodb-demo`.

## 1. Administración y descubrimiento de conexiones

| Tool | Prompt |
|---|---|
| `hello_world` | "Usa la herramienta hello_world para probar que el servidor MCP responde." |
| `health_check` | "¿El servidor MCP está en buen estado? Revísalo con health_check." |
| `list_connections` | "¿Qué conexiones de bases de datos hay configuradas en este servidor?" |
| `get_connection_capabilities` | "¿Qué capacidades tiene la conexión mariadb-demo? ¿Soporta procedimientos y triggers?" |
| `test_connection` | "Prueba la conexión mongodb-demo y dime si está respondiendo correctamente." |

## 2. Catálogo de metadata (PostgreSQL)

| Tool | Prompt |
|---|---|
| `refresh_schema_cache` | "Refresca el caché de metadata de la conexión postgres-demo." |
| `get_schema_cache_status` | "¿Cuándo se actualizó por última vez el caché de postgres-demo?" |
| `search_catalog` | "Busca en el catálogo de postgres-demo qué tablas o columnas mencionan 'salario'." |
| `list_schemas` | "¿Qué schemas existen en la conexión postgres-demo?" |
| `list_tables` | "Lista todas las tablas disponibles en postgres-demo." |
| `describe_table` | "Describe la estructura completa de la tabla empleados en postgres-demo." |
| `list_relationships` | "¿Qué relaciones de llave foránea tiene la tabla productos en postgres-demo?" |

## 3. Consultas SQL seguras (PostgreSQL/MariaDB)

| Tool | Prompt |
|---|---|
| `validate_sql` | "Valida, sin ejecutarla, esta sentencia sobre postgres-demo: `DELETE FROM empleados;`. Dime si sería bloqueada y por qué." |
| `execute_read_query` | "Ejecuta en postgres-demo: consulta el nombre y salario de los empleados, ordenados de mayor a menor salario." |
| `explain_query` | "Muéstrame el plan de ejecución (EXPLAIN) de esta consulta en postgres-demo: `SELECT * FROM ventas WHERE cliente_id = 1`." |

`execute_read_query`/`explain_query` también aplican a `mariadb-demo` — repite cualquiera de los dos
prompts anteriores cambiando "postgres-demo" por "mariadb-demo" para ejercitar el dialecto MySQL
internamente sin que tengas que especificarlo.

## 4. Objetos de base de datos (procedimientos y triggers)

| Tool | Prompt |
|---|---|
| `list_procedures` | "Lista los procedimientos y funciones disponibles en postgres-demo." |
| `list_triggers` | "¿Qué triggers existen en la tabla ventas de postgres-demo?" |

## 5. Generación asistida por LLM (requiere `generation.enabled: true`)

| Tool | Prompt |
|---|---|
| `generate_sql` | "Usando postgres-demo, genera (sin ejecutar) el SQL para: ¿cuántos empleados hay por puesto?" |
| `generate_and_execute_query` | "Usando postgres-demo, dime cuál es el cliente que más ha gastado en total." |
| `generate_report` | "Genera un reporte en formato XLSX con las ventas de postgres-demo, agrupadas por producto." |
| `explain_database_object` | "Explícame en lenguaje natural qué hace el trigger trg_empleados_historial_salario en postgres-demo, distinguiendo hechos verificables de inferencias." |

## 6. Consultas documentales (MongoDB)

| Tool | Prompt |
|---|---|
| `list_mongo_collections` | "¿Qué colecciones existen en mongodb-demo?" |
| `validate_mongo_query` | "Valida, sin ejecutarlo, este filtro sobre la colección ventas en mongodb-demo: cantidad mayor a 2." |
| `execute_mongo_find` | "Busca en mongodb-demo, colección clientes, los documentos donde el nombre sea 'Ana'." |
| `execute_mongo_aggregate` | "En mongodb-demo, agrupa la colección ventas por cliente_id y suma la cantidad total de cada uno." |

## 7. RAG documental (requiere `rag.enabled: true`)

| Tool | Prompt |
|---|---|
| `refresh_document_index` | "Reindexa toda la documentación funcional disponible." |
| `list_indexed_documents` | "¿Qué documentos están indexados actualmente?" |
| `search_documents` | "Busca en la documentación indexada información sobre seguridad de consultas." |
| `delete_indexed_document` | "Elimina del índice el documento con id `<pega aquí un document_id devuelto por list_indexed_documents>`." |

`delete_indexed_document` necesita un `document_id` real — pide primero `list_indexed_documents` en
la misma conversación y usa uno de los IDs devueltos.

---

## 8. Pruebas del esquema extendido del laboratorio PostgreSQL

Esta sección ejercita específicamente las tablas, procedimientos y triggers nuevos añadidos en
`database/init/06-more-demo-data.sql` y `database/init/07-more-demo-objects.sql`, con al menos un
prompt por objeto nuevo. Todos usan `execute_read_query`/`list_procedures`/`list_triggers`, ya
disponibles sin configurar ningún proveedor LLM adicional.

### Tablas nuevas

| Objeto | Prompt | Resultado esperado |
|---|---|---|
| `categorias` | "Usando postgres-demo, ¿qué categorías de productos existen y cuántos productos tiene cada una?" | 3 categorías (Cómputo, Accesorios, Oficina); Cómputo con 2 productos (Laptop, Monitor), Accesorios con 2 (Mouse, Teclado). |
| `proveedores` | "Usando postgres-demo, ¿qué proveedor abastece el producto Monitor?" | TechDistribuidora S.A. |
| `direcciones_envio` | "Usando postgres-demo, ¿cuáles son las direcciones de envío del cliente Ana López, y cuál es la principal?" | 2 direcciones (Guadalajara principal, Zapopan no principal). |
| `resenas_productos` | "Usando postgres-demo, muéstrame las reseñas del producto Mouse con su calificación y comentario." | 2 reseñas, calificación 4 ambas. |
| `empleados` | "Usando postgres-demo, lista los empleados con su puesto y salario actual." | 4 empleados; el salario de Luis Torres debe verse en 19000 (ya incluye el ajuste del trigger de inicialización). |
| `historial_salarios` | "Usando postgres-demo, ¿qué cambios de salario se han registrado?" | 1 fila: Luis Torres, de 18000 a 19000, generada automáticamente al inicializar el laboratorio. |

### Procedimientos/funciones nuevos

Estas 3 son funciones `STABLE` invocables dentro de un `SELECT` de solo lectura — verificado
directamente contra el servidor real, no solo listables.

| Función | Prompt | Resultado esperado |
|---|---|---|
| `producto_mas_vendido()` | "Usando postgres-demo, ¿cuál es el producto más vendido? Usa la función producto_mas_vendido si existe." | Mouse, con 5 unidades totales vendidas. |
| `calificacion_promedio_producto(id)` | "Usando postgres-demo, ¿cuál es la calificación promedio del producto Mouse? Usa calificacion_promedio_producto y el id correspondiente." | 4.0 |
| `clientes_por_ciudad(ciudad)` | "Usando postgres-demo, ¿qué clientes tienen una dirección de envío registrada en Guadalajara? Usa clientes_por_ciudad." | Ana López |

Las otras dos funciones nuevas (`valida_stock_venta`, `registrar_historial_salario`) son funciones
de trigger (`RETURNS trigger`): PostgreSQL no permite invocarlas directamente desde un `SELECT`,
solo se ejecutan cuando su trigger dispara — pruébalas indirectamente en la siguiente sección.

| Función de trigger | Prompt | Resultado esperado |
|---|---|---|
| ambas | "Usando postgres-demo, lista los procedimientos disponibles y confírmame si aparecen valida_stock_venta y registrar_historial_salario." | Ambas aparecen en `list_procedures`, con `kind: function` y su comentario descriptivo. |

### Triggers nuevos

El servidor MCP nunca ejecuta escritura (`INSERT`/`UPDATE`/`DELETE`), así que estos prompts no
disparan el trigger de verdad — confirman que el intento queda bloqueado por la validación antes de
llegar a la base de datos, la misma garantía que ya cubre HU-803 en
[openwebui-integration.md](openwebui-integration.md#5-generar-dml-sin-ejecutarlo-hu-803). El
comportamiento *real* de ambos triggers (rechazo por stock insuficiente, registro en
`historial_salarios`) ya se verificó directamente contra PostgreSQL fuera del MCP — ver la
descripción del PR que los introdujo.

| Trigger | Prompt | Resultado esperado |
|---|---|---|
| `trg_ventas_valida_stock` (BEFORE INSERT) | "Usando postgres-demo, inserta una venta de 99999 unidades del producto Mouse para el cliente Juan Pérez." | El modelo genera el `INSERT` y lo pasa a `execute_read_query`/`validate_sql`; la respuesta muestra `executed: false` con razones `DML_NOT_ALLOWED`/`READ_ONLY_STATEMENT_REQUIRED` — nunca llega al adaptador, así que el trigger nunca se dispara desde el chat. |
| `trg_empleados_historial_salario` (AFTER UPDATE) | "Usando postgres-demo, actualiza el salario del empleado Luis Torres a 25000." | Mismo resultado: `UPDATE` generado y bloqueado con los mismos códigos, sin tocar la base de datos. |

También puedes confirmar que ambos triggers están listados correctamente:

```text
Usando postgres-demo, ¿qué triggers existen en la tabla empleados?
```

Debe devolver `trg_empleados_historial_salario`, con `timing: AFTER` y `events: ["UPDATE"]`.

---

## Checklist de cobertura (29 tools)

| # | Tool | Sección |
|---|---|---|
| 1 | `hello_world` | 1 |
| 2 | `health_check` | 1 |
| 3 | `list_connections` | 1 |
| 4 | `get_connection_capabilities` | 1 |
| 5 | `test_connection` | 1 |
| 6 | `refresh_schema_cache` | 2 |
| 7 | `get_schema_cache_status` | 2 |
| 8 | `search_catalog` | 2 |
| 9 | `list_schemas` | 2 |
| 10 | `list_tables` | 2 |
| 11 | `describe_table` | 2 |
| 12 | `list_relationships` | 2 |
| 13 | `validate_sql` | 3 |
| 14 | `execute_read_query` | 3 |
| 15 | `explain_query` | 3 |
| 16 | `list_procedures` | 4 |
| 17 | `list_triggers` | 4 |
| 18 | `generate_sql` | 5 |
| 19 | `generate_and_execute_query` | 5 |
| 20 | `generate_report` | 5 |
| 21 | `explain_database_object` | 5 |
| 22 | `list_mongo_collections` | 6 |
| 23 | `validate_mongo_query` | 6 |
| 24 | `execute_mongo_find` | 6 |
| 25 | `execute_mongo_aggregate` | 6 |
| 26 | `refresh_document_index` | 7 |
| 27 | `list_indexed_documents` | 7 |
| 28 | `search_documents` | 7 |
| 29 | `delete_indexed_document` | 7 |
