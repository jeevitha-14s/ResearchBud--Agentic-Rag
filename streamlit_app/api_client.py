import os
from typing import Any

import httpx

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

_DEFAULT_TIMEOUT = 30.0
_LONG_TIMEOUT = 300.0  # ingestion/reindex can take minutes


class ApiError(Exception):
    """Raised for any backend call failure, with a message safe to show a user."""


def _request(method: str, path: str, *, timeout: float = _DEFAULT_TIMEOUT, **kwargs: Any) -> Any:
    try:
        response = httpx.request(method, f"{API_BASE_URL}{path}", timeout=timeout, **kwargs)
    except httpx.ConnectError as exc:
        raise ApiError(f"Cannot reach the backend at {API_BASE_URL}. Is it running?") from exc
    except httpx.TimeoutException as exc:
        raise ApiError("The backend took too long to respond.") from exc

    if response.status_code == 429:
        raise ApiError("Rate limit exceeded — please wait a moment and try again.")
    if response.status_code >= 400:
        detail = response.text
        try:
            detail = response.json().get("detail", detail)
        except ValueError:
            pass
        raise ApiError(f"Backend error ({response.status_code}): {detail}")

    return response.json()


def get_health() -> dict[str, Any]:
    return _request("GET", "/health")


def post_chat(query: str) -> dict[str, Any]:
    return _request("POST", "/chat", json={"query": query}, timeout=_LONG_TIMEOUT)


def post_ingest(query: str, max_results: int, force: bool) -> dict[str, Any]:
    return _request(
        "POST",
        "/ingest",
        json={"query": query, "max_results": max_results, "force": force},
        timeout=_LONG_TIMEOUT,
    )


def post_reindex() -> dict[str, Any]:
    return _request("POST", "/reindex", timeout=_LONG_TIMEOUT)


def get_papers() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = _request("GET", "/papers")
    return result
