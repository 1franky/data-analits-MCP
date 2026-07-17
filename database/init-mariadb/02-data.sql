INSERT INTO clientes (nombre, correo, fecha_registro) VALUES
('Juan Pérez','juan@example.com','2025-01-10'),
('Ana López','ana@example.com','2025-02-15'),
('Carlos Ruiz','carlos@example.com','2025-03-20');

INSERT INTO productos (nombre, precio, stock) VALUES
('Laptop',15000,20),
('Mouse',350,100),
('Teclado',900,50),
('Monitor',4200,15);

INSERT INTO ventas (cliente_id, producto_id, cantidad) VALUES
(1,1,1),
(1,2,2),
(2,4,1),
(3,3,1),
(2,2,3);
