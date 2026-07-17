-- Consultas de referencia sobre el esquema demo (connection=postgres-demo).
-- Documentadas para RAG: sirven como ejemplos de composicion, no se ejecutan automaticamente.

-- Total vendido por cliente (cantidad * precio de cada linea de venta, sumado).
SELECT
    c.nombre,
    SUM(v.cantidad * p.precio) AS total_vendido
FROM ventas AS v
JOIN clientes AS c ON c.id = v.cliente_id
JOIN productos AS p ON p.id = v.producto_id
GROUP BY c.nombre
ORDER BY total_vendido DESC;

-- Productos con stock por debajo de la cantidad total vendida historicamente,
-- utilizada para detectar posibles inconsistencias de inventario.
SELECT
    p.nombre,
    p.stock,
    SUM(v.cantidad) AS unidades_vendidas
FROM productos AS p
JOIN ventas AS v ON v.producto_id = p.id
GROUP BY p.nombre, p.stock
HAVING p.stock < SUM(v.cantidad);

-- Clientes registrados en los ultimos 30 dias respecto a una fecha de referencia.
SELECT id, nombre, correo, fecha_registro
FROM clientes
WHERE fecha_registro >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY fecha_registro DESC;
