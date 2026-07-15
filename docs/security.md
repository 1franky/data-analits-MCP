# Seguridad

## Alcance y amenazas de Sprint 4

Los activos principales son credenciales, datos consultados, metadata, auditoría y disponibilidad.
Las amenazas cubiertas incluyen exposición de secretos, SQL de escritura, bypass mediante múltiples
sentencias o CTE, funciones con efectos secundarios, consultas costosas, respuestas excesivas,
inyección en parámetros y persistencia accidental de datos sensibles.

## Capas implementadas

1. YAML sin contraseñas; secretos resueltos desde variables de entorno.
2. Modelos públicos que excluyen host, usuario, `password_env` y secretos.
3. Errores de base normalizados sin texto crudo del driver.
4. Conexiones habilitadas obligatoriamente readonly.
5. Rol PostgreSQL dedicado con `SELECT`, sin escritura/DDL y readonly por defecto.
6. Cada sesión del adaptador se marca readonly y toda consulta termina con `ROLLBACK`.
7. SQLGlot parsea el dialecto PostgreSQL; la política opera sobre AST, no sobre regex.
8. Allowlist de una sentencia `SELECT`; bloqueo de DML, DDL, privilegios, `COPY`, comandos,
   múltiples sentencias, escritura en CTE, `SELECT INTO` y locking reads.
9. Denylist de funciones PostgreSQL con efectos o abuso conocidos, incluidas `pg_sleep`, secuencias,
   archivos, notificaciones, WAL/replicación, large objects, `dblink_*` y advisory locks.
10. Parámetros exclusivamente nombrados y coincidencia exacta de claves; Psycopg recibe valores
    separados del SQL.
11. Límites mínimos entre solicitud/conexión/política para timeout y filas; tope de bytes y semáforo
    de concurrencia por proceso.
12. `EXPLAIN` constante en formato JSON con `ANALYZE FALSE`.
13. Auditoría append-only con hash SHA-256, tipo, decisión, razones, duración y conteo; sin SQL,
    parámetros ni resultados.
14. Contenedor no-root, raíz readonly, sin capabilities, `no-new-privileges` y puertos en loopback.
15. Exploración MCP sobre snapshots de metadata, sin consultar filas ni resolver secretos durante
    `list_schemas`, `list_tables`, `describe_table` o `list_relationships`.

## Operaciones permitidas

- Health check, conexiones y metadata de sprints anteriores.
- Validar cualquier texto SQL para obtener clasificación y razones.
- Ejecutar un único `SELECT` PostgreSQL validado y acotado.
- Generar el plan JSON de ese `SELECT` sin `ANALYZE`.
- Actualizar y buscar el caché técnico persistente.
- Listar schemas, tablas y relaciones, y describir tablas desde el snapshot cacheado.

## Operaciones bloqueadas

- `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `CREATE`, `ALTER`, `DROP`, `TRUNCATE` y `COPY`.
- Escrituras ocultas dentro de CTE y múltiples sentencias.
- `SELECT INTO`, `FOR UPDATE`/locking reads, comandos administrativos y cambios de privilegios.
- Placeholders posicionales, parámetros faltantes o adicionales.
- `EXPLAIN` suministrado como SQL de usuario; solo se acepta el `SELECT` subyacente.
- Procedimientos, RAG, generación LLM y cualquier ruta de confirmación de escritura.

Una escritura válida sí puede devolverse normalizada por `validate_sql` para revisión manual, pero
queda marcada `executable: false`, incluye advertencia de impacto y nunca llega al método ejecutor
del adaptador. Las pruebas usan un adaptador espía y verifican además que las filas reales no cambian.

## Auditoría y privacidad

Cada validación, ejecución o explicación crea un evento cuando `audit.enabled` es verdadero. El hash
permite correlacionar la misma entrada sin conservarla. No es un mecanismo de anonimización para
entradas de baja entropía: quienes tengan acceso al archivo podrían probar hashes candidatos, por lo
que el volumen debe protegerse como dato operativo sensible.

`audit.db` comparte el volumen `/app/data` con el catálogo. La primera implementación es apta para
una sola réplica. Retención, exportación, consulta administrativa y firmas inmutables pertenecen al
hardening futuro; no existe aún una herramienta MCP para leer auditoría.

## Responsabilidades del administrador

- Sustituir los marcadores de `.env.example` y proteger `.env` y el volumen de datos.
- Usar roles readonly externos, nunca administradores; retirar `EXECUTE` sobre funciones no
  confiables y evitar funciones `SECURITY DEFINER` accesibles al rol MCP.
- Configurar TLS para bases remotas.
- Restringir membresía de `ai-platform` y no publicar MCP/PostgreSQL a Internet.
- Revisar la política al actualizar PostgreSQL/SQLGlot y ejecutar pruebas de ataques e integración.
- Dimensionar filas, bytes, timeout y concurrencia según memoria/CPU de Oracle Cloud Free Tier.

## Limitaciones conocidas

Un parser conoce la estructura de una llamada, no la implementación de cada función definida por el
usuario. La sesión readonly impide escrituras PostgreSQL ordinarias, pero una función autorizada puede
tener efectos externos; los privilegios de función son una frontera imprescindible. La denylist es
defensa adicional, no prueba formal de ausencia de efectos.

Sprint 4 no incorpora autenticación/autorización MCP, rate limiting distribuido, pool de conexiones,
logs estructurados, readiness, rotación/retención de auditoría ni gestión nativa de secretos. La red
Docker compartida sigue siendo una frontera de confianza provisional.
