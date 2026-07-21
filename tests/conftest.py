import os

# Must run before any `src.*` import (including the ones below) — src.config
# calls load_dotenv() on import, and load_dotenv() does not override an
# already-set env var. Setting these to "" here (before that happens) means
# Settings() ends up with empty Langfuse credentials during tests regardless
# of what's in .env, so tracing stays disabled and test runs never send real
# trace data to Langfuse Cloud.
os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""

from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402
import redis  # noqa: E402

from src.services import cache as cache_module  # noqa: E402


@pytest.fixture(autouse=True)
def _no_real_redis_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never depend on whatever Redis happens to be reachable on
    the host — a stray unrelated Redis server on localhost:6379 previously
    caused cross-test cache pollution. Force every cache call through the
    real error-handling path instead."""
    mock_client = MagicMock()
    mock_client.get.side_effect = redis.RedisError("no redis in tests")
    mock_client.set.side_effect = redis.RedisError("no redis in tests")
    monkeypatch.setattr(cache_module, "_client", mock_client)
