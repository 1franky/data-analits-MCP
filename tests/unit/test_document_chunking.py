"""Tests for deterministic character-based text chunking."""

from app.rag.ingestion.chunking import TextChunk, chunk_markdown_by_structure, chunk_text


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


def _assert_offsets_reproduce_text(text: str, chunks: tuple[TextChunk, ...]) -> None:
    for chunk in chunks:
        assert text[chunk.char_start : chunk.char_end] == chunk.text


def test_markdown_empty_text_produces_no_chunks() -> None:
    assert chunk_markdown_by_structure("", chunk_size=100, chunk_overlap=10) == ()


def test_markdown_unstructured_text_smaller_than_chunk_size_produces_one_chunk() -> None:
    text = "a single unstructured line with no headings, code fences or blank lines"
    chunks = chunk_markdown_by_structure(text, chunk_size=1000, chunk_overlap=100)

    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].char_start == 0
    assert chunks[0].char_end == len(text)
    _assert_offsets_reproduce_text(text, chunks)


def test_markdown_headings_produce_section_aligned_chunks() -> None:
    text = (
        "# Título\n"
        "Introducción breve.\n"
        "\n"
        "## Sección uno\n"
        "Contenido de la primera sección.\n"
        "\n"
        "## Sección dos\n"
        "Contenido de la segunda sección.\n"
    )
    chunks = chunk_markdown_by_structure(text, chunk_size=60, chunk_overlap=0)

    assert len(chunks) > 1
    _assert_offsets_reproduce_text(text, chunks)
    # Every "## Sección ..." heading starts its own chunk, instead of appearing
    # mid-chunk glued to the end of the previous section's content.
    heading_chunks = [chunk for chunk in chunks if "## Sección" in chunk.text]
    assert heading_chunks
    for chunk in heading_chunks:
        assert chunk.text.lstrip().startswith("## Sección")


def test_markdown_large_fenced_code_block_is_never_split_when_it_fits() -> None:
    code_block = "```python\n" + "\n".join(f"line_{i} = {i}" for i in range(5)) + "\n```\n"
    text = f"# Título\n\nTexto antes.\n\n{code_block}\nTexto después.\n"
    chunks = chunk_markdown_by_structure(text, chunk_size=1000, chunk_overlap=0)

    _assert_offsets_reproduce_text(text, chunks)
    fence_count = sum(chunk.text.count("```") for chunk in chunks)
    assert any(chunk.text.count("```") == 2 for chunk in chunks)
    assert fence_count >= 2


def test_markdown_oversized_fence_falls_back_to_sliding_window_within_size_limit() -> None:
    long_code = "\n".join(f"x_{i} = {i}" for i in range(200))
    code_block = f"```python\n{long_code}\n```\n"
    text = f"# Título\n\n{code_block}"
    chunk_size = 100
    chunks = chunk_markdown_by_structure(text, chunk_size=chunk_size, chunk_overlap=0)

    _assert_offsets_reproduce_text(text, chunks)
    for chunk in chunks:
        assert len(chunk.text) <= chunk_size
    assert chunks[-1].char_end == len(text)
    assert chunks[0].char_start == 0


def test_markdown_offsets_always_reproduce_original_text() -> None:
    text = (
        "# Encabezado\n"
        "Párrafo uno con algo de contenido.\n"
        "\n"
        "Párrafo dos, distinto del primero.\n"
        "\n"
        "```sql\nSELECT 1;\n```\n"
        "\n"
        "Cierre final del documento.\n"
    )
    chunks = chunk_markdown_by_structure(text, chunk_size=40, chunk_overlap=10)
    _assert_offsets_reproduce_text(text, chunks)
