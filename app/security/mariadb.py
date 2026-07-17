"""Strict MariaDB/MySQL AST policy used after SQLGlot parsing."""


class MariaDbSqlPolicy:
    """Identify functions unsafe for a generic read-only query surface."""

    _BLOCKED_FUNCTIONS = frozenset(
        {
            "load_file",
            "sleep",
            "benchmark",
            "get_lock",
            "release_lock",
            "release_all_locks",
            "is_free_lock",
            "is_used_lock",
            "master_pos_wait",
            "source_pos_wait",
            "uuid_short",
        }
    )

    @classmethod
    def function_is_blocked(cls, name: str) -> bool:
        """Return whether a normalized function name is explicitly denied."""
        normalized = name.rsplit(".", maxsplit=1)[-1].casefold()
        return normalized in cls._BLOCKED_FUNCTIONS
