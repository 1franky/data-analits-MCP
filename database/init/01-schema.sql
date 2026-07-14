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

COMMENT ON TABLE clientes IS 'Clientes registrados en la plataforma comercial.';
COMMENT ON COLUMN clientes.correo IS 'Correo electrónico único del cliente.';
COMMENT ON TABLE productos IS 'Productos disponibles para venta e inventario.';
COMMENT ON COLUMN productos.stock IS 'Unidades actualmente disponibles.';
COMMENT ON TABLE ventas IS 'Ventas realizadas a clientes de productos del catálogo.';
COMMENT ON COLUMN ventas.cliente_id IS 'Cliente que realizó la compra.';
COMMENT ON COLUMN ventas.producto_id IS 'Producto incluido en la venta.';
