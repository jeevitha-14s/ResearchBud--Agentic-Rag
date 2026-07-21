from langfuse import Langfuse, observe

from src.config import settings

_client = Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host,
    tracing_enabled=bool(settings.langfuse_public_key and settings.langfuse_secret_key),
)

__all__ = ["observe", "flush_traces"]


def flush_traces() -> None:
    _client.flush()
