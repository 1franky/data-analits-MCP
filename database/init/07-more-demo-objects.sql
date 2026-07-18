-- Procedimientos/funciones y triggers adicionales sobre el esquema demo extendido
-- (database/init/06-more-demo-data.sql), con la misma garantía de solo lectura del
-- rol mcp_readonly que 05-demo-objects.sql: EXECUTE se otorga explícitamente porque
-- las default privileges de 03-readonly-user.sql solo cubren tablas, no funciones.

CREATE OR REPLACE FUNCTION producto_mas_vendido()
RETURNS TABLE(producto_id integer, nombre varchar, total_vendido bigint)
LANGUAGE sql
STABLE
AS $$
    SELECT productos.id, productos.nombre, SUM(ventas.cantidad)::bigint AS total_vendido
    FROM ventas
    INNER JOIN productos ON productos.id = ventas.producto_id
    GROUP BY productos.id, productos.nombre
    ORDER BY total_vendido DESC
    LIMIT 1;
$$;

COMMENT ON FUNCTION producto_mas_vendido() IS
    'Devuelve el producto con mayor cantidad total vendida.';

CREATE OR REPLACE FUNCTION calificacion_promedio_producto(p_producto_id integer)
RETURNS numeric
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(AVG(calificacion), 0)::numeric
    FROM resenas_productos
    WHERE producto_id = p_producto_id;
$$;

COMMENT ON FUNCTION calificacion_promedio_producto(integer) IS
    'Calcula la calificación promedio de un producto a partir de sus reseñas.';

CREATE OR REPLACE FUNCTION clientes_por_ciudad(p_ciudad varchar)
RETURNS TABLE(cliente_id integer, nombre varchar)
LANGUAGE sql
STABLE
AS $$
    SELECT DISTINCT clientes.id, clientes.nombre
    FROM clientes
    INNER JOIN direcciones_envio ON direcciones_envio.cliente_id = clientes.id
    WHERE direcciones_envio.ciudad = p_ciudad;
$$;

COMMENT ON FUNCTION clientes_por_ciudad(varchar) IS
    'Lista los clientes con una dirección de envío registrada en una ciudad dada.';

-- Trigger BEFORE INSERT: complementa (timing distinto) al AFTER INSERT ya existente
-- (trg_ventas_actualiza_stock), rechazando la venta si no hay stock suficiente.
CREATE OR REPLACE FUNCTION valida_stock_venta()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF (SELECT stock FROM productos WHERE id = NEW.producto_id) < NEW.cantidad THEN
        RAISE EXCEPTION 'Stock insuficiente para el producto %', NEW.producto_id;
    END IF;
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION valida_stock_venta() IS
    'Rechaza una venta si no hay stock suficiente del producto antes de insertarla.';

CREATE TRIGGER trg_ventas_valida_stock
    BEFORE INSERT ON ventas
    FOR EACH ROW
    EXECUTE FUNCTION valida_stock_venta();

-- Trigger AFTER UPDATE: evento distinto (UPDATE en vez de INSERT), con condición WHEN
-- implícita en el cuerpo, sobre una tabla nueva (empleados) en vez de ventas.
CREATE OR REPLACE FUNCTION registrar_historial_salario()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.salario IS DISTINCT FROM OLD.salario THEN
        INSERT INTO historial_salarios (empleado_id, salario_anterior, salario_nuevo)
        VALUES (NEW.id, OLD.salario, NEW.salario);
    END IF;
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION registrar_historial_salario() IS
    'Registra en historial_salarios cada cambio real de salario de un empleado.';

CREATE TRIGGER trg_empleados_historial_salario
    AFTER UPDATE ON empleados
    FOR EACH ROW
    EXECUTE FUNCTION registrar_historial_salario();

GRANT EXECUTE ON FUNCTION producto_mas_vendido() TO mcp_readonly;
GRANT EXECUTE ON FUNCTION calificacion_promedio_producto(integer) TO mcp_readonly;
GRANT EXECUTE ON FUNCTION clientes_por_ciudad(varchar) TO mcp_readonly;
GRANT EXECUTE ON FUNCTION valida_stock_venta() TO mcp_readonly;
GRANT EXECUTE ON FUNCTION registrar_historial_salario() TO mcp_readonly;

-- Dispara una vez el trigger de historial durante la inicialización, para que
-- historial_salarios no quede vacío en un laboratorio recién creado.
UPDATE empleados SET salario = salario + 1000 WHERE nombre = 'Luis Torres';
