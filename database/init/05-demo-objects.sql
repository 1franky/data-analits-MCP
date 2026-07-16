CREATE OR REPLACE FUNCTION actualizar_stock_producto()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE productos
    SET stock = stock - NEW.cantidad
    WHERE id = NEW.producto_id;
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION actualizar_stock_producto() IS
    'Descuenta del stock del producto la cantidad vendida en cada nueva venta.';

CREATE TRIGGER trg_ventas_actualiza_stock
    AFTER INSERT ON ventas
    FOR EACH ROW
    EXECUTE FUNCTION actualizar_stock_producto();

CREATE OR REPLACE FUNCTION resumen_ventas_cliente(p_cliente_id integer)
RETURNS TABLE(total_ventas bigint, monto_total numeric)
LANGUAGE sql
STABLE
AS $$
    SELECT
        COUNT(*)::bigint,
        COALESCE(SUM(productos.precio * ventas.cantidad), 0)::numeric
    FROM ventas
    INNER JOIN productos ON productos.id = ventas.producto_id
    WHERE ventas.cliente_id = p_cliente_id;
$$;

COMMENT ON FUNCTION resumen_ventas_cliente(integer) IS
    'Calcula el número de ventas y el monto total gastado por un cliente.';

GRANT EXECUTE ON FUNCTION actualizar_stock_producto() TO mcp_readonly;
GRANT EXECUTE ON FUNCTION resumen_ventas_cliente(integer) TO mcp_readonly;
