from functools import lru_cache
from typing import Any, cast

from fastapi import APIRouter, HTTPException

from src.agents.graph import build_graph, initial_state
from src.config import settings
from src.models.chat import ChatRequest, ChatResponse
from src.services.bm25_index import Bm25Index
from src.services.embeddings import EmbeddingModel
from src.services.llm import get_llm_client
from src.services.vector_index import VectorIndex

router = APIRouter()


@lru_cache(maxsize=1)
def _get_graph() -> Any:
    bm25_index = Bm25Index.load(settings.bm25_index_path)
    vector_index = VectorIndex()
    embedder = EmbeddingModel()
    llm_client = get_llm_client()
    return build_graph(bm25_index, vector_index, embedder, llm_client)


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        graph = _get_graph()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503, detail="Search index not built yet. Run src/index.py."
        ) from exc

    result = cast(dict[str, Any], graph.invoke(initial_state(request.query)))

    return ChatResponse(
        answer=result["answer"],
        rejected=result["rejected"],
        trace=result["trace"],
    )
