"""Contract implemented by document database adapters.

Deliberately excludes any write method (insert/update/delete). Read-only is a
structural guarantee here, not a runtime check: an implementation cannot expose
what this interface never declares.
"""

from abc import ABC, abstractmethod

from pydantic import JsonValue

from app.models.connections import CollectionInfo, ConnectionCapabilities, ConnectionTestResult
from app.models.document_query import AdapterDocumentResult


class DocumentDatabaseAdapter(ABC):
    """Document metadata and strictly read-only query contract."""

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
    def list_collections(self) -> tuple[CollectionInfo, ...]:
        """List visible, non-system collections."""
        raise NotImplementedError

    @abstractmethod
    def execute_find(
        self,
        collection: str,
        filter: dict[str, JsonValue],
        projection: dict[str, JsonValue] | None,
        max_rows: int,
        timeout_seconds: int,
        max_serialized_bytes: int,
    ) -> AdapterDocumentResult:
        """Execute a prevalidated find() under database-level safety controls."""
        raise NotImplementedError

    @abstractmethod
    def execute_aggregation(
        self,
        collection: str,
        pipeline: list[dict[str, JsonValue]],
        max_rows: int,
        timeout_seconds: int,
        max_serialized_bytes: int,
    ) -> AdapterDocumentResult:
        """Execute a prevalidated aggregation pipeline under safety controls."""
        raise NotImplementedError
