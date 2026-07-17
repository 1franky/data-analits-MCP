"""MCP contract tests for document indexing and semantic search tools."""

from pathlib import Path

import pytest
from fastmcp import Client

import app.tools.rag as rag_tools
from app.tools.server import mcp
from tests.rag_fakes import build_document_index_service, build_document_search_service


async def test_rag_tools_are_callable_and_structured_over_mcp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents_root = tmp_path / "documents"
    documents_root.mkdir()
    (documents_root / "a.md").write_text("contenido de prueba", encoding="utf-8")

    index_service, _provider, vector_store, _audit_repository, _repository = (
        build_document_index_service(
            tmp_path / "documents.db", tmp_path / "audit.db", documents_root
        )
    )
    search_service, _search_provider, _search_vector_store, _search_audit = (
        build_document_search_service(tmp_path / "search-audit.db", vector_store=vector_store)
    )
    monkeypatch.setattr(rag_tools, "get_document_index_service", lambda: index_service)
    monkeypatch.setattr(rag_tools, "get_document_search_service", lambda: search_service)

    async with Client(mcp) as client:
        tools = {tool.name for tool in await client.list_tools()}
        refreshed = await client.call_tool("refresh_document_index", {})
        listed = await client.call_tool("list_indexed_documents", {})
        searched = await client.call_tool("search_documents", {"query": "contenido"})
        document_id = refreshed.data.entries[0].document_id
        deleted = await client.call_tool(
            "delete_indexed_document",
            {"document_id": document_id},
        )

    assert {
        "search_documents",
        "list_indexed_documents",
        "refresh_document_index",
        "delete_indexed_document",
    }.issubset(tools)
    assert refreshed.data.indexed_count == 1
    assert refreshed.data.contract_version == "1.0.0"
    assert listed.data.total == 1
    assert searched.data.contract_version == "1.0.0"
    assert deleted.data.deleted is True
