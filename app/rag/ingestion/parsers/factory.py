"""Default document parser registrations available in the running application."""

from app.rag.ingestion.parsers.registry import DocumentParserFactory
from app.rag.ingestion.parsers.text_parser import TextDocumentParser


def create_document_parser_factory() -> DocumentParserFactory:
    """Create an isolated registry with all implemented document parsers."""
    factory = DocumentParserFactory()
    for extension in TextDocumentParser.extensions:
        factory.register(extension=extension, builder=TextDocumentParser)
    return factory
