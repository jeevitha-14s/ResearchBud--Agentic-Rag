import logging
from pathlib import Path

import pdfplumber

from src.config import settings
from src.db.connection import get_connection
from src.db.repository import ChunkRepository, PaperRepository
from src.models.paper import PaperMetadata
from src.services.arxiv_client import ArxivClient
from src.services.chunker import chunk_text
from src.services.pdf_parser import download_pdf, extract_text

logger = logging.getLogger(__name__)

MIN_CHARS_PER_PAGE = 100


def ingest_paper(metadata: PaperMetadata, force: bool) -> bool:
    with get_connection() as conn:
        papers = PaperRepository(conn)
        chunks_repo = ChunkRepository(conn)

        if not force and papers.is_fully_ingested(metadata.arxiv_id):
            logger.info("Skipping already-ingested paper %s", metadata.arxiv_id)
            return False

        paper = papers.upsert_metadata(metadata)

        pdf_path = str(Path(settings.pdf_storage_dir) / f"{metadata.arxiv_id}.pdf")
        download_pdf(metadata.pdf_url, pdf_path)

        text = extract_text(pdf_path)
        if not _looks_valid(text, pdf_path):
            logger.warning("Skipping paper %s: extracted text looks invalid", metadata.arxiv_id)
            return False

        chunks = chunk_text(
            text,
            chunk_size=settings.chunk_size_chars,
            overlap=settings.chunk_overlap_chars,
        )
        chunks_repo.replace_chunks(paper.id, chunks)
        papers.mark_ingested(paper.id, pdf_path)
        return True


def _looks_valid(text: str, pdf_path: str) -> bool:
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
    return page_count > 0 and len(text) >= MIN_CHARS_PER_PAGE * page_count * 0.1


def ingest_query(query: str, max_results: int, force: bool) -> tuple[int, int]:
    client = ArxivClient()
    results = client.search(query, max_results)

    ingested = 0
    skipped = 0
    for metadata in results:
        if ingest_paper(metadata, force):
            ingested += 1
        else:
            skipped += 1
    return ingested, skipped
