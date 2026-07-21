from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import settings
from src.db.schema import init_db
from src.models.paper import PaperMetadata
from src.services.ingestion import ingest_paper


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = str(tmp_path / "test.db")
    pdf_dir = str(tmp_path / "pdfs")
    monkeypatch.setattr(settings, "sqlite_db_path", db_path)
    monkeypatch.setattr(settings, "pdf_storage_dir", pdf_dir)
    init_db(db_path)


def _sample_metadata() -> PaperMetadata:
    return PaperMetadata(
        arxiv_id="2101.00001v1",
        title="A Great Paper",
        authors=["Ada Lovelace"],
        abstract="An abstract.",
        categories=["cs.AI"],
        published_date="2021-01-01T00:00:00Z",
        pdf_url="http://arxiv.org/pdf/2101.00001v1",
    )


@patch("src.services.ingestion._looks_valid", return_value=True)
@patch("src.services.ingestion.extract_text", return_value="Paper body text. " * 200)
@patch("src.services.ingestion.download_pdf")
def test_ingest_paper_stores_metadata_and_chunks(
    mock_download: MagicMock, mock_extract: MagicMock, mock_valid: MagicMock
) -> None:
    from src.db.connection import get_connection
    from src.db.repository import ChunkRepository, PaperRepository

    result = ingest_paper(_sample_metadata(), force=False)

    assert result is True
    with get_connection() as conn:
        paper = PaperRepository(conn).get_by_arxiv_id("2101.00001v1")
        assert paper is not None
        assert paper.ingested_at is not None
        chunks = ChunkRepository(conn).get_by_paper(paper.id)
        assert len(chunks) > 0


@patch("src.services.ingestion._looks_valid", return_value=True)
@patch("src.services.ingestion.extract_text", return_value="Paper body text. " * 200)
@patch("src.services.ingestion.download_pdf")
def test_ingest_paper_skips_when_already_ingested(
    mock_download: MagicMock, mock_extract: MagicMock, mock_valid: MagicMock
) -> None:
    ingest_paper(_sample_metadata(), force=False)
    mock_download.reset_mock()

    result = ingest_paper(_sample_metadata(), force=False)

    assert result is False
    mock_download.assert_not_called()


@patch("src.services.ingestion._looks_valid", return_value=True)
@patch("src.services.ingestion.extract_text", return_value="Paper body text. " * 200)
@patch("src.services.ingestion.download_pdf")
def test_ingest_paper_force_reingests(
    mock_download: MagicMock, mock_extract: MagicMock, mock_valid: MagicMock
) -> None:
    ingest_paper(_sample_metadata(), force=False)
    mock_download.reset_mock()

    result = ingest_paper(_sample_metadata(), force=True)

    assert result is True
    mock_download.assert_called_once()


@patch("src.services.ingestion._looks_valid", return_value=False)
@patch("src.services.ingestion.extract_text", return_value="garbled")
@patch("src.services.ingestion.download_pdf")
def test_ingest_paper_skips_invalid_extracted_text(
    mock_download: MagicMock, mock_extract: MagicMock, mock_valid: MagicMock
) -> None:
    from src.db.connection import get_connection
    from src.db.repository import PaperRepository

    result = ingest_paper(_sample_metadata(), force=False)

    assert result is False
    with get_connection() as conn:
        paper = PaperRepository(conn).get_by_arxiv_id("2101.00001v1")
        assert paper is not None
        assert paper.ingested_at is None
