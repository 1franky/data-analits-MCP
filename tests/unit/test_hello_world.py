"""Tests for the bootstrap MCP tool."""

import pytest
from fastmcp import Client

from app.tools.hello import hello_world
from app.tools.server import mcp
from tests.unit.test_mcp_contracts import EXPECTED_TOOLS


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Ada", {"message": "Hello, Ada!"}),
        ("  MCP  ", {"message": "Hello, MCP!"}),
        ("", {"message": "Hello, world!"}),
    ],
)
def test_hello_world_builds_a_deterministic_greeting(
    name: str,
    expected: dict[str, str],
) -> None:
    assert hello_world(name) == expected


async def test_hello_world_is_registered_and_callable_over_mcp() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
        result = await client.call_tool("hello_world", {"name": "Open WebUI"})

    assert {tool.name for tool in tools} == EXPECTED_TOOLS
    assert result.data == {"message": "Hello, Open WebUI!"}
