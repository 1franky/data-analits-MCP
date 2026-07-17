"""Registry-based document parser construction without format conditionals."""

from collections.abc import Callable
from dataclasses import dataclass

from app.exceptions import UnsupportedDocumentFormatError
from app.rag.ingestion.parsers.base import DocumentParser

DocumentParserBuilder = Callable[[], DocumentParser]


@dataclass(frozen=True, slots=True)
class DocumentParserRegistration:
    """Builder registered for one document file extension."""

    builder: DocumentParserBuilder


class DocumentParserFactory:
    """Create document parsers through an explicit extension registry."""

    def __init__(self) -> None:
        self._registrations: dict[str, DocumentParserRegistration] = {}

    def register(self, extension: str, builder: DocumentParserBuilder) -> None:
        """Register or replace the parser builder for one extension."""
        self._registrations[extension.lower()] = DocumentParserRegistration(builder)

    def supports(self, extension: str) -> bool:
        """Return whether a parser is registered for an extension."""
        return extension.lower() in self._registrations

    def create(self, extension: str) -> DocumentParser:
        """Construct the registered parser for a requested extension."""
        registration = self._registrations.get(extension.lower())
        if registration is None:
            raise UnsupportedDocumentFormatError(extension)
        return registration.builder()
