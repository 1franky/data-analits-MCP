# Ejemplo: Open WebUI + Data Platform MCP

Este directorio **no forma parte del despliegue de producción de Data Platform MCP**. Es un
ejemplo aislado para validar localmente la integración de Sprint 8 (HU-801 a HU-803), siguiendo el
principio del proyecto de no acoplar su código al contenedor de Open WebUI: en un despliegue real,
Open WebUI vive en su propio proyecto Compose y solo necesita compartir la red `ai-platform`.

Guía completa de uso: [`docs/openwebui-integration.md`](../../docs/openwebui-integration.md).

## Uso rápido

```bash
# 1. Con data-platform-mcp ya corriendo (docker compose up -d en la raíz del repo):
cp examples/openwebui/.env.example examples/openwebui/.env
# Edita WEBUI_SECRET_KEY antes de continuar (openssl rand -hex 32).

# 2. Levanta Open WebUI unido a la misma red ai-platform:
docker compose -f examples/openwebui/compose.yaml --env-file examples/openwebui/.env up -d

# 3. Abre http://127.0.0.1:3000 y sigue la guía de integración para añadir el servidor MCP.
```

Para detener solo este ejemplo sin afectar al servidor MCP:

```bash
docker compose -f examples/openwebui/compose.yaml down
```
