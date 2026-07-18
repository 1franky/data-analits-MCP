-- Extiende el esquema demo original (clientes/productos/ventas) con tablas adicionales
-- para ejercitar catálogo, relaciones y objetos más ricos en el laboratorio.
-- No se modifica la estructura de clientes/ventas: solo se agregan columnas nullable
-- nuevas a productos y tablas nuevas relacionadas por FK.

CREATE TABLE categorias (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL UNIQUE,
    descripcion VARCHAR(255)
);

CREATE TABLE proveedores (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL,
    contacto VARCHAR(120),
    telefono VARCHAR(30)
);

ALTER TABLE productos
    ADD COLUMN categoria_id INTEGER REFERENCES categorias(id),
    ADD COLUMN proveedor_id INTEGER REFERENCES proveedores(id);

CREATE TABLE direcciones_envio (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    calle VARCHAR(150) NOT NULL,
    ciudad VARCHAR(80) NOT NULL,
    codigo_postal VARCHAR(15) NOT NULL,
    es_principal BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE resenas_productos (
    id SERIAL PRIMARY KEY,
    producto_id INTEGER NOT NULL REFERENCES productos(id),
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    calificacion SMALLINT NOT NULL CHECK (calificacion BETWEEN 1 AND 5),
    comentario VARCHAR(500),
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE empleados (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    puesto VARCHAR(80) NOT NULL,
    fecha_contratacion DATE NOT NULL,
    salario NUMERIC(10,2) NOT NULL
);

CREATE TABLE historial_salarios (
    id SERIAL PRIMARY KEY,
    empleado_id INTEGER NOT NULL REFERENCES empleados(id),
    salario_anterior NUMERIC(10,2) NOT NULL,
    salario_nuevo NUMERIC(10,2) NOT NULL,
    fecha_cambio TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE categorias IS 'Categorías del catálogo de productos.';
COMMENT ON TABLE proveedores IS 'Proveedores que abastecen el catálogo de productos.';
COMMENT ON COLUMN productos.categoria_id IS 'Categoría a la que pertenece el producto.';
COMMENT ON COLUMN productos.proveedor_id IS 'Proveedor que abastece el producto.';
COMMENT ON TABLE direcciones_envio IS 'Direcciones de envío registradas por cliente.';
COMMENT ON COLUMN direcciones_envio.es_principal IS
    'Indica si es la dirección de envío principal del cliente.';
COMMENT ON TABLE resenas_productos IS
    'Reseñas y calificaciones de clientes sobre productos comprados.';
COMMENT ON TABLE empleados IS 'Empleados de la plataforma comercial.';
COMMENT ON TABLE historial_salarios IS
    'Historial de cambios de salario, poblado automáticamente por trigger.';

INSERT INTO categorias (nombre, descripcion) VALUES
('Cómputo', 'Equipos de cómputo y componentes'),
('Accesorios', 'Periféricos y accesorios'),
('Oficina', 'Artículos para oficina');

INSERT INTO proveedores (nombre, contacto, telefono) VALUES
('TechDistribuidora S.A.', 'ventas@techdistribuidora.example', '+52-55-1000-2000'),
('Accesorios Global', 'contacto@accesoriosglobal.example', '+52-55-2000-3000'),
('Oficina Total', 'pedidos@oficinatotal.example', '+52-55-3000-4000');

UPDATE productos SET
    categoria_id = (SELECT id FROM categorias WHERE nombre = 'Cómputo'),
    proveedor_id = (SELECT id FROM proveedores WHERE nombre = 'TechDistribuidora S.A.')
WHERE nombre = 'Laptop';

UPDATE productos SET
    categoria_id = (SELECT id FROM categorias WHERE nombre = 'Accesorios'),
    proveedor_id = (SELECT id FROM proveedores WHERE nombre = 'Accesorios Global')
WHERE nombre = 'Mouse';

UPDATE productos SET
    categoria_id = (SELECT id FROM categorias WHERE nombre = 'Accesorios'),
    proveedor_id = (SELECT id FROM proveedores WHERE nombre = 'Accesorios Global')
WHERE nombre = 'Teclado';

UPDATE productos SET
    categoria_id = (SELECT id FROM categorias WHERE nombre = 'Cómputo'),
    proveedor_id = (SELECT id FROM proveedores WHERE nombre = 'TechDistribuidora S.A.')
WHERE nombre = 'Monitor';

INSERT INTO direcciones_envio (cliente_id, calle, ciudad, codigo_postal, es_principal) VALUES
((SELECT id FROM clientes WHERE correo = 'juan@example.com'),
 'Av. Reforma 123', 'Ciudad de México', '06600', true),
((SELECT id FROM clientes WHERE correo = 'ana@example.com'),
 'Calle Hidalgo 45', 'Guadalajara', '44100', true),
((SELECT id FROM clientes WHERE correo = 'ana@example.com'),
 'Blvd. del Sol 900', 'Zapopan', '45010', false),
((SELECT id FROM clientes WHERE correo = 'carlos@example.com'),
 'Av. Constitución 500', 'Monterrey', '64000', true);

INSERT INTO resenas_productos (producto_id, cliente_id, calificacion, comentario) VALUES
((SELECT id FROM productos WHERE nombre = 'Laptop'),
 (SELECT id FROM clientes WHERE correo = 'juan@example.com'), 5, 'Excelente rendimiento.'),
((SELECT id FROM productos WHERE nombre = 'Mouse'),
 (SELECT id FROM clientes WHERE correo = 'juan@example.com'), 4, 'Buena precisión, cómodo.'),
((SELECT id FROM productos WHERE nombre = 'Monitor'),
 (SELECT id FROM clientes WHERE correo = 'ana@example.com'), 5, 'Colores muy nítidos.'),
((SELECT id FROM productos WHERE nombre = 'Teclado'),
 (SELECT id FROM clientes WHERE correo = 'carlos@example.com'), 3, 'Cumple, teclas un poco duras.'),
((SELECT id FROM productos WHERE nombre = 'Mouse'),
 (SELECT id FROM clientes WHERE correo = 'ana@example.com'), 4, 'Buena relación calidad-precio.');

INSERT INTO empleados (nombre, puesto, fecha_contratacion, salario) VALUES
('Marta Sánchez', 'Gerente de Ventas', '2023-03-01', 32000),
('Luis Torres', 'Ejecutivo de Ventas', '2024-06-15', 18000),
('Sofía Ramírez', 'Soporte al Cliente', '2024-11-01', 15000),
('Diego Fernández', 'Analista de Inventario', '2025-02-10', 17000);
