from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from src.config import settings
from src.db.connection import get_connection
from src.db.repository import ChunkRepository, PaperRepository
from src.db.schema import init_db
from src.models.paper import Chunk, PaperMetadata
from src.services.bm25_index import Bm25Index
from src.services.search import bm25_search, hybrid_search, vector_search
from src.services.vector_index import VectorIndex


class FakeEmbedder:
    """Deterministic 2D embedder: encodes word overlap with fixed anchor terms."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)

    @staticmethod
    def _embed_one(text: str) -> list[float]:
        lowered = text.lower()
        return [
            1.0 if "robotics" in lowered else 0.0,
            1.0 if "molecules" in lowered else 0.0,
        ]


@pytest.fixture
def seeded_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[int, int]:
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(settings, "sqlite_db_path", db_path)
    init_db(db_path)

    with get_connection() as conn:
        papers = PaperRepository(conn)
        chunks = ChunkRepository(conn)

        paper = papers.upsert_metadata(
            PaperMetadata(
                arxiv_id="1111.11111",
                title="Robotics Paper",
                authors=["A"],
                abstract="about robotics",
                categories=["cs.RO"],
                published_date="2021-01-01",
                pdf_url="http://example.com/1.pdf",
            )
        )
        chunks.replace_chunks(paper.id, [("reinforcement learning for robotics", 0, 10)])
        robotics_chunk_id = chunks.get_by_paper(paper.id)[0].id

        paper2 = papers.upsert_metadata(
            PaperMetadata(
                arxiv_id="2222.22222",
                title="Molecules Paper",
                authors=["B"],
                abstract="about molecules",
                categories=["cs.LG"],
                published_date="2021-01-01",
                pdf_url="http://example.com/2.pdf",
            )
        )
        chunks.replace_chunks(paper2.id, [("graph neural networks for molecules", 0, 10)])
        molecules_chunk_id = chunks.get_by_paper(paper2.id)[0].id

        # A third, unrelated paper. With only 2 docs, a term appearing in
        # exactly 1 of them gets IDF == 0 (log((2-1+0.5)/(1+0.5)) == 0),
        # which zeroes out its BM25 score entirely and hides a real match.
        # A third doc avoids that degenerate small-corpus case.
        paper3 = papers.upsert_metadata(
            PaperMetadata(
                arxiv_id="3333.33333",
                title="Distractor Paper",
                authors=["C"],
                abstract="about databases",
                categories=["cs.DB"],
                published_date="2021-01-01",
                pdf_url="http://example.com/3.pdf",
            )
        )
        chunks.replace_chunks(paper3.id, [("distributed database indexing", 0, 10)])

    assert robotics_chunk_id is not None
    assert molecules_chunk_id is not None
    return robotics_chunk_id, molecules_chunk_id


def _all_chunks() -> list[Chunk]:
    with get_connection() as conn:
        return ChunkRepository(conn).get_all()


def test_bm25_search_hydrates_results(seeded_db: tuple[int, int]) -> None:
    robotics_chunk_id, _ = seeded_db
    bm25_index = Bm25Index.build(_all_chunks())

    results = bm25_search(bm25_index, "robotics", top_k=5)

    assert results[0].chunk_id == robotics_chunk_id
    assert results[0].arxiv_id == "1111.11111"
    assert results[0].title == "Robotics Paper"


def test_vector_search_hydrates_results(seeded_db: tuple[int, int]) -> None:
    _, molecules_chunk_id = seeded_db
    chunks = _all_chunks()

    client = QdrantClient(location=":memory:")
    vector_index = VectorIndex(client=client)
    vector_index.ensure_collection(dim=2)
    embedder = FakeEmbedder()
    vector_index.upsert_chunks(chunks, embedder)

    results = vector_search(vector_index, embedder, "molecules research", top_k=5)

    assert results[0].chunk_id == molecules_chunk_id


def test_hybrid_search_fuses_both_methods(seeded_db: tuple[int, int]) -> None:
    robotics_chunk_id, _ = seeded_db
    chunks = _all_chunks()

    bm25_index = Bm25Index.build(chunks)
    client = QdrantClient(location=":memory:")
    vector_index = VectorIndex(client=client)
    vector_index.ensure_collection(dim=2)
    embedder = FakeEmbedder()
    vector_index.upsert_chunks(chunks, embedder)

    results = hybrid_search(bm25_index, vector_index, embedder, "robotics", top_k=5)

    assert results[0].chunk_id == robotics_chunk_id
