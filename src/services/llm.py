from typing import Protocol

import anthropic
import openai

from src.config import settings
from src.services.retry import with_retry


class LLMClient(Protocol):
    def complete(self, system: str, user: str, max_tokens: int) -> str: ...


class AnthropicLLMClient:
    def __init__(self, model: str | None = None, max_retries: int | None = None) -> None:
        self._client = anthropic.Anthropic()
        self._model = model or settings.llm_model
        self._max_retries = max_retries or settings.llm_max_retries

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        @with_retry(max_retries=self._max_retries)
        def _call() -> str:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            for block in response.content:
                if block.type == "text":
                    return block.text
            return ""

        return _call()


class OpenAILLMClient:
    def __init__(self, model: str | None = None, max_retries: int | None = None) -> None:
        self._client = openai.OpenAI()
        self._model = model or settings.llm_model
        self._max_retries = max_retries or settings.llm_max_retries

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        @with_retry(max_retries=self._max_retries)
        def _call() -> str:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return response.choices[0].message.content or ""

        return _call()


def get_llm_client() -> LLMClient:
    if settings.llm_provider == "openai":
        return OpenAILLMClient()
    return AnthropicLLMClient()
