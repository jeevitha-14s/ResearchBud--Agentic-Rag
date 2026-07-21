from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from src.config import settings
from src.models.search import SearchResponse
from src.services.bm25_index import Bm25Index
from src.services.embeddings import EmbeddingModel
from src.services.search import bm25_search, hybrid_search, vector_search
from src.services.vector_index import VectorIndex

router = APIRouter()


@lru_cache(maxsize=1)
def _get_bm25_index() -> Bm25Index:
    return Bm25Index.load(settings.bm25_index_path)


@lru_cache(maxsize=1)
def _get_vector_index() -> VectorIndex:
    return VectorIndex()


@lru_cache(maxsize=1)
def _get_embedder() -> EmbeddingModel:
    return EmbeddingModel()


@router.get("/search", response_model=SearchResponse)
def search(
    q: str,
    mode: Literal["bm25", "vector", "hybrid"] = "hybrid",
    top_k: int = Query(default=settings.search_default_top_k, ge=1, le=50),
) -> SearchResponse:
    try:
        if mode == "bm25":
            results = bm25_search(_get_bm25_index(), q, top_k)
        elif mode == "vector":
            results = vector_search(_get_vector_index(), _get_embedder(), q, top_k)
        else:
            results = hybrid_search(
                _get_bm25_index(), _get_vector_index(), _get_embedder(), q, top_k
            )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503, detail="Search index not built yet. Run src/index.py."
        ) from exc

    return SearchResponse(query=q, mode=mode, results=results)
