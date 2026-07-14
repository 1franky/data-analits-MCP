"""Contract implemented by relational database adapters."""

from abc import ABC, abstractmethod

from app.models.connections import (
    ConnectionCapabilities,
    ConnectionTestResult,
    SchemaInfo,
    TableDescription,
    TableInfo,
)


class SqlDatabaseAdapter(ABC):
    """Minimum SQL metadata contract delivered in Sprint 1."""

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
