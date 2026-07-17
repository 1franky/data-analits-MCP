# Reglas de negocio: ventas (postgres-demo)

Documentación funcional del dominio de ventas del laboratorio `postgres-demo`, que complementa
(sin reemplazar) la metadata técnica real expuesta por `describe_table`/`list_relationships`.

## Reglas

- Una fila de `ventas` representa una única línea de venta: un `cliente_id`, un `producto_id`,
  una `cantidad` y una `fecha`.
- `ventas.cantidad` no debería exceder el `productos.stock` disponible en el momento de la venta.
  Esta regla es de negocio, no se aplica como restricción SQL en el esquema del laboratorio.
- `clientes.correo` es único: dos clientes nunca comparten el mismo correo electrónico.
- El monto de una venta se calcula como `ventas.cantidad * productos.precio`; no existe una
  columna `monto` almacenada en `ventas`.

## Notas

Si un documento de negocio entra en conflicto con la metadata técnica real (por ejemplo, un tipo
de columna descrito aquí no coincide con el catálogo), la metadata del catálogo tiene prioridad
— ver `docs/rag.md` para el patrón de combinación recomendado (HU-703).
