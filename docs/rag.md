# RAG documental

## Alcance

Sprint 7 añade un subsistema RAG desacoplado para indexar documentación funcional (diccionarios de
datos, reglas de negocio, ejemplos SQL) y recuperarla por búsqueda semántica. El RAG **no
reemplaza** el catálogo técnico de Sprint 2:

```text
Catálogo = estructura real de la base (schemas, tablas, columnas, PK/FK, procedimientos, triggers).
RAG      = documentación y contexto funcional (reglas de negocio, convenciones, ejemplos).
```

Está deshabilitado por defecto (`rag.enabled: false`) y requiere un proveedor de embeddings
configurado explícitamente, igual que la generación LLM de Sprint 5.

## Fuente de documentos

Los documentos se leen desde un directorio montado de solo lectura, por defecto `/app/documents`
(`rag.documents_path`), nunca subidos vía una tool MCP. Formatos soportados: `.md`, `.txt`, `.sql`,
`.json`, `.yaml`, `.yml` (extensible a PDF en el futuro). Un archivo con otra extensión o que exceda
`rag.max_document_bytes` se rechaza sin indexarse.

## Convención de organización — segmentos `clave=valor`

`connection_id`, `domain`, `document_type` y `version` se derivan de segmentos de directorio con la
forma `clave=valor` en cualquier profundidad y orden dentro de la ruta relativa a
`documents_path`. Claves reconocidas: `connection`, `domain`, `type`, `version`, `title`. Un
segmento que no matchea el patrón (`^[a-z][a-z0-9_]*=[A-Za-z0-9][A-Za-z0-9_.-]*$`) se ignora y sirve
solo de organización libre para el humano.

```text
documents/data-dictionary-global.md
  → connection_id=None, domain=None, document_type="documentation" (por extensión)

documents/connection=postgres-demo/domain=ventas/reglas-negocio-ventas.md
  → connection_id="postgres-demo", domain="ventas", document_type="documentation"

documents/connection=postgres-demo/type=sql_reference/consultas-referencia.sql
  → connection_id="postgres-demo", domain=None, document_type="sql_reference"
```

`document_type` por defecto según extensión si no hay segmento `type=`: `.md`/`.txt` →
`documentation`; `.sql` → `sql_reference`; `.json`/`.yaml`/`.yml` → `structured_reference`. `title`
por defecto es el nombre de archivo sin extensión, con `-`/`_` convertidos a espacios y
capitalizados; puede sobreescribirse con un segmento `title=`.

Se eligió esta convención — en vez de una ruta posicional fija (`documents/<connection_id>/<domain>/archivo.md`)
o frontmatter YAML — porque no impone una profundidad de carpetas concreta, no obliga a inventar un
valor sentinel para "sin conexión"/"sin dominio", y no rompe la sintaxis nativa de `.sql`/`.json`/
`.yaml` (un frontmatter antepuesto a esos formatos invalidaría el archivo fuente, que además es de
solo lectura).

`document_id` es determinista: `sha256(ruta_relativa_posix)`. Mover o renombrar un archivo se trata
como "documento eliminado" + "documento nuevo" (nuevos embeddings) — limitación aceptada por
simplicidad e idempotencia.

## Indexación

`refresh_document_index(source?)` reindexa un archivo puntual o hace un barrido completo del
directorio. Es idempotente: un documento cuyo hash de contenido no cambió se marca `unchanged` y
**no recalcula embeddings**. Un documento nuevo o modificado reemplaza por completo sus vectores
anteriores (nunca deja chunks huérfanos de una versión previa más larga). Un documento que ya no
existe en disco se marca `removed` solo durante un barrido completo. Además del disparo manual, un
scheduler no bloqueante (mismo patrón que `CatalogScheduler`) reindexa periódicamente según
`rag.refresh_interval_minutes`, con `refresh_on_startup` opcional.

## Búsqueda

