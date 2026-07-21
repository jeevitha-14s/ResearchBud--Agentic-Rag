import hashlib
import logging

import redis

from src.config import settings

logger = logging.getLogger(__name__)

_client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)


def build_cache_key(*parts: str) -> str:
    normalized = "|".join(p.strip().lower() for p in parts)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"arxiv_rag:{digest}"


def get_cached(key: str) -> str | None:
    try:
        value = _client.get(key)
        return str(value) if value is not None else None
    except redis.RedisError:
        logger.warning("Redis get failed for key %s; treating as cache miss", key)
        return None


def set_cached(key: str, value: str, ttl: int | None = None) -> None:
    try:
        _client.set(key, value, ex=ttl or settings.redis_cache_ttl_seconds)
    except redis.RedisError:
        logger.warning("Redis set failed for key %s; skipping cache write", key)
