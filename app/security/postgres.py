"""Strict PostgreSQL AST policy used after SQLGlot parsing."""


class PostgresSqlPolicy:
    """Identify functions unsafe for a generic read-only query surface."""

    _BLOCKED_FUNCTIONS = frozenset(
        {
            "dblink",
            "dblink_exec",
            "lo_export",
            "lo_import",
            "lowrite",
            "nextval",
            "pg_cancel_backend",
            "pg_log_backend_memory_contexts",
            "pg_logical_emit_message",
            "pg_ls_dir",
            "pg_notify",
            "pg_promote",
            "pg_read_binary_file",
            "pg_read_file",
            "pg_reload_conf",
            "pg_rotate_logfile",
            "pg_stat_file",
            "pg_switch_wal",
            "pg_sleep",
            "pg_terminate_backend",
            "set_config",
            "setval",
        }
    )
    _BLOCKED_PREFIXES = (
        "dblink_",
        "lo_",
        "pg_advisory_",
        "pg_backup_",
        "pg_cancel_",
        "pg_create_",
        "pg_copy_",
        "pg_drop_",
        "pg_log_",
        "pg_ls_",
        "pg_reload_",
        "pg_replication_origin_",
        "pg_replication_slot_",
        "pg_rotate_",
        "pg_switch_",
        "pg_sync_",
        "pg_terminate_",
        "pg_try_advisory_",
        "pg_wal_replay_",
    )

    @classmethod
    def function_is_blocked(cls, name: str) -> bool:
        """Return whether a normalized function name is explicitly denied."""
        normalized = name.rsplit(".", maxsplit=1)[-1].casefold()
        return normalized in cls._BLOCKED_FUNCTIONS or normalized.startswith(cls._BLOCKED_PREFIXES)
