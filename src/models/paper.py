from pydantic import BaseModel


class PaperMetadata(BaseModel):
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    published_date: str
    pdf_url: str


class Paper(PaperMetadata):
    id: int
    pdf_path: str | None = None
    ingested_at: str | None = None


class Chunk(BaseModel):
    id: int | None = None
    paper_id: int
    chunk_index: int
    text: str
    char_start: int
    char_end: int
