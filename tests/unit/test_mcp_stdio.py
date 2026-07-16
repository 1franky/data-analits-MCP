"""Smoke contract for the local MCP STDIO transport."""

import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def test_stdio_transport_lists_and_calls_tools() -> None:
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "app.tools.server"],
        cwd=str(Path.cwd()),
    )

    async with Client(transport) as client:
        tools = await client.list_tools()
        health = await client.call_tool("health_check", {})

    assert "list_schemas" in {tool.name for tool in tools}
    assert health.data.contract_version == "1.0.0"
    assert health.data.server_version == "0.7.0"
