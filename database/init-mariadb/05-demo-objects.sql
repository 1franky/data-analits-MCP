-- mcp_readonly is declared DEFINER so it can see its own routine/trigger bodies via
-- SHOW CREATE: unlike PostgreSQL, MariaDB hides routine/trigger definitions from any
-- role that is neither the DEFINER nor holds broader administrative privileges, even
-- when EXECUTE was granted explicitly.
DELIMITER $$

CREATE DEFINER = 'mcp_readonly'@'%' TRIGGER trg_ventas_actualiza_stock
    AFTER INSERT ON ventas
    FOR EACH ROW
BEGIN
    UPDATE productos
    SET stock = stock - NEW.cantidad
    WHERE id = NEW.producto_id;
END $$

CREATE DEFINER = 'mcp_readonly'@'%' PROCEDURE resumen_ventas_cliente(IN p_cliente_id INT)
    COMMENT 'Calcula el número de ventas y el monto total gastado por un cliente.'
BEGIN
    SELECT
        COUNT(*) AS total_ventas,
        COALESCE(SUM(productos.precio * ventas.cantidad), 0) AS monto_total
    FROM ventas
    INNER JOIN productos ON productos.id = ventas.producto_id
    WHERE ventas.cliente_id = p_cliente_id;
END $$

DELIMITER ;

GRANT EXECUTE ON PROCEDURE demo.resumen_ventas_cliente TO 'mcp_readonly'@'%';

-- MariaDB hides trigger metadata (information_schema.TRIGGERS, SHOW CREATE TRIGGER) from
-- any role without the TRIGGER privilege, even the trigger's own DEFINER. That privilege
-- also grants CREATE/DROP TRIGGER at the database level -- a real trade-off, accepted here
-- only because this is an explicitly local-only demo lab (see docs/connections.md for the
-- production guidance: grant TRIGGER only if trigger introspection is required, and treat
-- it as a schema-write-capable credential, not a plain readonly one).
GRANT TRIGGER ON demo.* TO 'mcp_readonly'@'%';

FLUSH PRIVILEGES;
