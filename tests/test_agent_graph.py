from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from src.agents.generate import GENERATE_SYSTEM_PROMPT, NO_CONTEXT_ANSWER
from src.agents.grade import GRADE_SYSTEM_PROMPT
from src.agents.graph import CompiledGraph, build_graph, initial_state
from src.agents.guardrail import GUARDRAIL_SYSTEM_PROMPT, REJECTION_MESSAGE
from src.agents.rewrite import REWRITE_SYSTEM_PROMPT
from src.config import settings
from src.db.connection import get_connection
from src.db.repository import ChunkRepository, PaperRepository
from src.db.schema import init_db
from src.models.paper import Chunk, PaperMetadata
from src.services.bm25_index import Bm25Index
from src.services.vector_index import VectorIndex


class FakeEmbedder:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


class ScriptedLLMClient:
    """Routes canned responses by which node's system prompt is calling."""

    def __init__(
        self,
        guardrail: str = "ON_TOPIC",
        grade_responses: list[str] | None = None,
        rewrite: str = "rewritten query",
        generate: str = "final answer",
    ) -> None:
        self.guardrail = guardrail
        self.grade_responses = grade_responses if grade_responses is not None else ["1"]
        self.rewrite = rewrite
        self.generate = generate
        self.calls: list[str] = []

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        if system == GUARDRAIL_SYSTEM_PROMPT:
            self.calls.append("guardrail")
            return self.guardrail
        if system == GRADE_SYSTEM_PROMPT:
            self.calls.append("grade")
            return self.grade_responses.pop(0) if self.grade_responses else "NONE"
        if system == REWRITE_SYSTEM_PROMPT:
            self.calls.append("rewrite")
            return self.rewrite
        if system == GENERATE_SYSTEM_PROMPT:
            self.calls.append("generate")
            return self.generate
        raise AssertionError(f"Unexpected system prompt: {system}")


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


def _chunks() -> list[Chunk]:
    with get_connection() as conn:
        return ChunkRepository(conn).get_all()


def _build_test_graph(llm_client: ScriptedLLMClient) -> CompiledGraph:
    chunks = _chunks()
    bm25_index = Bm25Index.build(chunks)
    client = QdrantClient(location=":memory:")
    vector_index = VectorIndex(client=client)
    vector_index.ensure_collection(dim=2)
    vector_index.upsert_chunks(chunks, FakeEmbedder())
    return build_graph(bm25_index, vector_index, FakeEmbedder(), llm_client)


def test_guardrail_rejects_off_topic_query_without_retrieval(seeded_db: None) -> None:
    llm = ScriptedLLMClient(guardrail="OFF_TOPIC")
    graph = _build_test_graph(llm)

    result = graph.invoke(initial_state("what's the weather today?"))

    assert result["rejected"] is True
    assert result["answer"] == REJECTION_MESSAGE
    assert llm.calls == ["guardrail"]


def test_full_happy_path_answers_on_first_retrieval(seeded_db: None) -> None:
    llm = ScriptedLLMClient(guardrail="ON_TOPIC", grade_responses=["1"], generate="final answer")
    graph = _build_test_graph(llm)

    result = graph.invoke(initial_state("tell me about reinforcement learning"))

    assert result["rejected"] is False
    assert result["answer"] == "final answer"
    assert llm.calls == ["guardrail", "grade", "generate"]


def test_rewrite_then_succeed(seeded_db: None) -> None:
    llm = ScriptedLLMClient(
        guardrail="ON_TOPIC",
        grade_responses=["NONE", "1"],
        rewrite="reinforcement learning survey",
        generate="final answer",
    )
    graph = _build_test_graph(llm)

    result = graph.invoke(initial_state("tell me about something unrelated to the corpus"))

    assert result["answer"] == "final answer"
    assert llm.calls == ["guardrail", "grade", "rewrite", "grade", "generate"]
    assert result["rewrite_count"] == 1


def test_rewrite_cap_exhausted_still_terminates(seeded_db: None) -> None:
    # All grade calls return NONE, so the rewrite loop exhausts its cap and
    # generate_node short-circuits on an empty graded list (never calling
    # the LLM) rather than looping forever.
    llm = ScriptedLLMClient(
        guardrail="ON_TOPIC",
        grade_responses=["NONE", "NONE", "NONE"],
        rewrite="still no match",
        generate="should not be called",
    )
    graph = _build_test_graph(llm)

    result = graph.invoke(initial_state("tell me about something unrelated to the corpus"))

    assert result["rewrite_count"] == settings.max_rewrites
    assert result["answer"] == NO_CONTEXT_ANSWER
    assert llm.calls.count("rewrite") == settings.max_rewrites
    assert "generate" not in llm.calls
