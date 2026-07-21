from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.main import app
from src.models.search import SearchResult

client = TestClient(app)

_FAKE_RESULT = SearchResult(
    chunk_id=1,
    paper_id=1,
    arxiv_id="1111.11111",
    title="A Paper",
    text="some chunk text",
    score=0.9,
)


@patch("src.routers.search._get_embedder")
@patch("src.routers.search._get_vector_index")
@patch("src.routers.search._get_bm25_index")
@patch("src.routers.search.hybrid_search", return_value=[_FAKE_RESULT])
def test_search_default_mode_is_hybrid(
    mock_hybrid: MagicMock,
    mock_bm25_idx: MagicMock,
    mock_vector_idx: MagicMock,
    mock_embedder: MagicMock,
) -> None:
    response = client.get("/search", params={"q": "robotics"})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "hybrid"
    assert body["results"][0]["arxiv_id"] == "1111.11111"


@patch("src.routers.search._get_bm25_index")
@patch("src.routers.search.bm25_search", return_value=[_FAKE_RESULT])
def test_search_bm25_mode(mock_bm25: MagicMock, mock_bm25_idx: MagicMock) -> None:
    response = client.get("/search", params={"q": "robotics", "mode": "bm25"})

    assert response.status_code == 200
    assert response.json()["mode"] == "bm25"


def test_search_rejects_invalid_mode() -> None:
    response = client.get("/search", params={"q": "robotics", "mode": "nonsense"})
    assert response.status_code == 422


@patch("src.routers.search._get_bm25_index", side_effect=FileNotFoundError)
def test_search_returns_503_when_index_missing(mock_bm25_idx: MagicMock) -> None:
    response = client.get("/search", params={"q": "robotics", "mode": "bm25"})
    assert response.status_code == 503
