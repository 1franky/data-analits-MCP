"""Deterministic character-based text chunking with configurable overlap."""

import re
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


_FENCE_LINE = re.compile(r"^\s*```")
_HEADING_LINE = re.compile(r"^#{1,6}\s")


def _find_fence_spans(text: str) -> list[tuple[int, int]]:
    """Return non-overlapping (start, end) spans, one per fenced code block.

    An unclosed fence extends to the end of the text, so it is never split.
    """
    spans: list[tuple[int, int]] = []
    length = len(text)
    pos = 0
    while pos < length:
        line_end = text.find("\n", pos)
        line_end = length if line_end == -1 else line_end + 1
        line = text[pos:line_end]
        if _FENCE_LINE.match(line):
            fence_start = pos
            search_pos = line_end
            closed_at: int | None = None
            while search_pos < length:
                next_line_end = text.find("\n", search_pos)
                next_line_end = length if next_line_end == -1 else next_line_end + 1
                if _FENCE_LINE.match(text[search_pos:next_line_end]):
                    closed_at = next_line_end
                    break
                search_pos = next_line_end
            fence_end = length if closed_at is None else closed_at
            spans.append((fence_start, fence_end))
            pos = fence_end
            continue
        pos = line_end
    return spans


def _natural_block_boundaries(text: str, fence_spans: list[tuple[int, int]]) -> list[int]:
    """Return sorted cut points for headings/blank lines that never fall inside a fence."""
    length = len(text)
    cuts = {0, length}
    for fence_start, fence_end in fence_spans:
        cuts.add(fence_start)
        cuts.add(fence_end)

    def _inside_fence(offset: int) -> bool:
        return any(start < offset < end for start, end in fence_spans)

    pos = 0
    while pos < length:
        line_end = text.find("\n", pos)
        line_end = length if line_end == -1 else line_end + 1
        if not _inside_fence(pos):
            stripped = text[pos:line_end].strip()
            if stripped == "":
                cuts.add(line_end)
            elif pos != 0 and _HEADING_LINE.match(stripped):
                cuts.add(pos)
        pos = line_end
    return sorted(cuts)


def chunk_markdown_by_structure(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> tuple[TextChunk, ...]:
    """Split Markdown into chunks that prefer heading/paragraph/fence boundaries.

    Never splits a fenced code block across two chunks unless the fence alone
    exceeds chunk_size, in which case that block falls back to the same
    sliding-window logic as chunk_text() to preserve the maximum-size invariant.
    """
    if not text:
        return ()

    fence_spans = _find_fence_spans(text)
    boundaries = _natural_block_boundaries(text, fence_spans)
    natural_blocks = [
        (boundaries[index], boundaries[index + 1]) for index in range(len(boundaries) - 1)
    ]

    raw_spans: list[tuple[int, int]] = []
    current_start: int | None = None
    current_end: int | None = None
    for block_start, block_end in natural_blocks:
        if block_end - block_start > chunk_size:
            if current_start is not None:
                raw_spans.append((current_start, current_end))  # type: ignore[arg-type]
                current_start = None
            for sub_chunk in chunk_text(text[block_start:block_end], chunk_size, 0):
                raw_spans.append(
                    (block_start + sub_chunk.char_start, block_start + sub_chunk.char_end)
                )
            continue
        if current_start is None:
            current_start, current_end = block_start, block_end
        elif block_end - current_start <= chunk_size:
            current_end = block_end
        else:
            raw_spans.append((current_start, current_end))  # type: ignore[arg-type]
            current_start, current_end = block_start, block_end
    if current_start is not None:
        raw_spans.append((current_start, current_end))  # type: ignore[arg-type]

    def _clamp_overlap_start(naive_start: int) -> int:
        for fence_start, fence_end in fence_spans:
            if fence_start < naive_start < fence_end:
                return fence_end
        return naive_start

    chunks: list[TextChunk] = []
    for index, (span_start, span_end) in enumerate(raw_spans):
        effective_start = span_start
        if index > 0 and chunk_overlap > 0:
            effective_start = _clamp_overlap_start(max(0, span_start - chunk_overlap))
        chunks.append(
            TextChunk(
                text=text[effective_start:span_end],
                char_start=effective_start,
                char_end=span_end,
            )
        )
    return tuple(chunks)
