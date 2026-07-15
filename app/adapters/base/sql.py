"""Contract implemented by relational database adapters."""

from abc import ABC, abstractmethod

from app.models.connections import (
    ConnectionCapabilities,
    ConnectionTestResult,
    SchemaInfo,
    TableDescription,
    TableInfo,
)
from app.models.query import AdapterQueryPlan, AdapterQueryResult, QueryParameter


class SqlDatabaseAdapter(ABC):
    """Relational metadata and strictly read-only query contract."""

    @property
    @abstractmethod
    def capabilities(self) -> ConnectionCapabilities:
        """Describe supported operations."""
        raise NotImplementedError

    @abstractmethod
    def test_connection(self) -> ConnectionTestResult:
        """Test connectivity using a bounded read-only operation."""
        raise NotImplementedError

    @abstractmethod
    def list_schemas(self) -> tuple[SchemaInfo, ...]:
        """List visible non-system schemas."""
        raise NotImplementedError

    @abstractmethod
    def list_tables(self, schema: str | None = None) -> tuple[TableInfo, ...]:
        """List visible tables, optionally restricted to one schema."""
        raise NotImplementedError

    @abstractmethod
    def describe_table(self, schema: str, table: str) -> TableDescription:
        """Return columns and key metadata for a visible table."""
        raise NotImplementedError

    @abstractmethod
    def execute_read_query(
        self,
        sql: str,
        parameters: dict[str, QueryParameter] | None,
        max_rows: int,
        timeout_seconds: int,
        max_serialized_bytes: int,
    ) -> AdapterQueryResult:
        """Execute a prevalidated SELECT under database-level safety controls."""
        raise NotImplementedError

    @abstractmethod
    def explain_read_query(
        self,
        sql: str,
        parameters: dict[str, QueryParameter] | None,
        timeout_seconds: int,
    ) -> AdapterQueryPlan:
        """Plan a prevalidated SELECT without ANALYZE."""
        raise NotImplementedError
