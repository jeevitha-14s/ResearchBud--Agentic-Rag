from unittest.mock import MagicMock

import pytest
import redis

from src.services import cache as cache_module
from src.services.cache import build_cache_key, get_cached, set_cached


def test_build_cache_key_is_deterministic() -> None:
    key1 = build_cache_key("search", "hybrid", "robotics", "5")
    key2 = build_cache_key("search", "hybrid", "robotics", "5")
    assert key1 == key2


def test_build_cache_key_is_case_and_whitespace_insensitive() -> None:
    key1 = build_cache_key("search", "  Robotics  ")
    key2 = build_cache_key("search", "robotics")
    assert key1 == key2


def test_build_cache_key_differs_for_different_inputs() -> None:
    key1 = build_cache_key("search", "robotics")
    key2 = build_cache_key("search", "molecules")
    assert key1 != key2


def test_get_cached_returns_value_on_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    mock_client.get.return_value = "cached value"
    monkeypatch.setattr(cache_module, "_client", mock_client)

    assert get_cached("some-key") == "cached value"


def test_get_cached_returns_none_on_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    mock_client.get.return_value = None
    monkeypatch.setattr(cache_module, "_client", mock_client)

    assert get_cached("some-key") is None


def test_get_cached_degrades_to_none_on_redis_error(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    mock_client.get.side_effect = redis.RedisError("connection refused")
    monkeypatch.setattr(cache_module, "_client", mock_client)

    assert get_cached("some-key") is None


def test_set_cached_writes_with_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    monkeypatch.setattr(cache_module, "_client", mock_client)

    set_cached("some-key", "some-value", ttl=120)

    mock_client.set.assert_called_once_with("some-key", "some-value", ex=120)


def test_set_cached_silently_swallows_redis_error(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_client = MagicMock()
    mock_client.set.side_effect = redis.RedisError("connection refused")
    monkeypatch.setattr(cache_module, "_client", mock_client)

    set_cached("some-key", "some-value")  # must not raise