`search_documents(query, connection_id?, domain?, max_results?)` calcula el embedding de la
pregunta y consulta el vector store. Los documentos sin `connection_id`/`domain` (globales) se
incluyen siempre, sin importar el filtro pedido. Si no se pasa `connection_id` y el resultado
mezcla varias conexiones, la respuesta incluye `mixed_connections_warning: true` para que el
cliente lo sepa explícitamente — nunca oculta la mezcla en silencio.

## Combinar RAG y catálogo (HU-703)

No existe una tool que fusione ambos automáticamente. El patrón recomendado para un cliente MCP
externo (o el flujo de generación de SQL) es llamar **ambas fuentes por separado** para la misma
pregunta/conexión y componerlas en un único prompt:

1. `search_catalog` / `describe_table` / `list_relationships` → estructura técnica real (nombres
   exactos de tabla/columna, tipos, relaciones).
2. `search_documents` → contexto funcional (qué significa un campo, reglas de negocio, ejemplos).
3. **El catálogo tiene prioridad sobre nombres técnicos.** Si un fragmento de documentación
   contradice la metadata real (p. ej. describe una columna con un tipo o nombre que ya no existe),
   el catálogo gana y el desacuerdo debe señalarse al usuario final, no resolverse en silencio a
   favor del documento.

## Configuración

```yaml
rag:
  enabled: false
  documents_path: /app/documents
  allowed_extensions: [".md", ".txt", ".sql", ".json", ".yaml", ".yml"]
  chunk_size: 1000
  chunk_overlap: 150
  max_document_bytes: 5000000
  refresh_interval_minutes: 60
  refresh_on_startup: true
  max_search_results: 20
  embedding_provider:
    type: openai_compatible
    base_url: http://llm-gateway:8080/v1
    api_key_env: EMBEDDING_API_KEY
    model: text-embedding-3-small
    dimensions: 1536
    timeout_seconds: 30
    batch_size: 64
  vector_store:
    url: http://qdrant:6333
    collection_name: documents
    timeout_seconds: 10
```

`embedding_provider` es **independiente** de `generation.provider` de Sprint 5: el modelo de
embeddings puede ser distinto (vendor, dimensión, incluso local en el futuro) del modelo de chat
usado para generar SQL. `rag.enabled=true` sin `embedding_provider` declarado falla la validación
de configuración al arrancar.

## Vector store (Qdrant)

El nombre real de la colección se deriva de `sha256(tipo:modelo:dimensiones)` del proveedor de
embeddings configurado, no del `collection_name` literal en crudo — cambiar de modelo o dimensión
de embeddings crea automáticamente una colección nueva y aislada; **nunca mezcla vectores
incompatibles** en el mismo índice. La colección anterior queda huérfana y su limpieza es una
tarea administrativa manual fuera del alcance del servidor MCP.

Si `rag.enabled=true` y Qdrant no responde al arrancar, el proceso falla el arranque completo
(mismo criterio fail-fast que ya usa `ConnectionService.validate_startup()` para PostgreSQL). Con
`rag.enabled=false`, ninguna dependencia de RAG se toca y el proceso arranca igual que sin este
sprint.

## Auditoría y privacidad

`AuditOperation.INDEX_DOCUMENT` y `SEARCH_DOCUMENTS` reutilizan el esquema SQLite de auditoría ya
existente, sin migraciones. Nunca se persiste el contenido de un documento ni el texto de una
búsqueda — solo hash SHA-256 del contenido (para idempotencia y correlación) y de la pregunta de
búsqueda.

## Límites conocidos

- El barrido completo relee y hashea cada archivo en cada ciclo del scheduler; el hash evita
  recalcular embeddings de archivos sin cambios, pero no evita el I/O de disco.
- Chunking por caracteres, no por tokens del modelo de embeddings — una limitación explícita a
  revisar si el proveedor exige control fino de tokens.
- `delete_indexed_document` no es una exclusión permanente: si el archivo sigue en el volumen de
  documentos, el próximo refresh (manual o programado) lo reindexa de nuevo.
