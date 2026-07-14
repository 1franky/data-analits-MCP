# Seguridad

## Alcance y amenazas de Sprint 1

Los activos principales son credenciales de base de datos, metadata técnica y disponibilidad del
servicio. Las amenazas relevantes son exposición de secretos, abuso de una conexión privilegiada,
inyección en consultas de metadata, escritura accidental y exposición del MCP fuera de la red de
confianza.

## Capas implementadas

1. YAML sin contraseñas; secretos resueltos desde variables de entorno.
2. Modelos públicos que excluyen host, usuario, `password_env` y secretos.
3. Errores de base normalizados sin texto crudo del driver.
4. Conexiones habilitadas obligatoriamente declaradas readonly.
5. Rol PostgreSQL dedicado con `SELECT`, sin escritura/DDL y transacciones readonly por defecto.
6. Sesión del adaptador marcada readonly además de los permisos del rol.
7. SQL de metadata controlado por la aplicación y parámetros para valores variables.
8. Timeouts de conexión validados y aplicados.
9. Contenedor MCP no-root, raíz readonly, sin capabilities y `no-new-privileges`.
10. Publicación de puertos en loopback por defecto.

## Operaciones permitidas

- Health check del proceso.
- Listar declaraciones y capacidades no sensibles.
- Probar conectividad con `SELECT 1`.
- Desde el adaptador interno: leer catálogos para schemas, tablas, columnas, PK y FK.

## Operaciones no disponibles

- Ejecutar SQL proporcionado por usuarios o LLM.
- INSERT, UPDATE, DELETE, DDL o llamadas a procedimientos.
- Leer filas de negocio mediante herramientas MCP.
- RAG, catálogo persistente o generación SQL.

No existe un endpoint oculto ni una función de confirmación que habilite escritura.

## Responsabilidades del administrador

- Sustituir los marcadores de `.env.example` y proteger el archivo `.env`.
- Usar roles readonly creados fuera del MCP, nunca administradores.
- Configurar TLS para bases remotas.
- Restringir membresía de `ai-platform` y no publicar MCP/PostgreSQL a Internet.
- Rotar secretos y reiniciar el servicio de forma controlada.
- Mantener imágenes/dependencias actualizadas después de ejecutar toda la suite.

## Limitaciones conocidas

Sprint 1 no incorpora autenticación/autorización MCP, rate limiting, auditoría, logs estructurados,
readiness de dependencias ni gestión nativa de secretos. La red Docker compartida es la frontera de
confianza provisional. Estas limitaciones impiden considerar el servicio listo para exposición
pública.
