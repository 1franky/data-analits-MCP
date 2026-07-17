CREATE TABLE clientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    correo VARCHAR(150) NOT NULL UNIQUE COMMENT 'Correo electrónico único del cliente.',
    fecha_registro DATE NOT NULL
) COMMENT = 'Clientes registrados en la plataforma comercial.';

CREATE TABLE productos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    precio NUMERIC(10,2) NOT NULL,
    stock INT NOT NULL COMMENT 'Unidades actualmente disponibles.'
) COMMENT = 'Productos disponibles para venta e inventario.';

CREATE TABLE ventas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT NOT NULL COMMENT 'Cliente que realizó la compra.',
    producto_id INT NOT NULL COMMENT 'Producto incluido en la venta.',
    cantidad INT NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ventas_cliente FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    CONSTRAINT fk_ventas_producto FOREIGN KEY (producto_id) REFERENCES productos(id)
) COMMENT = 'Ventas realizadas a clientes de productos del catálogo.';
