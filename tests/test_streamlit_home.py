import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "streamlit_app"))

from api_client import ApiError  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

PAGE_PATH = str(Path(__file__).resolve().parent.parent / "streamlit_app" / "Home.py")


@patch("api_client.get_health", return_value={"status": "ok"})
def test_home_shows_healthy_status(mock_get_health: object) -> None:
    at = AppTest.from_file(PAGE_PATH)
    at.run()

    assert at.exception == []
    success_values = [s.value for s in at.success]
    assert any("status: ok" in v for v in success_values)


@patch("api_client.get_health", side_effect=ApiError("Cannot reach the backend"))
def test_home_shows_error_when_backend_unreachable(mock_get_health: object) -> None:
    at = AppTest.from_file(PAGE_PATH)
    at.run()

    assert at.exception == []
    error_values = [e.value for e in at.error]
    assert any("Cannot reach the backend" in v for v in error_values)
