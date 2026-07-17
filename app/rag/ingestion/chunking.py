"""Deterministic character-based text chunking with configurable overlap."""

from typing import NamedTuple


class TextChunk(NamedTuple):
    """One contiguous slice of text with its exact character offsets."""

    text: str
    char_start: int
    char_end: int


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> tuple[TextChunk, ...]:
    """Split text into overlapping windows of at most chunk_size characters."""
    if not text:
        return ()
    stride = chunk_size - chunk_overlap
    length = len(text)
    chunks: list[TextChunk] = []
    start = 0
    while start < length:
        end = min(start + chunk_size, length)
        chunks.append(TextChunk(text=text[start:end], char_start=start, char_end=end))
        if end == length:
            break
        start += stride
    return tuple(chunks)
