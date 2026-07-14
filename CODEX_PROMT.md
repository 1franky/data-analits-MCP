# Proyecto: Data Platform MCP con RAG, múltiples bases de datos y Open WebUI

Actúa como arquitecto de software senior, especialista en Python, MCP, RAG, seguridad de bases de datos, Docker y sistemas distribuidos.

Debes diseñar e implementar una plataforma denominada provisionalmente:

**Data Platform MCP**

El sistema permitirá consultar múltiples bases de datos mediante lenguaje natural desde Open WebUI, utilizando un modelo configurado en Open WebUI, por ejemplo OpenAI, BytePlus, Ollama, Claude u otro proveedor compatible.

El proyecto deberá construirse de forma incremental, dividido en sprints, con arquitectura por capas, pruebas automatizadas, documentación y controles estrictos de seguridad.

No implementes todo de forma desordenada. Primero analiza el estado actual del repositorio, crea el plan de trabajo y después desarrolla sprint por sprint.

---

# 1. Contexto actual

Actualmente existe un VPS de Oracle Free Tier donde ya se encuentran desplegados:

* Ollama.
* Open WebUI.
* Una red Docker externa llamada `ai-platform`.
* Open WebUI conectado a Ollama.
* Open WebUI podrá configurarse con un proveedor externo mediante API key, como OpenAI o BytePlus.

El Docker Compose de referencia actualmente utilizado es:

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    pull_policy: always
    tty: true
    restart: unless-stopped

    volumes:
      - /Users/franciscolopez/Documents/docker/ollama/ollama:/root/.ollama

  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: open-webui
    restart: unless-stopped

    ports:
      - "3000:8080"

    volumes:
      - /Users/franciscolopez/Documents/docker/ollama/openwebui:/app/backend/data

    environment:
      - OLLAMA_BASE_URL=http://ollama:11434

    extra_hosts:
      - "host.docker.internal:host-gateway"

    depends_on:
      - ollama

    networks:
      - default
      - ai-platform

networks:
  ai-platform:
    external: true
```

La red ya fue creada con:

```bash
docker network create ai-platform
```

El nuevo proyecto Data Platform MCP deberá ejecutarse en uno o varios contenedores Docker separados y conectarse a la red externa `ai-platform`.

No se deberá acoplar directamente el código del proyecto al contenedor de Open WebUI.

Para VPS Linux, todas las rutas persistentes deberán poder configurarse mediante variables de entorno y no deberán depender de rutas específicas de macOS.

---

# 2. Objetivo general

Construir una plataforma de IA orientada a datos que permita:

1. Conectarse a múltiples bases de datos.
2. Consultar bases de datos mediante lenguaje natural.
3. Generar consultas complejas utilizando el esquema real de cada base.
4. Ejecutar exclusivamente operaciones de lectura.
5. Generar sentencias de escritura sin ejecutarlas.
6. Consultar metadatos de tablas, columnas, índices y relaciones.
7. Leer definiciones de procedimientos almacenados, funciones, vistas y triggers.
8. Explicar objetos de base de datos mediante el LLM.
9. Incorporar documentación técnica mediante RAG.
10. Mantener un catálogo o caché actualizable de schemas.
11. Integrarse con Open WebUI.
12. Exponer sus capacidades mediante MCP.
13. Poder añadir nuevas conexiones editando un archivo `connections.yaml`.
14. Ejecutarse completamente mediante Docker Compose.
15. Mantener auditoría de las operaciones ejecutadas.

---

# 3. Flujo conceptual

La arquitectura conceptual será:

```text
Usuario
   │
   ▼
Open WebUI
   │
   ▼
LLM configurado en Open WebUI
OpenAI / BytePlus / Ollama / Claude / otro
   │
   ▼
Data Platform MCP
   │
   ├── MCP Tools
   ├── RAG Tools
   ├── SQL Validation
   ├── Metadata Catalog
   └── Audit
   │
   ▼
Services Layer
   │
   ▼
Adapters Layer
   │
   ▼
Database Engines
```

La implementación preferida debe mantener al MCP independiente del proveedor de LLM.

El flujo recomendado para una consulta es:

```text
1. El usuario formula una pregunta en Open WebUI.
2. El LLM identifica la conexión solicitada.
3. El LLM consulta las herramientas MCP para obtener schemas y metadatos.
4. El LLM genera una consulta.
5. El MCP valida la consulta.
6. Si es de lectura, el MCP puede ejecutarla.
7. Si es de escritura o DDL, el MCP solamente devuelve el SQL generado.
8. El resultado se devuelve al LLM.
9. El LLM explica el resultado al usuario.
```

Como extensión futura, el backend podrá disponer de una abstracción opcional de proveedores LLM, pero el núcleo MCP no debe depender obligatoriamente de una API key.

---

# 4. Casos de uso principales

## 4.1 Consulta de lectura

Ejemplo de solicitud:

```text
Dame el INNER JOIN entre productos y ventas de la conexión postgres-demo.
```

El sistema deberá:

1. Identificar `postgres-demo`.
2. Consultar el esquema almacenado en caché.
3. Detectar relaciones entre tablas.
4. Generar SQL compatible con PostgreSQL.
5. Validar que sea una consulta de lectura.
6. Ejecutarla con timeout y límite de filas.
7. Devolver:

   * SQL generado.
   * Resultado.
   * Número de filas.
   * Tiempo de ejecución.
   * Advertencias, cuando existan.

## 4.2 Consulta compleja

El sistema deberá poder asistir en consultas que incluyan:

* Múltiples JOIN.
* CTE.
* Subconsultas.
* Funciones ventana.
* Agregaciones.
* Filtros complejos.
* Transformaciones.
* Paginación.
* Consultas sobre vistas.
* Consultas específicas del dialecto.

Nunca debe inventar tablas o columnas sin advertirlo.

## 4.3 Generación de escritura

Ejemplo:

```text
Genera un UPDATE para aumentar en 10% el precio de los productos sin stock.
```

El sistema podrá generar:

* `INSERT`.
* `UPDATE`.
* `DELETE`.
* `MERGE`.
* `CREATE`.
* `ALTER`.
* `DROP`.
* DDL o DML específico del motor.

Sin embargo:

* Nunca deberá ejecutar estas sentencias.
* Deberá devolverlas únicamente como texto.
* Deberá marcarlas claramente como no ejecutadas.
* Deberá explicar el posible impacto.
* No deberá existir una opción de confirmación que permita ejecutarlas posteriormente desde MCP.

## 4.4 Explicación de objetos

Ejemplo:

```text
Explícame el procedimiento almacenado procesar_ventas.
```

El sistema deberá:

1. Obtener la definición del objeto.
2. Identificar parámetros, tablas utilizadas y dependencias.
3. Entregar la definición al LLM.
4. Generar una explicación funcional y técnica.
5. No ejecutar el procedimiento.

También deberá soportar, según las capacidades del motor:

* Stored procedures.
* Functions.
* Triggers.
* Views.
* Materialized views.
* Indexes.
* Constraints.
* Sequences.
* Packages, cuando el motor los soporte.

## 4.5 Documentación RAG

El sistema podrá indexar documentación como:

* Diccionarios de datos.
* Reglas de negocio.
* Manuales.
* Archivos Markdown.
* Archivos de texto.
* Documentación de procedimientos.
* Ejemplos SQL.
* Convenciones internas.
* Descripciones funcionales de tablas y columnas.

El LLM deberá poder combinar:

* Metadatos reales de la base.
* Definiciones de objetos.
* Documentación recuperada mediante RAG.

---

# 5. Alcance de motores

Diseña la arquitectura para soportar inicialmente:

## Motores relacionales

* PostgreSQL.
* SQL Server.
* MariaDB/MySQL.
* Informix.
* Oracle, como extensión.
* Otros motores SQL mediante adaptadores futuros.

## Motores documentales

* MongoDB.

MongoDB no utiliza SQL de manera nativa. Por tanto:

* Los adaptadores deberán declarar el lenguaje de consulta soportado.
* PostgreSQL, SQL Server, MariaDB, Informix y Oracle utilizarán SQL.
* MongoDB utilizará filtros `find` o pipelines de agregación.
* En MongoDB deberán bloquearse operaciones como:

  * `insertOne`.
  * `insertMany`.
  * `updateOne`.
  * `updateMany`.
  * `deleteOne`.
  * `deleteMany`.
  * `$out`.
  * `$merge`.
  * Operaciones administrativas o de modificación.

No intentes forzar a MongoDB a implementar una interfaz puramente SQL. Diseña interfaces comunes de capacidades, pero permite diferencias por tipo de motor.

---

# 6. Arquitectura por capas

Utiliza una arquitectura limpia, modular y extensible.

Estructura sugerida:

```text
app/
├── main.py
├── api/
├── adapters/
│   ├── base/
│   ├── postgres/
│   ├── sqlserver/
│   ├── mariadb/
│   ├── informix/
│   └── mongodb/
├── services/
├── tools/
├── models/
├── repositories/
├── config/
├── catalog/
├── rag/
├── prompts/
├── security/
├── audit/
├── exceptions/
└── utils/

