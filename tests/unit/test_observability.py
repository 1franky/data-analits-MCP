"""Tests for JSON log formatting and per-request correlation."""

import asyncio
import json
import logging

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.observability.context import request_id_var
from app.observability.logging import JsonFormatter


def test_json_formatter_produces_valid_json_with_expected_fields() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="something happened",
        args=(),
        exc_info=None,
    )
    record.tool_name = "execute_read_query"
    token = request_id_var.set("abc-123")
    try:
        line = formatter.format(record)
    finally:
        request_id_var.reset(token)

    payload = json.loads(line)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["message"] == "something happened"
    assert payload["request_id"] == "abc-123"
    assert payload["tool_name"] == "execute_read_query"
    assert "timestamp" in payload


def test_json_formatter_defaults_request_id_when_outside_a_request() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="no request in flight",
        args=(),
        exc_info=None,
    )

    payload = json.loads(formatter.format(record))

    assert payload["request_id"] == "-"


async def test_request_id_header_present_and_unique_per_concurrent_request() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        responses = await asyncio.gather(client.get("/health"), client.get("/health"))

    request_ids = [response.headers["x-request-id"] for response in responses]
    assert len(set(request_ids)) == 2
    for request_id in request_ids:
        assert request_id != "-"
