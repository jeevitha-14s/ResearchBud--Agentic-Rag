import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from src.db.repository import ChunkRepository, PaperRepository
from src.db.schema import init_db
from src.models.paper import PaperMetadata


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    yield connection
    connection.close()


def _sample_metadata(arxiv_id: str = "2101.00001v1") -> PaperMetadata:
    return PaperMetadata(
        arxiv_id=arxiv_id,
        title="A Great Paper",
        authors=["Ada Lovelace", "Alan Turing"],
        abstract="This is the abstract.",
        categories=["cs.AI", "cs.LG"],
        published_date="2021-01-01T00:00:00Z",
        pdf_url="http://arxiv.org/pdf/2101.00001v1",
    )


def test_upsert_metadata_inserts_new_paper(conn: sqlite3.Connection) -> None:
    repo = PaperRepository(conn)
    paper = repo.upsert_metadata(_sample_metadata())

    assert paper.arxiv_id == "2101.00001v1"
    assert paper.title == "A Great Paper"
    assert paper.authors == ["Ada Lovelace", "Alan Turing"]
    assert paper.ingested_at is None


def test_upsert_metadata_updates_existing_paper(conn: sqlite3.Connection) -> None:
    repo = PaperRepository(conn)
    repo.upsert_metadata(_sample_metadata())

    updated_metadata = _sample_metadata()
    updated_metadata.title = "An Updated Title"
    paper = repo.upsert_metadata(updated_metadata)

    assert paper.title == "An Updated Title"
    all_papers = repo.list_papers()
    assert len(all_papers) == 1


def test_get_by_arxiv_id_returns_none_when_missing(conn: sqlite3.Connection) -> None:
    repo = PaperRepository(conn)
    assert repo.get_by_arxiv_id("nonexistent") is None


def test_mark_ingested_sets_pdf_path_and_timestamp(conn: sqlite3.Connection) -> None:
    repo = PaperRepository(conn)
    paper = repo.upsert_metadata(_sample_metadata())

    assert not repo.is_fully_ingested(paper.arxiv_id)
    repo.mark_ingested(paper.id, "/data/pdfs/2101.00001v1.pdf")
    assert repo.is_fully_ingested(paper.arxiv_id)

    refreshed = repo.get_by_arxiv_id(paper.arxiv_id)
    assert refreshed is not None
    assert refreshed.pdf_path == "/data/pdfs/2101.00001v1.pdf"
    assert refreshed.ingested_at is not None


def test_replace_chunks_stores_and_retrieves(conn: sqlite3.Connection) -> None:
    paper_repo = PaperRepository(conn)
    chunk_repo = ChunkRepository(conn)
    paper = paper_repo.upsert_metadata(_sample_metadata())

    chunk_repo.replace_chunks(
        paper.id,
        [("first chunk", 0, 11), ("second chunk", 11, 24)],
    )
    chunks = chunk_repo.get_by_paper(paper.id)

    assert len(chunks) == 2
    assert chunks[0].text == "first chunk"
    assert chunks[0].chunk_index == 0
    assert chunks[1].char_start == 11


def test_replace_chunks_removes_old_chunks(conn: sqlite3.Connection) -> None:
    paper_repo = PaperRepository(conn)
    chunk_repo = ChunkRepository(conn)
    paper = paper_repo.upsert_metadata(_sample_metadata())

    chunk_repo.replace_chunks(paper.id, [("old chunk", 0, 9)])
    chunk_repo.replace_chunks(paper.id, [("new chunk", 0, 9)])

    chunks = chunk_repo.get_by_paper(paper.id)
    assert len(chunks) == 1
    assert chunks[0].text == "new chunk"
