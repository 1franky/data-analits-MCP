# Contratos MCP y compatibilidad

## Versiones

Data Platform MCP distingue dos versiones:

- servidor `0.6.0`: versión de la aplicación, imagen y servidor FastMCP;
- contrato `1.0.0`: versión semántica de los envelopes MCP introducidos en Sprint 4.

`contract_version` aparece en la raíz de `health_check`, `get_connection_capabilities`,
`list_schemas`, `list_tables`, `describe_table` y `list_relationships`. Los tools existentes de los
sprints anteriores conservan su forma para no introducir una ruptura artificial; su JSON Schema
publicado por `list_tools` y las pruebas de contrato protegen esa forma.

## Política de compatibilidad

Los clientes deben ignorar campos desconocidos y validar el major de `contract_version` antes de
consumir una respuesta versionada.

- Patch: correcciones de documentación o comportamiento que no cambian el schema.
- Minor: campos opcionales, nuevos valores expresamente extensibles o tools nuevos.
- Major: quitar/renombrar campos o tools, volver obligatorio un input antes opcional, cambiar tipos,
  aliases, significado o unidades, o eliminar un valor permitido.

Todo cambio incompatible debe:

1. incrementar el major de `contract_version`;
2. registrarse como `BREAKING` en `CHANGELOG.md` con guía de migración;
3. actualizar ejemplos, schemas esperados y pruebas de contrato;
4. mantener una ventana de compatibilidad o publicarse en un endpoint/servidor separado cuando un
   consumidor no pueda migrar de manera atómica.

No existe un cambio incompatible en `1.0.0` porque es la primera versión explícita del contrato.

## Envelope común

Toda respuesta versionada tiene esta propiedad raíz:

```json
{
  "contract_version": "1.0.0"
}
```

Las respuestas de metadata añaden siempre `connection_id` y `cache_status`. El estado permite al
cliente distinguir un snapshot fresco de uno obsoleto. La exploración requiere un snapshot válido;
si no existe, el error explica que debe llamarse `refresh_schema_cache`.

## Contratos versionados

| Tool | Entrada | Salida raíz |
|---|---|---|
| `health_check` | ninguna | `contract_version`, `status`, `service`, `server_version` |
| `get_connection_capabilities` | `connection_id` | `contract_version`, `connection_id`, `connection` |
| `list_schemas` | `connection_id` | `contract_version`, `connection_id`, `schemas`, `cache_status` |
| `list_tables` | `connection_id`, `schema?` | `contract_version`, `connection_id`, `schema_filter`, `tables`, `cache_status` |
| `describe_table` | `connection_id`, `schema`, `table` | `contract_version`, `connection_id`, `table`, `cache_status` |
| `list_relationships` | `connection_id`, `schema?`, `table?` | `contract_version`, `connection_id`, filtros, `relationships`, `cache_status` |

FastMCP genera `inputSchema` y `outputSchema` desde las anotaciones Pydantic. Los tests consultan el
catálogo a través de un cliente MCP, no duplican un schema escrito manualmente.

## Cardinalidad

Cada relación representa una FK orientada desde la tabla que contiene las columnas FK hacia la
tabla referenciada:

```json
{
  "source_schema": "public",
  "source_table": "ventas",
  "source_columns": ["cliente_id"],
  "target_schema": "public",
  "target_table": "clientes",
  "target_columns": ["id"],
  "cardinality": "many-to-one",
  "cardinality_inference": "source_not_unique"
}
```

Valores actuales:

- `one-to-one` + `source_primary_key`: las columnas FK son la PK completa de origen;
- `one-to-one` + `source_unique_key`: las columnas FK forman un índice único simple y completo;
- `many-to-one` + `source_not_unique`: no existe unicidad declarada sobre las columnas origen.

No se leen filas para inferir cardinalidad. Índices parciales, de expresión, inválidos o columnas
`INCLUDE` no se consideran evidencia de unicidad.

## Transportes

El registro y los contratos son idénticos en ambos transportes:

- red: Streamable HTTP en `http://<servicio>:8000/mcp`;
- local: STDIO mediante `data-platform-mcp-stdio` o `python -m app.tools.server`.

La prueba de contrato STDIO arranca un subproceso real. El smoke test de red está en
`scripts/smoke_mcp.py` y llama el servicio desplegado, refresca metadata y recorre los tools de
exploración.
