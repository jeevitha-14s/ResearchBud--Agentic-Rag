from pydantic import BaseModel


class SearchResult(BaseModel):
    chunk_id: int
    paper_id: int
    arxiv_id: str
    title: str
    text: str
    score: float


class SearchResponse(BaseModel):
    query: str
    mode: str
    results: list[SearchResult]
