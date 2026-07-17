"""Unit tests for MongoDB adapter construction, safe failures and serialization."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from bson import Binary, Decimal128, ObjectId
from pydantic import JsonValue, SecretStr

from app.adapters.mongodb import MongoDbAdapter
from app.exceptions import ConfigurationError
from app.models.connections import ConnectionConfig
from tests.factories import make_connection_config


def _mongo_config(**overrides: object) -> ConnectionConfig:
    values: dict[str, object] = {
        "id": "mongodb-demo",
        "name": "MongoDB Demo",
        "type": "mongodb",
        "host": "mongo-lab",
        "port": 27017,
        "database": "demo",
        "username": "mcp_readonly",
        "password_env": "MONGO_DEMO_PASSWORD",
        "options": {},
    }
    values.update(overrides)
    return make_connection_config(**values)


def test_mongodb_adapter_rejects_wrong_engine_type() -> None:
    config = _mongo_config(type="postgres", options={})

    try:
        MongoDbAdapter(config, SecretStr("unit-test-secret"))
    except ConfigurationError as error:
        assert error.code == "MONGODB_CONFIG_TYPE_ERROR"
    else:
        raise AssertionError("ConfigurationError was not raised")


def test_mongodb_adapter_rejects_unknown_driver_options() -> None:
    config = _mongo_config(options={"unsafe_option": "value"})

    try:
        MongoDbAdapter(config, SecretStr("unit-test-secret"))
    except ConfigurationError as error:
        assert error.code == "MONGODB_OPTIONS_ERROR"
        assert "unsafe_option" in error.message
    else:
        raise AssertionError("ConfigurationError was not raised")


def test_failed_connection_result_never_exposes_password() -> None:
    config = _mongo_config(host="127.0.0.1", port=1, connect_timeout_seconds=1)
    password = "secret-that-must-not-leak"

    result = MongoDbAdapter(config, SecretStr(password)).test_connection()

    assert result.success is False
    assert result.error_code == "DATABASE_CONNECTION_ERROR"
    assert password not in result.message
    assert password not in result.model_dump_json()


def test_to_json_safe_handles_bson_specific_types() -> None:
    object_id = ObjectId()
    payload = {
        "_id": object_id,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "amount": Decimal128(Decimal("19.99")),
        "raw": Binary(b"\x00\x01"),
        "nested": {"child": [1, 2, object_id]},
        "plain": "text",
        "flag": True,
        "empty": None,
    }

    safe = cast("dict[str, JsonValue]", MongoDbAdapter._to_json_safe(payload))

    assert safe["_id"] == str(object_id)
    assert safe["created_at"] == "2026-01-01T00:00:00+00:00"
    assert safe["amount"] == "19.99"
    assert safe["raw"] == "base64:AAE="
    assert safe["nested"] == {"child": [1, 2, str(object_id)]}
    assert safe["plain"] == "text"
    assert safe["flag"] is True
    assert safe["empty"] is None
