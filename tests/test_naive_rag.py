from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from src.agents.generate import GENERATE_SYSTEM_PROMPT, NO_CONTEXT_ANSWER
from src.config import settings
from src.db.connection import get_connection
from src.db.repository import ChunkRepository, PaperRepository
from src.db.schema import init_db
from src.models.paper import PaperMetadata
from src.services.bm25_index import Bm25Index
from src.services.naive_rag import naive_rag_answer
from src.services.vector_index import VectorIndex


class FakeEmbedder:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


class FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        self.calls.append((system, user))
        return self.response


@pytest.fixture
def seeded_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(settings, "sqlite_db_path", db_path)
    init_db(db_path)

    with get_connection() as conn:
        paper = PaperRepository(conn).upsert_metadata(
            PaperMetadata(
                arxiv_id="1111.11111",
                title="A Paper",
                authors=["A"],
                abstract="abstract",
                categories=["cs.AI"],
                published_date="2021-01-01",
                pdf_url="http://example.com/1.pdf",
            )
        )
        ChunkRepository(conn).replace_chunks(paper.id, [("reinforcement learning", 0, 10)])


def _build_indices() -> tuple[Bm25Index, VectorIndex]:
    with get_connection() as conn:
        chunks = ChunkRepository(conn).get_all()
    bm25_index = Bm25Index.build(chunks)
    client = QdrantClient(location=":memory:")
    vector_index = VectorIndex(client=client)
    vector_index.ensure_collection(dim=2)
    vector_index.upsert_chunks(chunks, FakeEmbedder())
    return bm25_index, vector_index


def test_naive_rag_answers_using_same_generation_prompt_as_agentic(seeded_db: None) -> None:
    bm25_index, vector_index = _build_indices()
    llm = FakeLLMClient("Here is an answer.")

    result = naive_rag_answer(
        bm25_index, vector_index, FakeEmbedder(), llm, "reinforcement learning"
    )

    assert result.answer == "Here is an answer."
    assert len(result.retrieved) == 1
    assert llm.calls[0][0] == GENERATE_SYSTEM_PROMPT


def test_naive_rag_returns_no_context_answer_when_nothing_retrieved(seeded_db: None) -> None:
    # Query with an empty corpus produces no retrieval candidates.
    with get_connection() as conn:
        ChunkRepository(conn).replace_chunks(1, [])
    bm25_index, vector_index = _build_indices()
    llm = FakeLLMClient("should not be used")

    result = naive_rag_answer(bm25_index, vector_index, FakeEmbedder(), llm, "anything")

    assert result.answer == NO_CONTEXT_ANSWER
    assert result.retrieved == []
    assert llm.calls == []