database/
├── init/
│   ├── 01-schema.sql
│   └── 02-data.sql
└── docs/

tests/
├── unit/
├── integration/
├── security/
└── fixtures/

docs/
├── architecture.md
├── configuration.md
├── connections.md
├── mcp-tools.md
├── security.md
├── deployment.md
├── openwebui-integration.md
└── development.md

scripts/
├── start.sh
├── stop.sh
├── test.sh
├── lint.sh
├── refresh-catalog.sh
└── smoke-test.sh

connections.yaml
compose.yaml
compose.override.yaml
Dockerfile
.env.example
pyproject.toml
README.md
CHANGELOG.md
TASKS.md
```

La estructura puede ajustarse si existe una razón técnica clara, pero debe conservar la separación de responsabilidades.

---

# 7. Stack técnico recomendado

Utiliza como línea base:

* Python 3.12.
* FastAPI para endpoints administrativos y health checks.
* FastMCP o SDK oficial compatible para exponer herramientas MCP.
* Pydantic para configuración y modelos.
* PyYAML para cargar conexiones.
* SQLAlchemy cuando sea apropiado.
* Drivers específicos por motor cuando SQLAlchemy no sea suficiente.
* `sqlglot` o una alternativa robusta para parseo y validación SQL.
* `pytest` para pruebas.
* `pytest-asyncio` cuando se utilice código asíncrono.
* `ruff` para lint y formato.
* `mypy` o `pyright` para validación de tipos.
* Logging estructurado en JSON.
* Docker y Docker Compose.
* Un almacén vectorial desacoplado para RAG, preferentemente Qdrant.
* SQLite o una base interna equivalente para auditoría y catálogo en el MVP, siempre que la capa de persistencia sea reemplazable.

No agregues dependencias innecesarias.

Fija versiones compatibles en `pyproject.toml` o utiliza rangos de versión controlados.

---

# 8. Configuración de conexiones

Las conexiones deberán declararse en `connections.yaml`.

Ejemplo inicial:

```yaml
connections:
  - id: postgres-demo
    name: PostgreSQL Demo
    type: postgres
    host: postgres-lab
    port: 5432
    database: demo
    username: postgres
    password_env: POSTGRES_DEMO_PASSWORD
    readonly: true
    enabled: true
    connect_timeout_seconds: 10
    query_timeout_seconds: 30
    max_rows: 500

  - id: sqlserver-demo
    name: SQL Server Demo
    type: sqlserver
    host: sqlserver
    port: 1433
    database: demo
    username: sa
    password_env: SQLSERVER_DEMO_PASSWORD
    readonly: true
    enabled: false
    connect_timeout_seconds: 10
    query_timeout_seconds: 30
    max_rows: 500
```

Requisitos:

1. No guardar contraseñas reales directamente en YAML.
2. Resolver secretos mediante variables de entorno.
3. Validar IDs duplicados.
4. Validar tipos de motores soportados.
5. Validar puertos, timeouts y límites.
6. Permitir desactivar conexiones con `enabled: false`.
7. No registrar contraseñas en logs.
8. Enmascarar información sensible al listar conexiones.
9. Permitir recargar la configuración sin reconstruir la imagen.
10. Documentar cómo añadir una conexión nueva.
11. Fallar al inicio si la configuración es inválida.
12. Permitir definir opciones específicas por motor dentro de un bloque `options`.

Ejemplo:

```yaml
options:
  sslmode: prefer
  application_name: data-platform-mcp
```

---

# 9. Interfaces de adaptadores

Crear abstracciones explícitas.

Para motores SQL, considerar una interfaz equivalente a:

```python
class SqlDatabaseAdapter(ABC):
    def test_connection(self) -> ConnectionTestResult:
        ...

    def list_schemas(self) -> list[SchemaInfo]:
        ...

    def list_tables(self, schema: str | None = None) -> list[TableInfo]:
        ...

    def describe_table(self, schema: str, table: str) -> TableDescription:
        ...

    def list_relationships(self, schema: str | None = None) -> list[RelationshipInfo]:
        ...

    def list_views(self, schema: str | None = None) -> list[DatabaseObjectInfo]:
        ...

    def list_procedures(self, schema: str | None = None) -> list[DatabaseObjectInfo]:
        ...

    def get_procedure_definition(
        self,
        schema: str,
        procedure: str,
    ) -> ObjectDefinition:
        ...

    def list_triggers(self, schema: str | None = None) -> list[DatabaseObjectInfo]:
        ...

    def get_trigger_definition(
        self,
        schema: str,
        trigger: str,
    ) -> ObjectDefinition:
        ...

    def explain_query(self, sql: str) -> QueryPlan:
        ...

    def execute_read_query(
        self,
        sql: str,
        parameters: dict | None = None,
        max_rows: int | None = None,
        timeout_seconds: int | None = None,
    ) -> QueryResult:
        ...
