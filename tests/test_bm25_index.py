from pathlib import Path

from src.models.paper import Chunk
from src.services.bm25_index import Bm25Index, tokenize


def _chunks() -> list[Chunk]:
    return [
        Chunk(
            id=1,
            paper_id=1,
            chunk_index=0,
            text="reinforcement learning for robotics",
            char_start=0,
            char_end=10,
        ),
        Chunk(
            id=2,
            paper_id=1,
            chunk_index=1,
            text="transformer models for natural language",
            char_start=10,
            char_end=20,
        ),
        Chunk(
            id=3,
            paper_id=2,
            chunk_index=0,
            text="graph neural networks for molecules",
            char_start=0,
            char_end=10,
        ),
    ]


def test_tokenize_lowercases_and_strips_punctuation() -> None:
    assert tokenize("Hello, World! 123") == ["hello", "world", "123"]


def test_search_returns_most_relevant_chunk_first() -> None:
    index = Bm25Index.build(_chunks())
    results = index.search("transformer language models", top_k=3)
    assert results[0][0] == 2


def test_search_excludes_zero_score_chunks() -> None:
    index = Bm25Index.build(_chunks())
    results = index.search("robotics", top_k=3)
    assert all(chunk_id != 3 for chunk_id, _ in results)


def test_search_respects_top_k() -> None:
    index = Bm25Index.build(_chunks())
    results = index.search("for", top_k=1)
    assert len(results) <= 1


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    index = Bm25Index.build(_chunks())
    path = str(tmp_path / "bm25.pkl")
    index.save(path)

    loaded = Bm25Index.load(path)
    results = loaded.search("transformer language models", top_k=3)
    assert results[0][0] == 2


def test_build_on_empty_corpus_does_not_raise() -> None:
    index = Bm25Index.build([])
    assert index.search("anything", top_k=5) == []


def test_empty_index_save_and_load_roundtrip(tmp_path: Path) -> None:
    index = Bm25Index.build([])
    path = str(tmp_path / "empty.pkl")
    index.save(path)

    loaded = Bm25Index.load(path)
    assert loaded.search("anything", top_k=5) == []
