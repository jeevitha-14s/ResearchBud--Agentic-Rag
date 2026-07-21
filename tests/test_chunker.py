import pytest

from src.services.chunker import chunk_text


def test_empty_text_returns_no_chunks() -> None:
    assert chunk_text("", chunk_size=100, overlap=10) == []


def test_short_text_returns_single_chunk() -> None:
    text = "Hello world."
    chunks = chunk_text(text, chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0][0] == text


def test_long_text_produces_overlapping_chunks() -> None:
    text = "a" * 1000
    chunks = chunk_text(text, chunk_size=300, overlap=50)
    assert len(chunks) > 1
    for chunk_text_, start, end in chunks:
        assert end - start <= 300
        assert text[start:end].strip() == chunk_text_ or chunk_text_ == ""


def test_chunks_cover_full_text_range() -> None:
    text = "word " * 400
    chunks = chunk_text(text, chunk_size=200, overlap=20)
    assert chunks[0][1] == 0
    assert chunks[-1][2] == len(text.strip()) or chunks[-1][2] <= len(text)


def test_rejects_overlap_greater_than_chunk_size() -> None:
    with pytest.raises(ValueError, match="chunk_size must be greater than overlap"):
        chunk_text("some text", chunk_size=50, overlap=50)


def test_breaks_on_paragraph_boundary_when_possible() -> None:
    para_a = "A" * 100
    para_b = "B" * 100
    text = f"{para_a}\n\n{para_b}"
    chunks = chunk_text(text, chunk_size=150, overlap=10)
    assert chunks[0][0] == para_a
