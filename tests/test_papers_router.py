from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


@patch("src.routers.papers.init_db")
@patch("src.routers.papers.ingest_query", return_value=(3, 2))
def test_ingest_returns_counts(mock_ingest: MagicMock, mock_init_db: MagicMock) -> None:
    response = client.post("/ingest", json={"query": "cat:cs.AI", "max_results": 5})

    assert response.status_code == 200
    body = response.json()
    assert body == {"ingested": 3, "skipped": 2}
    mock_ingest.assert_called_once_with("cat:cs.AI", 5, False)


@patch("src.routers.papers.ingest_query", return_value=(0, 0))
@patch("src.routers.papers.init_db")
def test_ingest_defaults_force_to_false(mock_init_db: MagicMock, mock_ingest: MagicMock) -> None:
    client.post("/ingest", json={"query": "cat:cs.AI"})
    args, _ = mock_ingest.call_args
    assert args[2] is False


@patch("src.routers.papers.build_indices", return_value=42)
def test_reindex_returns_chunk_count(mock_build: MagicMock) -> None:
    response = client.post("/reindex")

    assert response.status_code == 200
    assert response.json() == {"chunks_indexed": 42}


@patch("src.routers.papers.get_connection")
def test_list_papers_returns_summaries_with_chunk_counts(
    mock_get_connection: MagicMock,
) -> None:
    mock_paper = MagicMock(
        id=1,
        arxiv_id="1111.11111",
        title="A Paper",
        categories=["cs.AI", "cs.LG"],
        published_date="2021-01-01",
        ingested_at="2021-01-02T00:00:00",
    )
    mock_conn = MagicMock()
    mock_get_connection.return_value.__enter__.return_value = mock_conn

    with (
        patch("src.routers.papers.PaperRepository") as mock_paper_repo_cls,
        patch("src.routers.papers.ChunkRepository") as mock_chunk_repo_cls,
    ):
        mock_paper_repo_cls.return_value.list_papers.return_value = [mock_paper]
        mock_chunk_repo_cls.return_value.count_by_paper_all.return_value = {1: 7}

        response = client.get("/papers")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["arxiv_id"] == "1111.11111"
    assert body[0]["chunk_count"] == 7


@patch("src.routers.papers.get_connection")
def test_list_papers_defaults_chunk_count_to_zero_when_missing(
    mock_get_connection: MagicMock,
) -> None:
    mock_paper = MagicMock(
        id=2,
        arxiv_id="2222.22222",
        title="Another Paper",
        categories=["cs.CL"],
        published_date="2021-02-01",
        ingested_at=None,
    )
    mock_get_connection.return_value.__enter__.return_value = MagicMock()

    with (
        patch("src.routers.papers.PaperRepository") as mock_paper_repo_cls,
        patch("src.routers.papers.ChunkRepository") as mock_chunk_repo_cls,
    ):
        mock_paper_repo_cls.return_value.list_papers.return_value = [mock_paper]
        mock_chunk_repo_cls.return_value.count_by_paper_all.return_value = {}

        response = client.get("/papers")

    assert response.json()[0]["chunk_count"] == 0
