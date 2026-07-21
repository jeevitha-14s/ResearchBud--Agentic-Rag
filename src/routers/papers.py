from fastapi import APIRouter, Request

from src.config import settings
from src.db.connection import get_connection
from src.db.repository import ChunkRepository, PaperRepository
from src.db.schema import init_db
from src.index import build_indices
from src.models.papers import IngestRequest, IngestResponse, PaperSummary, ReindexResponse
from src.services.ingestion import ingest_query
from src.services.rate_limit import limiter

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
@limiter.limit(settings.rate_limit_ingest)
def ingest(request: Request, payload: IngestRequest) -> IngestResponse:
    init_db(settings.sqlite_db_path)
    ingested, skipped = ingest_query(payload.query, payload.max_results, payload.force)
    return IngestResponse(ingested=ingested, skipped=skipped)


@router.post("/reindex", response_model=ReindexResponse)
@limiter.limit(settings.rate_limit_ingest)
def reindex(request: Request) -> ReindexResponse:
    chunks_indexed = build_indices()
    return ReindexResponse(chunks_indexed=chunks_indexed)


@router.get("/papers", response_model=list[PaperSummary])
@limiter.limit(settings.rate_limit_search)
def list_papers(request: Request) -> list[PaperSummary]:
    with get_connection() as conn:
        papers = PaperRepository(conn).list_papers()
        chunk_counts = ChunkRepository(conn).count_by_paper_all()

    return [
        PaperSummary(
            id=paper.id,
            arxiv_id=paper.arxiv_id,
            title=paper.title,
            categories=paper.categories,
            published_date=paper.published_date,
            ingested_at=paper.ingested_at,
            chunk_count=chunk_counts.get(paper.id, 0),
        )
        for paper in papers
    ]
