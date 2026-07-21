from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address


def _build_test_app(limit: str) -> FastAPI:
    limiter = Limiter(key_func=get_remote_address, in_memory_fallback_enabled=True)
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/ping")
    @limiter.limit(limit)
    def ping(request: Request) -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_requests_under_the_limit_succeed() -> None:
    client = TestClient(_build_test_app("2/minute"))

    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200


def test_exceeding_the_limit_returns_429() -> None:
    client = TestClient(_build_test_app("2/minute"))

    client.get("/ping")
    client.get("/ping")
    response = client.get("/ping")

    assert response.status_code == 429
