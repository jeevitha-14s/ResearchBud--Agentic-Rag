from src.config import settings
from src.db.connection import get_connection
from src.db.repository import ChunkRepository, PaperRepository
from src.models.search import SearchResult
from src.services.bm25_index import Bm25Index
from src.services.embeddings import Embedder
from src.services.rrf import reciprocal_rank_fusion
from src.services.tracing import observe
from src.services.vector_index import VectorIndex


def _hydrate(ranked: list[tuple[int, float]]) -> list[SearchResult]:
    results = []
    with get_connection() as conn:
        chunk_repo = ChunkRepository(conn)
        paper_repo = PaperRepository(conn)
        for chunk_id, score in ranked:
            chunk = chunk_repo.get_by_id(chunk_id)
            if chunk is None:
                continue
            paper = paper_repo.get_by_id(chunk.paper_id)
            if paper is None:
                continue
            results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    paper_id=paper.id,
                    arxiv_id=paper.arxiv_id,
                    title=paper.title,
                    text=chunk.text,
                    score=score,
                )
            )
    return results


@observe(name="bm25_search")
def bm25_search(bm25_index: Bm25Index, query: str, top_k: int) -> list[SearchResult]:
    ranked = bm25_index.search(query, top_k)
    return _hydrate(ranked)


@observe(name="vector_search")
def vector_search(
    vector_index: VectorIndex, embedder: Embedder, query: str, top_k: int
) -> list[SearchResult]:
    query_vector = embedder.embed_query(query)
    ranked = vector_index.search(query_vector, top_k)
    return _hydrate(ranked)


@observe(name="hybrid_search")
def hybrid_search(
    bm25_index: Bm25Index,
    vector_index: VectorIndex,
    embedder: Embedder,
    query: str,
    top_k: int,
) -> list[SearchResult]:
    pool = settings.search_candidate_pool
    bm25_ranked = [chunk_id for chunk_id, _ in bm25_index.search(query, pool)]

    query_vector = embedder.embed_query(query)
    vector_ranked = [chunk_id for chunk_id, _ in vector_index.search(query_vector, pool)]

    fused = reciprocal_rank_fusion([bm25_ranked, vector_ranked], k=settings.rrf_k, top_n=top_k)
    return _hydrate(fused)
