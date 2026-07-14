# Changelog

Todos los cambios relevantes de este proyecto se documentan en este archivo. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa versionado semántico.

## [Unreleased]

### Added

- Bootstrap de la aplicación para Python 3.12.
- Aplicación ASGI combinada con FastAPI y FastMCP.
- Endpoint de liveness `GET /health`.
- Herramienta MCP `hello_world` sobre Streamable HTTP en `/mcp`.
- Pruebas unitarias del health check, lógica de saludo y registro/invocación MCP.
- Configuración de pytest, Ruff y mypy estricto.
- Imagen Docker multi-stage basada en `python:3.12.13-slim-bookworm` y usuario no-root.
- Compose endurecido y conectado a la red externa `ai-platform`.
- Documentación inicial, arquitectura, guía de desarrollo y plan completo de sprints.

### Security

- Publicación del puerto limitada a loopback por defecto.
- Filesystem de contenedor de solo lectura, capabilities eliminadas y `no-new-privileges`.
- Exclusión de `.env` y artefactos locales del contexto Git/Docker.

### Fixed

- El target Docker de pruebas conserva `tests/` en el contexto de build.
- La prueba HTTP usa transporte ASGI directo y no genera advertencias deprecatorias de TestClient.

### Not implemented

- Conexiones y laboratorio PostgreSQL (Sprint 1).
- Catálogo, RAG, generación, validación o ejecución SQL.
- Autenticación, auditoría y métricas operativas.
