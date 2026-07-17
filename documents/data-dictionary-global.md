# Diccionario de datos global

Este documento describe convenciones aplicables a cualquier conexión configurada en
Data Platform MCP, independientemente de la base de datos concreta.

## Convenciones generales

- Las columnas `id` son siempre claves primarias autoincrementales (`SERIAL`/`IDENTITY`).
- Las columnas de fecha/hora se almacenan siempre en UTC.
- Los correos electrónicos se validan como únicos por tabla cuando la columna se llama `correo`
  o `email`.
- Ningún adaptador ejecuta escritura: toda consulta generada o manual pasa por validación de
  solo lectura antes de ejecutarse.

## Cómo usar este documento

Este documento es global (no tiene `connection=` ni `domain=` en su ruta), por lo que aparece en
cualquier búsqueda de `search_documents`, se pida o no una conexión específica.
