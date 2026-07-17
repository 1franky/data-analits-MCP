// Demo collections mirroring the relational lab (clientes/productos/ventas), with simple
// integer _id values so ventas.cliente_id/producto_id read like foreign keys and $lookup
// examples stay obvious.
db.createCollection("clientes");
db.createCollection("productos");
db.createCollection("ventas");

db.clientes.insertMany([
  { _id: 1, nombre: "Juan Pérez", correo: "juan@example.com", fecha_registro: "2025-01-10" },
  { _id: 2, nombre: "Ana López", correo: "ana@example.com", fecha_registro: "2025-02-15" },
  { _id: 3, nombre: "Carlos Ruiz", correo: "carlos@example.com", fecha_registro: "2025-03-20" },
]);

db.productos.insertMany([
  { _id: 1, nombre: "Laptop", precio: 15000, stock: 20 },
  { _id: 2, nombre: "Mouse", precio: 350, stock: 100 },
  { _id: 3, nombre: "Teclado", precio: 900, stock: 50 },
  { _id: 4, nombre: "Monitor", precio: 4200, stock: 15 },
]);

db.ventas.insertMany([
  { _id: 1, cliente_id: 1, producto_id: 1, cantidad: 1 },
  { _id: 2, cliente_id: 1, producto_id: 2, cantidad: 2 },
  { _id: 3, cliente_id: 2, producto_id: 4, cantidad: 1 },
  { _id: 4, cliente_id: 3, producto_id: 3, cantidad: 1 },
  { _id: 5, cliente_id: 2, producto_id: 2, cantidad: 3 },
]);
