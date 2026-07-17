"""Integration tests against the disposable Docker MongoDB laboratory."""

import os
from typing import cast

import pytest
from pydantic import JsonValue, SecretStr
from pymongo import MongoClient
from pymongo.errors import OperationFailure

from app.adapters.mongodb import MongoDbAdapter
from tests.factories import make_connection_config

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_MONGODB_INTEGRATION") != "1",
        reason="set RUN_MONGODB_INTEGRATION=1 with the MongoDB lab running",
    ),
]


def build_adapter() -> MongoDbAdapter:
    """Create the adapter using only the lab secret supplied by the environment."""
    password = os.environ["MONGO_DEMO_PASSWORD"]
    config = make_connection_config(
        id="mongodb-demo",
        name="MongoDB Demo",
        type="mongodb",
        host="mongo-lab",
        port=27017,
        database="demo",
        username="mcp_readonly",
        password_env="MONGO_DEMO_PASSWORD",
        options={"authSource": "demo"},
    )
    return MongoDbAdapter(config, SecretStr(password))


def test_mongodb_connection_and_collections() -> None:
    adapter = build_adapter()

    connection_result = adapter.test_connection()
    collections = adapter.list_collections()

    assert connection_result.success is True
    assert connection_result.error_code is None
    assert {c.name for c in collections} == {"clientes", "productos", "ventas"}


def test_mongodb_execute_find_returns_real_documents() -> None:
    adapter = build_adapter()

    result = adapter.execute_find(
        "clientes",
        {"_id": 1},
        None,
        max_rows=10,
        timeout_seconds=10,
        max_serialized_bytes=1_000_000,
    )

    assert len(result.documents) == 1
    document = cast("dict[str, JsonValue]", result.documents[0])
    assert document["nombre"] == "Juan Pérez"


def test_mongodb_execute_aggregation_runs_lookup_and_group() -> None:
    adapter = build_adapter()

    pipeline: list[dict[str, JsonValue]] = [
        {"$match": {"cliente_id": 1}},
        {
            "$lookup": {
                "from": "productos",
                "localField": "producto_id",
                "foreignField": "_id",
                "as": "producto",
            }
        },
        {"$unwind": "$producto"},
        {
            "$group": {
                "_id": "$cliente_id",
                "total": {"$sum": {"$multiply": ["$cantidad", "$producto.precio"]}},
            }
        },
    ]

    result = adapter.execute_aggregation(
        "ventas",
        pipeline,
        max_rows=10,
        timeout_seconds=10,
        max_serialized_bytes=1_000_000,
    )

    assert len(result.documents) == 1
    document = cast("dict[str, JsonValue]", result.documents[0])
    assert document["_id"] == 1


def test_mongodb_lab_role_cannot_write() -> None:
    password = os.environ["MONGO_DEMO_PASSWORD"]
    client: MongoClient[dict[str, object]] = MongoClient(
        host="mongo-lab",
        port=27017,
        username="mcp_readonly",
        password=password,
        authSource="demo",
        serverSelectionTimeoutMS=10_000,
    )
    try:
        with pytest.raises(OperationFailure) as error_info:
            client["demo"]["productos"].insert_one({"nombre": "blocked", "precio": 1, "stock": 1})
        assert error_info.value.code == 13  # Unauthorized
    finally:
        client.close()
