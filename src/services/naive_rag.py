from src.agents.generate import GENERATE_SYSTEM_PROMPT, NO_CONTEXT_ANSWER, build_generation_prompt
from src.config import settings
from src.models.search import SearchResult
from src.services.bm25_index import Bm25Index
from src.services.embeddings import Embedder
from src.services.llm import LLMClient
from src.services.search import hybrid_search
from src.services.vector_index import VectorIndex


class NaiveRagResult:
    def __init__(self, answer: str, retrieved: list[SearchResult]) -> None:
        self.answer = answer
        self.retrieved = retrieved


def naive_rag_answer(
    bm25_index: Bm25Index,
    vector_index: VectorIndex,
    embedder: Embedder,
    llm_client: LLMClient,
    query: str,
    top_k: int | None = None,
) -> NaiveRagResult:
    """Single-shot retrieve-then-generate: no guardrail, no grading, no
    rewrite. Every retrieved chunk is fed to generation regardless of
    relevance. Uses the identical generation prompt as the agentic
    pipeline so a naive-vs-agentic comparison isolates only the presence
    of guardrail/grade/rewrite, not a different prompt."""
    results = hybrid_search(
        bm25_index, vector_index, embedder, query, top_k or settings.agent_retrieval_top_k
    )

    if not results:
        return NaiveRagResult(answer=NO_CONTEXT_ANSWER, retrieved=[])

    prompt = build_generation_prompt(query, [(r.title, r.arxiv_id, r.text) for r in results])
    answer = llm_client.complete(GENERATE_SYSTEM_PROMPT, prompt, max_tokens=1024)
    return NaiveRagResult(answer=answer, retrieved=results)
