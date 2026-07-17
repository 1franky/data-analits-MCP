"""FastMCP server and tool registry."""

from fastmcp import FastMCP

from app import __version__
from app.tools.administration import health_check
from app.tools.catalog import (
    get_schema_cache_status,
    refresh_schema_cache,
    search_catalog,
)
from app.tools.connections import (
    get_connection_capabilities,
    list_connections,
    test_connection,
)
from app.tools.explanation import explain_database_object
from app.tools.generation import generate_and_execute_query, generate_sql
from app.tools.hello import hello_world
from app.tools.metadata import (
    describe_table,
    list_procedures,
    list_relationships,
    list_schemas,
    list_tables,
    list_triggers,
)
from app.tools.query import execute_read_query, explain_query, validate_sql
from app.tools.rag import (
    delete_indexed_document,
    list_indexed_documents,
    refresh_document_index,
    search_documents,
)
from app.tools.reporting import generate_report

mcp = FastMCP(
    name="Data Platform MCP",
    version=__version__,
    strict_input_validation=True,
    instructions=(
        "Herramientas seguras para explorar plataformas de datos. "
        "Sprint 4 expone contratos versionados para conexiones, schemas, tablas, "
        "relaciones y consultas SELECT seguras. Sprint 5 añade generación de SQL asistida "
        "por LLM sobre el catálogo real, siempre revalidada antes de ejecutar. "
        "Añade también generación de reportes XLSX/PDF/CSV/JSON entregados en línea. "
        "Sprint 6 añade procedimientos y triggers cacheados de solo lectura. "
        "Sprint 7 añade indexación y búsqueda semántica de documentación funcional (RAG), "
        "complementaria al catálogo técnico, nunca un sustituto de este. "
        "DML y DDL nunca se ejecutan."
    ),
)
mcp.tool(name="hello_world")(hello_world)
mcp.tool(name="health_check")(health_check)
mcp.tool(name="list_connections")(list_connections)
mcp.tool(name="get_connection_capabilities")(get_connection_capabilities)
mcp.tool(name="test_connection")(test_connection)
mcp.tool(name="refresh_schema_cache")(refresh_schema_cache)
mcp.tool(name="get_schema_cache_status")(get_schema_cache_status)
mcp.tool(name="search_catalog")(search_catalog)
mcp.tool(name="list_schemas")(list_schemas)
mcp.tool(name="list_tables")(list_tables)
mcp.tool(name="describe_table")(describe_table)
mcp.tool(name="list_relationships")(list_relationships)
mcp.tool(name="validate_sql")(validate_sql)
mcp.tool(name="execute_read_query")(execute_read_query)
mcp.tool(name="explain_query")(explain_query)
mcp.tool(name="generate_sql")(generate_sql)
mcp.tool(name="generate_and_execute_query")(generate_and_execute_query)
mcp.tool(name="generate_report")(generate_report)
mcp.tool(name="list_procedures")(list_procedures)
mcp.tool(name="list_triggers")(list_triggers)
mcp.tool(name="explain_database_object")(explain_database_object)
mcp.tool(name="search_documents")(search_documents)
mcp.tool(name="list_indexed_documents")(list_indexed_documents)
mcp.tool(name="refresh_document_index")(refresh_document_index)
mcp.tool(name="delete_indexed_document")(delete_indexed_document)


def main() -> None:
    """Run the same server over the local STDIO transport."""
    mcp.run()


if __name__ == "__main__":
    main()
