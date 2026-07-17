"""Plain-text parser covering the initial Sprint 7 document formats."""

from typing import ClassVar

from app.exceptions import RagRequestError
from app.rag.ingestion.parsers.base import DocumentParser


class TextDocumentParser(DocumentParser):
    """Decode Markdown, plain text, SQL, JSON and YAML sources as UTF-8 text."""

    extensions: ClassVar[tuple[str, ...]] = (".md", ".txt", ".sql", ".json", ".yaml", ".yml")

    def parse(self, raw_bytes: bytes) -> str:
        """Decode raw bytes as UTF-8, rejecting content that cannot be decoded."""
        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            raise RagRequestError(
                code="DOCUMENT_ENCODING_ERROR",
                message="El documento no se pudo decodificar como UTF-8.",
            ) from error
