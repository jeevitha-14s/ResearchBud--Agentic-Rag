from collections.abc import Callable
from typing import Any

from src.agents.state import AgentState
from src.config import settings
from src.services.bm25_index import Bm25Index
from src.services.embeddings import Embedder
from src.services.search import hybrid_search
from src.services.tracing import observe
from src.services.vector_index import VectorIndex


def make_retrieve_node(
    bm25_index: Bm25Index, vector_index: VectorIndex, embedder: Embedder
) -> Callable[[AgentState], dict[str, Any]]:
    @observe(name="retrieve_node")
    def retrieve_node(state: AgentState) -> dict[str, Any]:
        results = hybrid_search(
            bm25_index,
            vector_index,
            embedder,
            state["query"],
            top_k=settings.agent_retrieval_top_k,
        )
        return {
            "retrieved": results,
            "trace": [*state["trace"], f"retrieve:{len(results)}_chunks"],
        }

    return retrieve_node