```

Para MongoDB, crear una interfaz específica basada en capacidades:

```python
class DocumentDatabaseAdapter(ABC):
    def test_connection(self) -> ConnectionTestResult:
        ...

    def list_databases(self) -> list[str]:
        ...

    def list_collections(self) -> list[CollectionInfo]:
        ...

    def describe_collection(self, collection: str) -> CollectionDescription:
        ...

    def execute_find(
        self,
        collection: str,
        filter: dict,
        projection: dict | None = None,
        limit: int | None = None,
    ) -> QueryResult:
        ...

    def execute_aggregation(
        self,
        collection: str,
        pipeline: list[dict],
        limit: int | None = None,
    ) -> QueryResult:
        ...
```

También crear:

* `AdapterFactory`.
* Registro de adaptadores.
* Matriz de capacidades por motor.
* Excepciones normalizadas.
* Modelos comunes para resultados y errores.

No utilices grandes bloques de `if/elif` para seleccionar motores.

---

# 10. Services Layer

La capa de servicios contendrá la lógica de negocio.

Servicios mínimos:

```text
ConnectionService
CatalogService
MetadataService
QueryGenerationService
QueryValidationService
QueryExecutionService
DatabaseObjectService
RagIngestionService
RagSearchService
AuditService
ConfigurationService
```

Responsabilidades sugeridas:

## ConnectionService

* Listar conexiones.
* Obtener una conexión por ID.
* Probar conectividad.
* Crear adaptadores.
* Exponer información sin secretos.

## CatalogService

* Obtener metadatos desde las bases.
* Guardar metadatos en caché.
* Determinar si el caché está vigente.
* Refrescar una conexión.
* Refrescar todas las conexiones.
* Buscar tablas y columnas.
* Recuperar relaciones.

## QueryValidationService

* Parsear SQL.
* Determinar tipo de sentencia.
* Detectar múltiples sentencias.
* Detectar DML o DDL.
* Detectar comandos administrativos.
* Validar dialecto.
* Aplicar límites.
* Rechazar consultas peligrosas.
* Devolver razones estructuradas.

## QueryExecutionService

* Ejecutar únicamente consultas validadas como lectura.
* Aplicar timeout.
* Aplicar límite de filas.
* Cancelar consultas excedidas.
* Medir duración.
* Normalizar resultados.
* Registrar auditoría.

## DatabaseObjectService

* Listar objetos.
* Obtener definiciones.
* Detectar dependencias cuando sea posible.
* Nunca ejecutar procedimientos o triggers.

## RagIngestionService

* Ingerir documentación.
* Dividir contenido en chunks.
* Añadir metadatos.
* Calcular embeddings mediante una abstracción.
* Guardar vectores.
* Reindexar documentos.

## RagSearchService

* Recuperar fragmentos relevantes.
* Filtrar por conexión, dominio o tipo de documento.
* Devolver citas internas y metadatos del documento.

---

# 11. Herramientas MCP

Implementar, como mínimo, las siguientes herramientas:

```text
hello_world
health_check
list_connections
get_connection_capabilities
test_connection
list_schemas
list_tables
describe_table
list_relationships
search_catalog
refresh_schema_cache
get_schema_cache_status
list_views
get_view_definition
list_procedures
get_procedure_definition
list_triggers
get_trigger_definition
validate_sql
execute_read_query
explain_query
generate_sql
search_documents
list_indexed_documents
explain_database_object
```

## Contratos importantes

### `list_connections`

Debe devolver:

* ID.
* Nombre.
* Tipo.
* Base de datos.
* Estado habilitado.
* Readonly.
* Capacidades.

Nunca debe devolver:

* Password.
* Connection string completa.
* Secretos.
* Parámetros sensibles.

### `generate_sql`

Debe recibir, al menos:

* `connection_id`.
* Solicitud en lenguaje natural.
* Contexto opcional.
* Modo:

  * `read`.
  * `write_generation_only`.

Debe devolver:

* Dialecto.
* SQL generado.
* Tipo de sentencia.
* Tablas detectadas.
* Advertencias.
* Ejecutable por la plataforma: `true` o `false`.
* Razón de bloqueo cuando no sea ejecutable.

El modo `write_generation_only` nunca deberá llamar a `execute_read_query`.

Si el MCP no utiliza internamente un proveedor LLM, esta herramienta puede preparar el contexto estructurado necesario para que el LLM de Open WebUI genere el SQL. Documenta claramente la decisión arquitectónica.

### `validate_sql`

Debe devolver un resultado estructurado:

```json
{
  "valid": true,
  "read_only": true,
  "statement_type": "SELECT",
  "dialect": "postgres",
  "multiple_statements": false,
  "blocked_reasons": [],
  "warnings": [],
  "referenced_objects": []
}
```

### `execute_read_query`

Debe requerir:

* `connection_id`.
* SQL.
* Parámetros opcionales.
* Límite opcional, restringido por el máximo de la conexión.

Antes de ejecutar:

1. Parsear.
2. Validar.
3. Bloquear múltiples sentencias.
4. Confirmar que sea lectura.
5. Aplicar timeout.
6. Aplicar límite.
7. Ejecutar con usuario de solo lectura.
8. Auditar.

### `get_procedure_definition`

Debe devolver solamente la definición y sus metadatos.

Nunca debe ejecutar el procedimiento.

---

# 12. Reglas estrictas de seguridad

La seguridad debe aplicarse en varias capas.

## 12.1 Usuario de base de datos

Documentar que las conexiones productivas deben utilizar usuarios de solo lectura.

No confiar únicamente en la propiedad `readonly: true`.

## 12.2 Transacciones read-only

Cuando el motor lo soporte:

* Abrir transacciones de solo lectura.
* Configurar session read-only.
* Configurar statement timeout.
* Realizar rollback al finalizar.

## 12.3 Parser SQL

Usar un parser real.

No validar únicamente con expresiones regulares.

Bloquear:

* `INSERT`.
* `UPDATE`.
* `DELETE`.
* `DROP`.
* `ALTER`.
* `TRUNCATE`.
* `CREATE`.
* `GRANT`.
* `REVOKE`.
* `MERGE`.
* `CALL`.
* `EXEC`.
* `EXECUTE`.
* `COPY` con escritura.
* Comandos administrativos.
* Múltiples sentencias.
* Consultas que intenten escribir mediante CTE.
* Funciones peligrosas conocidas por motor.

Permitir únicamente una lista explícita de operaciones de lectura.

Considerar como lectura, según el motor:

* `SELECT`.
* `WITH ... SELECT`.
* `EXPLAIN` sobre una consulta de lectura.
* Comandos de metadata explícitamente permitidos.

## 12.4 Límites

Toda ejecución debe tener:

* Timeout configurable.
* Máximo de filas.
* Máximo de bytes serializados, cuando sea posible.
* Límite máximo global.
* Cancelación de consultas.
* Control de conexiones concurrentes.

Si el usuario envía un `LIMIT` mayor que el permitido, aplicar el máximo configurado.

## 12.5 MongoDB

Permitir únicamente:

* `find`.
* Agregaciones de lectura.

Bloquear:

* `$out`.
* `$merge`.
* `$function`, salvo evaluación explícita y segura.
* JavaScript del lado del servidor.
* Operaciones de escritura.
* Comandos administrativos.

## 12.6 Generación frente a ejecución

Separar físicamente o lógicamente:

```text
GenerateSqlUseCase
ExecuteReadQueryUseCase
```

Una sentencia no ejecutable jamás debe alcanzar el adaptador de ejecución.

## 12.7 Protección de secretos

* No incluir secretos en logs.
* No incluir secretos en excepciones.
* No incluir secretos en respuestas MCP.
* No guardar secretos en auditoría.
* No versionar `.env`.
* Incluir `.env.example`.
* Enmascarar host y usuario cuando se configure ese nivel de privacidad.

---

# 13. Catálogo y caché de schemas

Implementar un catálogo interno para almacenar:

* Conexión.
* Schemas.
* Tablas.
* Columnas.
* Tipos.
* Primary keys.
* Foreign keys.
* Índices.
* Constraints.
* Vistas.
* Procedimientos.
* Funciones.
* Triggers.
* Fecha de actualización.
* Hash o versión del esquema, cuando sea posible.

Configuración sugerida:

```yaml
catalog:
  enabled: true
  refresh_interval_minutes: 60
  refresh_on_startup: true
  stale_after_minutes: 120
  include_procedure_definitions: false
  include_trigger_definitions: false
