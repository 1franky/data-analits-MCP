"""Common adapter contracts."""

from app.adapters.base.document import DocumentDatabaseAdapter
from app.adapters.base.sql import SqlDatabaseAdapter

__all__ = ["DocumentDatabaseAdapter", "SqlDatabaseAdapter"]
