from functools import lru_cache
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from src.agents.graph import build_graph, run_graph
from src.config import settings
from src.models.chat import ChatRequest, ChatResponse
from src.services.bm25_index import Bm25Index
from src.services.cache import build_cache_key, get_cached, set_cached
from src.services.embeddings import EmbeddingModel
from src.services.llm import get_llm_client
from src.services.rate_limit import limiter
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
@limiter.limit(settings.rate_limit_chat)
def chat(request: Request, payload: ChatRequest) -> ChatResponse:
    cache_key = build_cache_key("chat", payload.query)
    cached = get_cached(cache_key)
    if cached is not None:
        return ChatResponse.model_validate_json(cached)

    try:
        graph = _get_graph()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503, detail="Search index not built yet. Run src/index.py."
        ) from exc

    result = run_graph(graph, payload.query)

    response = ChatResponse(
        answer=result["answer"],
        rejected=result["rejected"],
        trace=result["trace"],
    )
    set_cached(cache_key, response.model_dump_json())
    return response
