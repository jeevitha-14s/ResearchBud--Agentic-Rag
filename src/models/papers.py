from pydantic import BaseModel

from src.config import settings


class IngestRequest(BaseModel):
    query: str
    max_results: int = settings.arxiv_default_max_results
    force: bool = False


class IngestResponse(BaseModel):
    ingested: int
    skipped: int


class ReindexResponse(BaseModel):
    chunks_indexed: int


class PaperSummary(BaseModel):
    id: int
    arxiv_id: str
    title: str
    categories: list[str]
    published_date: str
    ingested_at: str | None
    chunk_count: int
