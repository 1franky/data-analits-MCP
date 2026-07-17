"""Unit tests for the MariaDB dangerous-function denylist."""

import pytest

from app.security import MariaDbSqlPolicy


@pytest.mark.parametrize(
    "name",
    [
        "load_file",
        "LOAD_FILE",
        "Sleep",
        "benchmark",
        "get_lock",
        "release_lock",
        "release_all_locks",
        "is_free_lock",
        "is_used_lock",
        "master_pos_wait",
        "source_pos_wait",
        "uuid_short",
        "schema.load_file",
    ],
)
def test_known_dangerous_functions_are_blocked(name: str) -> None:
    assert MariaDbSqlPolicy.function_is_blocked(name) is True


@pytest.mark.parametrize("name", ["count", "sum", "now", "concat", "coalesce"])
def test_ordinary_functions_are_not_blocked(name: str) -> None:
    assert MariaDbSqlPolicy.function_is_blocked(name) is False
