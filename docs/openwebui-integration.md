# Integración con Open WebUI

Sprint 8 conecta Data Platform MCP a Open WebUI como cliente MCP. El servidor no cambia: ya expone
sus 25 tools por Streamable HTTP en `/mcp` desde Sprint 4. Open WebUI soporta MCP nativo por
Streamable HTTP desde la versión `v0.6.31` — no hace falta ningún proxy ni bridge intermedio.

Coherente con el principio del proyecto de no acoplar su código al contenedor de Open WebUI, este
repo no despliega Open WebUI como parte de `compose.yaml`. `examples/openwebui/` contiene un
compose aislado, solo para validar la integración localmente; en un despliegue real Open WebUI vive
en su propio proyecto y solo necesita compartir la red `ai-platform`.

## 1. Prerrequisitos

- `data-platform-mcp` corriendo y healthy (`docker compose up -d` en la raíz del repo).
- La red externa `ai-platform` ya existe (`docker network create ai-platform` si es la primera vez).
- Ninguna conexión con datos reales sensibles apuntada desde el laboratorio de prueba: usa
  `postgres-demo` u otra conexión de bajo riesgo mientras validas el flujo.

## 2. Levantar Open WebUI de ejemplo

```bash
cp examples/openwebui/.env.example examples/openwebui/.env
# Edita WEBUI_SECRET_KEY en examples/openwebui/.env (openssl rand -hex 32) antes de continuar.
docker compose -f examples/openwebui/compose.yaml --env-file examples/openwebui/.env up -d
```

Espera a que el contenedor quede `healthy` (`docker compose -f examples/openwebui/compose.yaml ps`)
y abre `http://127.0.0.1:3000`. La primera cuenta que registres se convierte en administradora.

## 3. Conectar el servidor MCP

1. Entra como administrador → **⚙️ Admin Settings → External Tools**.
2. Pulsa **+ (Add Server)**.
3. **Type**: `MCP (Streamable HTTP)`.
4. **Server URL**: `http://data-platform-mcp:8000/mcp` (nombre de servicio Docker, resuelto dentro
   de `ai-platform` — nunca uses `127.0.0.1` aquí, Open WebUI corre en su propio contenedor).
5. **Auth**: `None`. El servidor MCP no implementa autenticación propia hoy; `ai-platform` es la
   frontera de confianza (ver [seguridad](security.md) para el detalle de esta limitación conocida).
6. Guarda y confirma que aparecen las 25 tools (`hello_world`, `list_connections`,
   `search_catalog`, `execute_read_query`, `generate_sql`, `list_procedures`, `search_documents`,
   etc.). Si la lista está vacía, revisa la sección de [Troubleshooting](#troubleshooting).

## 4. Consultar PostgreSQL desde el chat (HU-802)

Con el tool server añadido y un modelo con tool-calling habilitado en la conversación, prueba un
prompt como:

```text
Usando la conexión postgres-demo, muéstrame el total vendido por producto, ordenado de mayor a menor.
```

Resultado esperado, observable en la conversación:

1. El modelo llama a `list_schemas`/`search_catalog`/`describe_table` para entender el esquema real
   (tablas `ventas`, `productos`, relación `producto_id`).
2. El modelo llama a `generate_sql` o construye el SQL él mismo y lo pasa a `validate_sql`/
   `execute_read_query` (`generate_and_execute_query` también es válido si el modelo lo prefiere).
3. La respuesta incluye el SQL ejecutado y una tabla de resultados con montos coherentes con los
   datos del laboratorio (`database/init/02-data.sql`).
4. El SQL nunca contiene escritura: es una consulta `SELECT` con `JOIN`/`GROUP BY`.

Si el modelo no invoca ninguna tool, confirma que el modelo elegido en Open WebUI soporta
tool-calling (no todos los modelos lo hacen) y que el tool server sigue habilitado en esa
conversación (icono de herramientas en la barra de entrada del chat).

## 5. Generar DML sin ejecutarlo (HU-803)

Prueba un prompt como:

```text
Usando la conexión postgres-demo, borra todas las filas de la tabla ventas.
```

Resultado esperado:

1. El modelo genera o recibe un `DELETE FROM ventas` y lo pasa a `validate_sql` o
   `execute_read_query`.
2. La respuesta de la tool muestra el SQL normalizado con `executable: false`, la razón de bloqueo
   estructurada (`DML_NOT_ALLOWED`/`READ_ONLY_STATEMENT_REQUIRED`) y una advertencia de impacto —
   nunca un resultado de filas afectadas, porque el adaptador nunca se invoca para ese SQL.
3. El modelo debe comunicar al usuario que la sentencia fue generada pero no ejecutada.

Verificación posterior de que los datos no cambiaron (fuera del chat, para no depender de que el
modelo lo haga bien):

```text
Pide en el chat: "cuántas filas tiene la tabla ventas en postgres-demo"
```

o directamente por MCP:

```bash
uv run python -c "
import asyncio
from fastmcp import Client

async def main():
    async with Client('http://127.0.0.1:8000/mcp') as client:
        result = await client.call_tool('execute_read_query', {
            'connection_id': 'postgres-demo',
            'sql': 'SELECT COUNT(*) AS total FROM ventas',
        })
        print(result.data)

asyncio.run(main())
"
```

El conteo debe coincidir con el que tenía antes del prompt de HU-803 (`database/init/02-data.sql`
carga un número fijo de filas de ejemplo).

## 6. Prueba de conectividad automatizada (HU-801)

Con `data-platform-mcp` y el Open WebUI de ejemplo corriendo en `ai-platform`:

```bash
python scripts/smoke_openwebui.py
```

Confirma que Open WebUI resuelve y alcanza `data-platform-mcp:8000` por nombre de servicio, sin
necesitar un modelo real ni tocar el chat — cubre el criterio "Open WebUI puede alcanzar el
servidor MCP por nombre de servicio" de forma reproducible en CI/validación local.

## Troubleshooting

| Síntoma | Causa habitual | Acción |
|---|---|---|
| Las tools no aparecen tras guardar el servidor | URL mal escrita, o `data-platform-mcp` no está `healthy` | Verifica `docker compose ps` en la raíz del repo; confirma que la URL termina en `/mcp` |
| `Connection refused` o timeout al guardar el servidor | Open WebUI y `data-platform-mcp` no comparten red | Confirma `AI_PLATFORM_NETWORK` igual en ambos `.env`; revisa `docker network inspect ai-platform` |
| La sesión de Open WebUI se cierra sola tras reiniciar el contenedor | `WEBUI_SECRET_KEY` no fijado o cambiado entre reinicios | Fija un valor único en `examples/openwebui/.env` y no lo cambies entre reinicios |
| El modelo nunca llama a ninguna tool | El modelo elegido no soporta tool-calling, o el tool server está deshabilitado en esa conversación | Cambia de modelo o habilita el icono de herramientas en la conversación |
| El modelo "alucina" resultados en vez de llamar a `execute_read_query` | El modelo es débil generando/decidiendo cuándo usar tools | Prueba con un modelo distinto; pide explícitamente "usa las herramientas MCP disponibles" |

## Alcance de esta guía

HU-801 se valida de forma 100% automatizada con `scripts/smoke_openwebui.py`, sin depender de un
proveedor LLM real. HU-802 y HU-803 dependen de que **tú** configures un modelo real con
tool-calling dentro de Open WebUI (OpenAI, Claude, Ollama u otro proveedor compatible) — el
servidor MCP en sí sigue sin depender de ningún proveedor concreto, igual que el resto del
proyecto. Esta guía documenta el runbook exacto; su ejecución y confirmación quedan a tu cargo.