```

Requisitos:

1. Refresh manual por conexión.
2. Refresh global.
3. Refresh periódico.
4. No bloquear completamente el servidor durante el refresh.
5. Marcar caché obsoleto.
6. Usar el último caché válido si una conexión está temporalmente caída.
7. Registrar errores de actualización.
8. Permitir excluir schemas del sistema.
9. Permitir incluir o excluir objetos por patrón.
10. No almacenar datos de las tablas, solamente metadatos y definiciones autorizadas.

---

# 14. RAG

Implementar un módulo RAG desacoplado.

## Fuentes iniciales

* `.md`.
* `.txt`.
* `.sql`.
* `.json`.
* `.yaml`.

Dejar preparada la extensión para PDF y otros formatos.

## Metadatos por documento

```json
{
  "document_id": "string",
  "title": "string",
  "source": "string",
  "connection_id": "optional",
  "domain": "optional",
  "document_type": "data_dictionary",
  "version": "optional",
  "indexed_at": "datetime"
}
```

## Requisitos

* Chunking configurable.
* Overlap configurable.
* Reindexación idempotente.
* Eliminación de documento indexado.
* Búsqueda semántica.
* Filtros por conexión.
* Filtros por dominio.
* Respuesta con score y referencia de origen.
* Abstracción de embeddings.
* No acoplar el núcleo a un proveedor específico.
* Poder utilizar embeddings locales en una fase futura.

El RAG no debe reemplazar el catálogo técnico. Ambos deben complementarse:

```text
Catálogo = estructura real de la base.
RAG = documentación y contexto funcional.
```

---

# 15. Auditoría

Registrar cada operación relevante.

Campos sugeridos:

```text
timestamp
request_id
tool_name
connection_id
operation_type
statement_type
query_hash
query_preview_redacted
validation_result
executed
blocked
blocked_reason
duration_ms
row_count
status
error_code
user_context
```

Requisitos:

* No almacenar secretos.
* No almacenar datos sensibles completos.
* Poder desactivar el almacenamiento del SQL completo.
* Utilizar un hash para correlación.
* Generar logs estructurados JSON.
* Exponer estadísticas básicas.
* Diferenciar claramente:

  * SQL generado.
  * SQL validado.
  * SQL ejecutado.
  * SQL bloqueado.

---

# 16. Base PostgreSQL de laboratorio

Añadir al Docker Compose una base PostgreSQL para pruebas.

```yaml
postgres-lab:
  image: postgres:17
  container_name: postgres-lab
  restart: unless-stopped

  environment:
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: postgres
    POSTGRES_DB: demo

  ports:
    - "5432:5432"

  volumes:
    - postgres-data:/var/lib/postgresql/data
    - ./database/init:/docker-entrypoint-initdb.d

  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U postgres -d demo"]
    interval: 10s
    timeout: 5s
    retries: 10

  networks:
    - ai-platform
```

Agregar el volumen:

```yaml
volumes:
  postgres-data:
```

Los archivos de inicialización deberán ser:

## `database/init/01-schema.sql`

```sql
CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    correo VARCHAR(150) UNIQUE NOT NULL,
    fecha_registro DATE NOT NULL
);

CREATE TABLE productos (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    precio NUMERIC(10,2) NOT NULL,
    stock INTEGER NOT NULL
);

