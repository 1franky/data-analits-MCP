"""Contract implemented by document content parsers."""

from abc import ABC, abstractmethod
from typing import ClassVar


class DocumentParser(ABC):
    """Decode raw document bytes into plain text for chunking."""

    extensions: ClassVar[tuple[str, ...]]

    @abstractmethod
    def parse(self, raw_bytes: bytes) -> str:
        """Decode raw bytes into text, raising a domain error on invalid encoding."""
        raise NotImplementedError
