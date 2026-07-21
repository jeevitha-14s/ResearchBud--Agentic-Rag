from unittest.mock import MagicMock, patch

import pytest

from src.config import settings
from src.services.llm import AnthropicLLMClient, OpenAILLMClient, get_llm_client


@patch("src.services.llm.anthropic.Anthropic")
def test_anthropic_client_extracts_text_block(mock_anthropic_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "hello from claude"
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_cls.return_value = mock_client

    client = AnthropicLLMClient(model="claude-sonnet-5", max_retries=1)
    result = client.complete("system prompt", "user prompt", max_tokens=10)

    assert result == "hello from claude"
    mock_client.messages.create.assert_called_once_with(
        model="claude-sonnet-5",
        max_tokens=10,
        system="system prompt",
        messages=[{"role": "user", "content": "user prompt"}],
    )


@patch("src.services.llm.anthropic.Anthropic")
def test_anthropic_client_returns_empty_when_no_text_block(
    mock_anthropic_cls: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_cls.return_value = mock_client

    client = AnthropicLLMClient(model="claude-sonnet-5", max_retries=1)
    result = client.complete("system", "user", max_tokens=10)

    assert result == ""


@patch("src.services.llm.openai.OpenAI")
def test_openai_client_extracts_message_content(mock_openai_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="hello from gpt"))]
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_cls.return_value = mock_client

    client = OpenAILLMClient(model="gpt-4o-mini", max_retries=1)
    result = client.complete("system prompt", "user prompt", max_tokens=10)

    assert result == "hello from gpt"


def test_get_llm_client_defaults_to_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    with patch("src.services.llm.anthropic.Anthropic"):
        client = get_llm_client()
        assert isinstance(client, AnthropicLLMClient)


def test_get_llm_client_selects_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "openai")
    with patch("src.services.llm.openai.OpenAI"):
        client = get_llm_client()
        assert isinstance(client, OpenAILLMClient)
