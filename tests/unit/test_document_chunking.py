"""Tests for deterministic character-based text chunking."""

from app.rag.ingestion.chunking import chunk_text


def test_empty_text_produces_no_chunks() -> None:
    assert chunk_text("", chunk_size=100, chunk_overlap=10) == ()


def test_text_smaller_than_chunk_size_produces_one_chunk() -> None:
    chunks = chunk_text("hello world", chunk_size=100, chunk_overlap=10)
    assert len(chunks) == 1
    assert chunks[0].text == "hello world"
    assert chunks[0].char_start == 0
    assert chunks[0].char_end == 11


def test_overlap_produces_overlapping_windows() -> None:
    text = "0123456789"
    chunks = chunk_text(text, chunk_size=4, chunk_overlap=2)

    assert [chunk.char_start for chunk in chunks] == [0, 2, 4, 6]
    assert [chunk.char_end for chunk in chunks] == [4, 6, 8, 10]
    assert [chunk.text for chunk in chunks] == ["0123", "2345", "4567", "6789"]


def test_zero_overlap_produces_contiguous_chunks() -> None:
    chunks = chunk_text("abcdefgh", chunk_size=3, chunk_overlap=0)
    assert [chunk.text for chunk in chunks] == ["abc", "def", "gh"]
