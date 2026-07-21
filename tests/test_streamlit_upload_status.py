import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "streamlit_app"))

from api_client import ApiError  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

PAGE_PATH = str(
    Path(__file__).resolve().parent.parent / "streamlit_app" / "pages" / "2_Upload_Status.py"
)


@patch("api_client.get_papers", return_value=[])
@patch("api_client.post_ingest", return_value={"ingested": 3, "skipped": 1})
def test_ingest_form_success_shows_counts(
    mock_post_ingest: object, mock_get_papers: object
) -> None:
    at = AppTest.from_file(PAGE_PATH)
    at.run()
    at.text_input[0].set_value("cat:cs.AI")
    at.button[0].click().run()

    assert at.exception == []
    success_values = [s.value for s in at.success]
    assert any("Ingested 3, skipped 1" in v for v in success_values)


@patch("api_client.get_papers", return_value=[])
@patch("api_client.post_ingest", side_effect=ApiError("backend unreachable"))
def test_ingest_form_api_error_shows_error(
    mock_post_ingest: object, mock_get_papers: object
) -> None:
    at = AppTest.from_file(PAGE_PATH)
    at.run()
    at.button[0].click().run()

    assert at.exception == []
    error_values = [e.value for e in at.error]
    assert "backend unreachable" in error_values


@patch("api_client.get_papers", return_value=[])
@patch("api_client.post_reindex", return_value={"chunks_indexed": 42})
def test_reindex_button_success_shows_count(
    mock_post_reindex: object, mock_get_papers: object
) -> None:
    at = AppTest.from_file(PAGE_PATH)
    at.run()
    at.button[1].click().run()

    assert at.exception == []
    success_values = [s.value for s in at.success]
    assert any("Indexed 42 chunks" in v for v in success_values)


@patch("api_client.get_papers", return_value=[])
def test_papers_section_shows_empty_state(mock_get_papers: object) -> None:
    at = AppTest.from_file(PAGE_PATH)
    at.run()

    assert at.exception == []
    info_values = [i.value for i in at.info]
    assert any("No papers ingested yet" in v for v in info_values)


@patch(
    "api_client.get_papers",
    return_value=[
        {
            "id": 1,
            "arxiv_id": "1111.11111",
            "title": "A Paper",
            "categories": ["cs.AI"],
            "published_date": "2021-01-01",
            "ingested_at": "2021-01-02T00:00:00",
            "chunk_count": 5,
        }
    ],
)
def test_papers_section_renders_dataframe_when_populated(mock_get_papers: object) -> None:
    at = AppTest.from_file(PAGE_PATH)
    at.run()

    assert at.exception == []
    assert len(at.dataframe) == 1