CREATE TABLE ventas (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    producto_id INTEGER NOT NULL REFERENCES productos(id),
    cantidad INTEGER NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## `database/init/02-data.sql`

```sql
INSERT INTO clientes (nombre, correo, fecha_registro) VALUES
('Juan Pérez','juan@example.com','2025-01-10'),
('Ana López','ana@example.com','2025-02-15'),
('Carlos Ruiz','carlos@example.com','2025-03-20');

INSERT INTO productos (nombre, precio, stock) VALUES
('Laptop',15000,20),
('Mouse',350,100),
('Teclado',900,50),
('Monitor',4200,15);

INSERT INTO ventas (cliente_id, producto_id, cantidad) VALUES
(1,1,1),
(1,2,2),
(2,4,1),
(3,3,1),
(2,2,3);
```

Crear adicionalmente un usuario PostgreSQL de solo lectura para que el MCP no se conecte como superusuario.

Agregar un tercer script:

## `database/init/03-readonly-user.sql`

Debe:

* Crear un usuario de solo lectura.
* Otorgar conexión a la base.
* Otorgar uso del schema.
* Otorgar `SELECT` sobre tablas existentes.
* Configurar privilegios por defecto para tablas futuras.
* No otorgar permisos de escritura ni DDL.

La conexión `postgres-demo` deberá utilizar este usuario de solo lectura.

---

# 17. Docker Compose esperado

Crear un `compose.yaml` que incluya al menos:

* `data-platform-mcp`.
* `postgres-lab`.
* `qdrant`, cuando el RAG sea habilitado.
* Volúmenes persistentes.
* Health checks.
* Red `ai-platform`.

Ejemplo conceptual:

```yaml
services:
  data-platform-mcp:
    build:
      context: .
      dockerfile: Dockerfile

    container_name: data-platform-mcp
    restart: unless-stopped

    env_file:
      - .env

    volumes:
      - ./connections.yaml:/app/connections.yaml:ro
      - ./data:/app/data
      - ./documents:/app/documents:ro

    ports:
      - "8000:8000"

    networks:
      - ai-platform

    depends_on:
      postgres-lab:
        condition: service_healthy

  postgres-lab:
    # Configuración definida anteriormente.

  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant
    restart: unless-stopped

    volumes:
      - qdrant-data:/qdrant/storage

    networks:
      - ai-platform

networks:
  ai-platform:
    external: true

volumes:
  postgres-data:
  qdrant-data:
```

No utilizar `latest` en la versión final sin justificarlo. Fijar una versión estable antes de considerar terminado el sprint de despliegue.

---

# 18. Endpoints administrativos

Además de MCP, exponer endpoints HTTP mínimos:

```text
GET /health
GET /ready
GET /version
GET /metrics
```

Opcionales protegidos:

```text
GET /api/connections
POST /api/catalog/refresh/{connection_id}
GET /api/catalog/status
GET /api/audit
```

Los endpoints administrativos sensibles deberán quedar deshabilitados o protegidos por token en producción.

No exponer una API HTTP que permita saltarse las reglas de seguridad del MCP.

---

# 19. Historias de usuario y sprints

Implementa el proyecto utilizando los siguientes sprints.

Cada sprint debe terminar con:

* Código funcional.
* Pruebas.
* Documentación.
* Actualización de `TASKS.md`.
* Actualización de `CHANGELOG.md`.
* Comandos de validación.
* Evidencia de criterios de aceptación.

---

## Sprint 0: Descubrimiento, arquitectura y bootstrap

### Objetivo

Crear la base técnica y documental del proyecto.

### Historias de usuario

#### HU-001 — Inicializar el proyecto

Como desarrollador, quiero una estructura de proyecto modular para poder desarrollar nuevas capacidades sin acoplar componentes.

Criterios de aceptación:

* Existe `pyproject.toml`.
* Existe estructura base por capas.
* El proyecto puede iniciar localmente.
* Existe configuración de lint, formato y tipos.
* Existe un endpoint `/health`.
* Existe un comando reproducible para ejecutar pruebas.

#### HU-002 — Documentar la arquitectura

Como responsable técnico, quiero conocer los componentes y decisiones de arquitectura para poder mantener el sistema.

Criterios de aceptación:

* Existe `docs/architecture.md`.
* Incluye diagrama de componentes.
* Incluye flujo de consulta.
* Incluye separación entre generación y ejecución.
* Incluye decisiones sobre MCP y RAG.
* Incluye limitaciones conocidas.

#### HU-003 — Preparar Docker

Como operador, quiero ejecutar el proyecto mediante Docker para poder desplegarlo en el VPS.

Criterios de aceptación:

* Existe `Dockerfile`.
* Existe `compose.yaml`.
* El contenedor inicia correctamente.
* El servicio se conecta a `ai-platform`.
* Existe health check.
* No se ejecuta como usuario root, salvo justificación técnica.

### Entregables

* Estructura inicial.
* Dockerfile.
* Compose base.
* README inicial.
* Documentación de arquitectura.
* Herramienta `hello_world`.
* Health checks.
* Configuración de pruebas y lint.

---

## Sprint 1: Configuración de conexiones y PostgreSQL

### Objetivo

Implementar carga de conexiones y el primer adaptador funcional.

### Historias de usuario

#### HU-101 — Configurar conexiones por YAML

Como administrador, quiero agregar conexiones en `connections.yaml` para evitar modificar el código.

Criterios de aceptación:

* El archivo se valida con Pydantic.
* Los secretos se obtienen desde variables de entorno.
* IDs duplicados producen un error claro.
* Tipos no soportados producen un error claro.
* Las conexiones deshabilitadas no pueden utilizarse.

#### HU-102 — Listar conexiones

Como usuario de Open WebUI, quiero conocer las conexiones disponibles para seleccionar la base correcta.

Criterios de aceptación:

* Existe la herramienta `list_connections`.
* No muestra contraseñas.
* Muestra tipo, nombre, ID y capacidades.
* Distingue conexiones habilitadas y deshabilitadas.

#### HU-103 — Probar una conexión

Como administrador, quiero probar la conectividad para detectar errores de configuración.

Criterios de aceptación:

* Existe `test_connection`.
* Devuelve éxito, latencia y error normalizado.
* Nunca muestra secretos.
* Tiene timeout.

#### HU-104 — Consultar PostgreSQL

Como usuario, quiero conectarme a PostgreSQL para consultar sus metadatos.

Criterios de aceptación:

* Existe `PostgresAdapter`.
* Implementa la interfaz SQL.
* Puede listar schemas.
* Puede listar tablas.
* Puede describir tablas.
* Puede detectar primary y foreign keys.

### Entregables

* `connections.yaml`.
* `.env.example`.
* Modelos de configuración.
* `AdapterFactory`.
* `PostgresAdapter`.
* PostgreSQL de laboratorio.
* Usuario de solo lectura.
* Pruebas unitarias e integración.

---

## Sprint 2: Catálogo y caché de schemas

### Objetivo

Evitar consultar todos los metadatos en cada solicitud.

### Historias de usuario

#### HU-201 — Actualizar catálogo

Como administrador, quiero actualizar los schemas para que el asistente utilice información vigente.

Criterios de aceptación:

* Existe `refresh_schema_cache`.
* Puede actualizar una conexión.
* Puede actualizar todas.
* Registra fecha, estado y errores.
* No almacena filas de negocio.

#### HU-202 — Consultar catálogo

Como LLM, quiero buscar tablas y columnas para generar consultas correctas.

Criterios de aceptación:

* Existe `search_catalog`.
* Busca tablas, columnas y descripciones.
* Permite filtrar por conexión.
* Devuelve relaciones relevantes.
* Indica cuándo el caché está obsoleto.

#### HU-203 — Refresh periódico

Como administrador, quiero actualizar automáticamente el catálogo para evitar metadatos desactualizados.

Criterios de aceptación:

* Intervalo configurable.
* No se ejecutan dos refresh simultáneos para una misma conexión.
* Los fallos no eliminan el último caché válido.
* Existe estado observable.

### Entregables

* `CatalogService`.
* Repositorio de catálogo.
* Scheduler.
* Herramientas MCP de catálogo.
* Pruebas de expiración y concurrencia.
* Documentación de caché.

---

## Sprint 3: Validación y ejecución SQL segura

### Objetivo

Ejecutar exclusivamente consultas de lectura.

### Historias de usuario

#### HU-301 — Validar SQL

Como operador de seguridad, quiero validar cada consulta para evitar modificaciones de datos.

Criterios de aceptación:

* Se utiliza un parser SQL.
* Se detecta el tipo de sentencia.
* Se bloquean múltiples sentencias.
* Se bloquea DML y DDL.
* Se detectan escrituras dentro de CTE.
* Se devuelve una razón estructurada.

#### HU-302 — Ejecutar SELECT

Como usuario, quiero ejecutar consultas de lectura para obtener información.

Criterios de aceptación:

* Solo se ejecuta SQL validado.
* Se utiliza conexión readonly.
* Se aplica timeout.
* Se aplica límite de filas.
* Se devuelven columnas y filas.
* Se devuelve duración.
* Se registra auditoría.

#### HU-303 — Generar escritura sin ejecutarla

Como usuario, quiero generar un UPDATE, DELETE o DROP para revisarlo manualmente.

Criterios de aceptación:

* La plataforma devuelve la sentencia.
* La sentencia se marca como no ejecutable.
* Nunca llega al adaptador de ejecución.
* Se muestra una advertencia de impacto.
* Existe una prueba que demuestre que no se ejecuta.

#### HU-304 — Explicar plan de ejecución

Como desarrollador, quiero obtener el plan de una consulta de lectura para analizar su rendimiento.

Criterios de aceptación:

* Existe `explain_query`.
* Solo acepta consultas de lectura.
* No utiliza `ANALYZE` de forma predeterminada.
* Devuelve un plan normalizado o textual.

### Entregables

* `QueryValidationService`.
* `QueryExecutionService`.
* Modelos de validación.
* Políticas por dialecto.
* Pruebas de ataques y bypass.
* Auditoría inicial.
* Herramientas `validate_sql`, `execute_read_query` y `explain_query`.

---

## Sprint 4: Herramientas MCP completas

### Objetivo

Exponer capacidades de base de datos mediante contratos MCP estables.

### Historias de usuario

#### HU-401 — Explorar tablas

Como usuario, quiero listar y describir tablas desde Open WebUI.

Criterios de aceptación:

* Funcionan `list_schemas`, `list_tables` y `describe_table`.
* Las respuestas tienen modelos estructurados.
* Los errores son entendibles.
* Se identifica la conexión utilizada.

#### HU-402 — Consultar relaciones

Como LLM, quiero conocer foreign keys para generar JOIN correctos.

Criterios de aceptación:

* Existe `list_relationships`.
* Devuelve tabla origen y destino.
* Devuelve columnas relacionadas.
* Incluye cardinalidad cuando pueda inferirse.

#### HU-403 — Contratos versionados

Como integrador, quiero contratos estables para evitar romper Open WebUI.

Criterios de aceptación:

* Las herramientas están documentadas.
* Los modelos tienen versionado.
* Los cambios incompatibles se registran.
* Existen pruebas de contrato.

### Entregables

* Servidor MCP funcional.
* Transporte local y transporte de red compatible.
* Catálogo de herramientas.
* Documentación de entrada y salida.
* Pruebas de contrato.
* Script de smoke test.

---

## Sprint 5: Generación de consultas mediante lenguaje natural

### Objetivo

Construir el contexto necesario para generar consultas complejas y correctas.

### Historias de usuario

#### HU-501 — Generar SQL usando metadata

Como usuario, quiero describir una consulta en lenguaje natural para obtener SQL compatible con la base seleccionada.

Criterios de aceptación:

* Recibe `connection_id`.
* Recupera tablas, columnas y relaciones.
* Respeta el dialecto.
* No inventa objetos sin advertencia.
* Devuelve tablas utilizadas y supuestos.

#### HU-502 — Ejecutar una consulta generada de lectura

Como usuario, quiero obtener resultados cuando la consulta generada sea segura.

Criterios de aceptación:

* El SQL se valida antes de ejecutar.
* Se devuelve SQL y resultado.
* Un SQL bloqueado nunca se ejecuta.
* Los errores del motor se normalizan.
* No se realizan reintentos que puedan cambiar el significado de la consulta.

#### HU-503 — Solicitar aclaraciones técnicas

Como usuario, quiero que el sistema detecte ambigüedades para evitar consultar la tabla incorrecta.

Criterios de aceptación:

* Detecta varias tablas o columnas con nombres similares.
* Devuelve opciones concretas.
* No ejecuta una consulta basada en una suposición peligrosa.
* Las ambigüedades se presentan de forma estructurada.

### Entregables

* `QueryGenerationService`.
* Constructor de contexto.
* Prompts versionados.
* Modelos de generación.
* Casos de prueba con JOIN, CTE, ventanas y agregaciones.
* Documentación del flujo natural-language-to-query.

---

## Sprint 6: Objetos de base de datos y explicaciones

### Objetivo

Leer y explicar procedimientos, triggers, vistas y otros objetos.

### Historias de usuario

#### HU-601 — Leer procedimientos

Como desarrollador, quiero consultar la definición de un procedimiento para entender su lógica.

Criterios de aceptación:

* Puede listar procedimientos.
* Puede obtener su definición.
* Nunca ejecuta el procedimiento.
* Devuelve parámetros y dependencias cuando estén disponibles.

#### HU-602 — Leer triggers

Como desarrollador, quiero consultar triggers para identificar efectos secundarios.

Criterios de aceptación:

* Puede listar triggers.
* Puede recuperar su definición.
* Relaciona el trigger con su tabla.
* No ejecuta acciones del trigger.

#### HU-603 — Explicar objetos

Como usuario, quiero una explicación estructurada de un objeto de base de datos.

Criterios de aceptación:

* La respuesta incluye propósito.
* Entradas y salidas.
* Tablas afectadas.
* Reglas principales.
* Riesgos y efectos secundarios.
* La explicación distingue hechos del código e inferencias.

### Entregables

* `DatabaseObjectService`.
* Herramientas MCP de objetos.
* Soporte PostgreSQL completo.
* Interfaces para otros motores.
* Pruebas.
* Documentación.

---

## Sprint 7: RAG documental

### Objetivo

Combinar schemas reales con documentación funcional.

### Historias de usuario

#### HU-701 — Indexar documentación

Como administrador, quiero indexar documentos para enriquecer las respuestas.

Criterios de aceptación:

* Soporta Markdown, texto, SQL, JSON y YAML.
* El proceso es idempotente.
* Se almacenan metadatos.
* Se puede reindexar un archivo modificado.
* Se puede eliminar un documento.

#### HU-702 — Buscar documentación

Como usuario, quiero recuperar reglas de negocio relacionadas con mi consulta.

Criterios de aceptación:

* Existe `search_documents`.
* Permite filtrar por conexión y dominio.
* Devuelve fragmentos con origen.
* Devuelve score.
* No mezcla documentos de conexiones incompatibles sin advertirlo.

#### HU-703 — Combinar RAG y catálogo

Como LLM, quiero recibir metadata técnica y reglas funcionales para generar mejores consultas.

Criterios de aceptación:

* Se distinguen ambos tipos de contexto.
* El catálogo tiene prioridad para nombres técnicos.
* La documentación puede aportar significado funcional.
* Los conflictos se reportan.

### Entregables

* Qdrant.
* Servicios RAG.
* Pipeline de ingesta.
* Herramientas MCP.
* Documentos de ejemplo.
* Pruebas de recuperación y filtros.

---

## Sprint 8: Integración con Open WebUI

### Objetivo

Permitir que Open WebUI utilice las herramientas del Data Platform MCP.

### Historias de usuario

#### HU-801 — Conectar Open WebUI al MCP

Como usuario, quiero utilizar el MCP desde Open WebUI para consultar bases de datos.

Criterios de aceptación:

* Ambos servicios comparten `ai-platform`.
* Open WebUI puede alcanzar el servidor MCP por nombre de servicio.
* Existe documentación paso a paso.
* Existe prueba de conectividad.
* No se requiere exponer el MCP públicamente cuando Open WebUI está en la misma red.

#### HU-802 — Consultar PostgreSQL desde el chat

Como usuario, quiero pedir un JOIN entre ventas y productos y obtener resultados.

Criterios de aceptación:

* El LLM identifica `postgres-demo`.
* Consulta el esquema.
* Genera SQL válido.
* El MCP lo valida.
* El MCP ejecuta la consulta.
* El usuario recibe SQL y resultados.

#### HU-803 — Generar DML sin ejecutarlo

Como usuario, quiero solicitar un DELETE y recibir solamente el SQL.

Criterios de aceptación:

* Se muestra el SQL.
* Se marca como no ejecutado.
* Existe registro de bloqueo.
* La base no cambia.
* Una prueba posterior confirma que los datos permanecen intactos.

### Entregables

* Guía `docs/openwebui-integration.md`.
* Configuración de red.
* Ejemplos de prompts.
* Pruebas end-to-end.
* Troubleshooting.
* Demostración de lectura y bloqueo de escritura.

---

## Sprint 9: Adaptadores adicionales

### Objetivo

Ampliar motores sin modificar los servicios centrales.

### Historias de usuario

#### HU-901 — SQL Server

Como usuario, quiero consultar SQL Server utilizando las mismas herramientas principales.

#### HU-902 — MariaDB

Como usuario, quiero consultar MariaDB con soporte de su dialecto.

#### HU-903 — Informix

Como usuario, quiero explorar tablas, vistas, procedimientos y consultar Informix.

#### HU-904 — MongoDB

Como usuario, quiero ejecutar consultas de lectura y pipelines de agregación en MongoDB.

### Criterios generales

* Cada adaptador declara sus capacidades.
* Las diferencias se documentan.
* Existe suite de pruebas de contrato.
* No se añaden condiciones específicas de motor a los servicios centrales.
* Los drivers propietarios o con restricciones se documentan.
* Un adaptador no disponible no impide iniciar los demás.
* Informix debe contemplar que la disponibilidad del driver puede depender del entorno.
* MongoDB utiliza validación específica de operaciones y pipelines.

### Entregables

* Adaptadores.
* Matriz de capacidades.
* Contenedores de laboratorio cuando sea viable.
* Pruebas por motor.
* Documentación de configuración.

---

## Sprint 10: Hardening y operación

### Objetivo

Preparar el sistema para uso controlado en el VPS.

### Historias de usuario

#### HU-1001 — Observabilidad

Como operador, quiero métricas y logs para diagnosticar problemas.

Criterios de aceptación:

* Logs JSON.
* Request ID.
* Métricas de latencia.
* Métricas de consultas bloqueadas.
* Métricas de errores.
* Health y readiness diferenciados.

#### HU-1002 — Control de concurrencia

Como operador, quiero limitar el consumo de recursos para proteger el VPS.

Criterios de aceptación:

* Pool configurable.
* Límite de consultas concurrentes.
* Timeout.
* Backpressure o respuesta controlada.
* Pruebas básicas de carga.

#### HU-1003 — Despliegue seguro

Como administrador, quiero desplegar sin exponer secretos ni puertos innecesarios.

Criterios de aceptación:

* Secretos fuera del repositorio.
* Puertos mínimos.
* Usuario no root.
* Volúmenes documentados.
* Política de reinicio.
* Backup del catálogo y RAG.
* Guía de actualización y rollback.

### Entregables

* Métricas.
* Hardening Docker.
* Guía de operación.
* Pruebas de carga básicas.
* Checklist de seguridad.
* Estrategia de backup y restauración.

---

# 20. Consultas de prueba obligatorias

Crear pruebas end-to-end con PostgreSQL.

## Consulta 1: JOIN

Solicitud:

```text
Muestra cada venta con el nombre del cliente, producto, cantidad, precio unitario y total de la venta.
```

SQL esperado conceptualmente:

```sql
SELECT
    v.id AS venta_id,
    c.nombre AS cliente,
    p.nombre AS producto,
    v.cantidad,
    p.precio AS precio_unitario,
    v.cantidad * p.precio AS total,
    v.fecha
FROM ventas v
INNER JOIN clientes c
    ON c.id = v.cliente_id
INNER JOIN productos p
    ON p.id = v.producto_id
ORDER BY v.id;
```

## Consulta 2: Agregación

```text
Obtén el total vendido por producto y ordénalo del mayor al menor.
```

## Consulta 3: CTE

```text
Utiliza un CTE para calcular el gasto total por cliente y mostrar solamente clientes con gasto mayor a 1,000.
```

## Consulta 4: Función ventana

```text
Clasifica las ventas por importe dentro de cada cliente utilizando ROW_NUMBER.
```

## Consulta 5: Escritura bloqueada

```text
Elimina todas las ventas anteriores al 1 de enero de 2026.
```

Resultado esperado:

* Se genera el `DELETE`.
* `executed=false`.
* Se muestra advertencia.
* No se elimina ninguna fila.

## Consulta 6: DDL bloqueado

```text
Elimina la tabla ventas.
```

Resultado esperado:

* Se genera o valida el `DROP TABLE`.
* Se clasifica como DDL.
* No se ejecuta.
* La tabla sigue existiendo.

## Consulta 7: Ataque con múltiples sentencias

```sql
SELECT * FROM ventas; DROP TABLE ventas;
```

Resultado esperado:

* Consulta rechazada.
* Razón: múltiples sentencias y operación DDL.
* Ninguna parte debe ejecutarse.

## Consulta 8: Escritura oculta en CTE

Crear una prueba con una sentencia de modificación dentro de un CTE.

Resultado esperado:

* Consulta bloqueada.
* Ninguna modificación realizada.

---

# 21. Pruebas mínimas

Implementar:

## Unitarias

* Validación de configuración.
* Factory de adaptadores.
* Parser SQL.
* Clasificación de sentencias.
* Aplicación de límites.
* Enmascaramiento de secretos.
* Modelos MCP.
* Servicios de catálogo.

## Integración

* Conexión PostgreSQL.
* Listado de tablas.
* Descripción de tablas.
* Foreign keys.
* Ejecución de SELECT.
* Timeout.
* Límite de filas.
* Usuario readonly.
* Auditoría.

## Seguridad

* DML bloqueado.
* DDL bloqueado.
* Múltiples sentencias.
* Comentarios utilizados para ocultar comandos.
* CTE con escritura.
* Procedimientos no ejecutados.
* SQL inválido.
* Límites excesivos.
* MongoDB `$out` y `$merge`, cuando se implemente MongoDB.

## End-to-end

```text
Open WebUI/cliente de prueba
    → MCP
    → catálogo
    → validación
    → PostgreSQL
    → respuesta
```

---

# 22. Documentación requerida

El proyecto no se considerará terminado sin:

## `README.md`

Debe incluir:

* Objetivo.
* Arquitectura.
* Requisitos.
* Inicio rápido.
* Configuración.
* Docker.
* Ejemplos.
* Seguridad.
* Estado de motores.
* Roadmap.

## `docs/connections.md`

* Formato de `connections.yaml`.
* Variables de entorno.
* Ejemplos por motor.
* SSL.
* Troubleshooting.

## `docs/security.md`

* Modelo de amenazas.
* Capas de defensa.
* Operaciones permitidas.
* Operaciones bloqueadas.
* Limitaciones.
* Responsabilidades del administrador.

## `docs/mcp-tools.md`

Para cada tool:

* Nombre.
* Objetivo.
* Parámetros.
* Respuesta.
* Errores.
* Ejemplo.

## `docs/openwebui-integration.md`

* Conexión de red.
* URL interna.
* Configuración requerida.
* Prueba.
* Ejemplos de conversación.
* Errores comunes.

## `docs/deployment.md`

* VPS Linux.
* Docker Compose.
* Variables.
* Volúmenes.
* Logs.
* Backup.
* Upgrade.
* Rollback.

---

# 23. Reglas de implementación para Codex

Sigue estas reglas durante todo el desarrollo:

1. Antes de modificar código, inspecciona el repositorio.
2. No elimines archivos existentes sin justificarlo.
3. Mantén compatibilidad con arquitectura ARM64, debido al VPS Oracle.
4. No agregues credenciales reales.
5. No uses contraseñas en ejemplos que puedan confundirse con producción.
6. No expongas el MCP públicamente por defecto.
7. No ejecutes DML o DDL.
8. No simules que una prueba pasó si no fue ejecutada.
9. No dejes funciones críticas con `TODO`, `pass` o implementaciones falsas.
10. Si una dependencia o driver no puede instalarse, documenta el bloqueo y crea una interfaz verificable, sin fingir soporte.
11. Ejecuta pruebas después de cada cambio importante.
12. Mantén código tipado.
13. Utiliza excepciones de dominio.
14. Evita capturar `Exception` sin tratamiento.
15. Utiliza logging estructurado.
16. No registres información sensible.
17. Mantén pequeñas las funciones y clases.
18. Evita dependencias circulares.
19. Mantén los modelos de transporte separados de los modelos de dominio.
20. Documenta las decisiones relevantes mediante ADR si es necesario.
21. Actualiza `TASKS.md` al completar cada historia.
22. Actualiza `CHANGELOG.md`.
23. Muestra los comandos exactos utilizados para validar el sprint.
24. No avances al siguiente sprint si las pruebas del sprint actual fallan, salvo que documentes claramente el bloqueo.
25. Prioriza primero un MVP sólido con PostgreSQL.
26. No comprometas la seguridad para acelerar la implementación.
27. Todas las consultas deben usar parámetros cuando existan valores proporcionados externamente.
28. Nunca concatenes valores del usuario directamente en SQL.
29. Nombres dinámicos de tablas o columnas deben validarse contra el catálogo.
30. Los resultados deben ser serializables y manejar correctamente fechas, decimales, UUID, binarios y valores nulos.

---

# 24. Forma de trabajo esperada

Comienza realizando lo siguiente:

## Paso 1: Inspección

* Lista los archivos actuales.
* Identifica qué componentes ya existen.
* Identifica qué componentes pueden reutilizarse.
* Detecta inconsistencias con esta especificación.

## Paso 2: Documentación inicial

Crea o actualiza:

```text
docs/architecture.md
TASKS.md
README.md
```

## Paso 3: Plan ejecutable

En `TASKS.md`, registra:

* Sprint.
* Historia.
* Estado.
* Dependencias.
* Archivos afectados.
* Pruebas requeridas.
* Criterios de aceptación.
* Bloqueos.

Utiliza estados:

```text
TODO
IN_PROGRESS
BLOCKED
DONE
```

## Paso 4: Implementación

Implementa primero el Sprint 0.

Después continúa con Sprint 1 y los siguientes de manera incremental.

## Paso 5: Validación

Al finalizar cada sprint, entrega un resumen con:

```text
Sprint completado:
Historias completadas:
Archivos creados:
Archivos modificados:
Pruebas ejecutadas:
Resultado de pruebas:
Comandos para ejecutar:
Riesgos pendientes:
Siguiente sprint:
```

---

# 25. Definición de terminado

Una historia se considera terminada únicamente cuando:

* El código está implementado.
* Existen pruebas.
* Las pruebas pasan.
* Está documentada.
* No contiene secretos.
* Respeta las capas.
* Tiene manejo de errores.
* Tiene logs adecuados.
* Cumple sus criterios de aceptación.
* Se actualizó `TASKS.md`.
* Se actualizó `CHANGELOG.md`.

El proyecto se considera funcional cuando sea posible ejecutar:

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
docker compose logs data-platform-mcp
```

Y posteriormente:

1. Probar `postgres-demo`.
2. Listar tablas.
3. Describir `ventas`.
4. Consultar relaciones.
5. Ejecutar un JOIN de lectura.
6. Bloquear un DELETE.
7. Bloquear un DROP.
8. Recuperar documentación mediante RAG.
9. Utilizar las herramientas desde Open WebUI o desde un cliente MCP de prueba.

---

# 26. Primera instrucción de ejecución

Comienza ahora con estas acciones:

1. Inspecciona el repositorio actual.
2. Presenta un diagnóstico breve.
3. Propón la arquitectura definitiva basándote en esta especificación.
4. Crea `TASKS.md` con todos los sprints e historias de usuario.
5. Crea o actualiza `docs/architecture.md`.
6. Implementa el Sprint 0.
7. Ejecuta las pruebas y validaciones del Sprint 0.
8. Muestra un resumen de resultados.
9. Después continúa con el Sprint 1 si el Sprint 0 queda correctamente validado.

No reduzcas el alcance silenciosamente. Cuando alguna función deba posponerse, regístrala explícitamente en `TASKS.md`, indicando motivo, dependencia y sprint objetivo.

