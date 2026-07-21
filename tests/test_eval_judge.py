import pytest

from src.eval.judge import score_faithfulness


class FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        return self.response


def test_score_faithfulness_parses_clean_integer() -> None:
    score = score_faithfulness(FakeLLMClient("4"), "q", "context", "answer")
    assert score == 4


def test_score_faithfulness_parses_integer_with_whitespace() -> None:
    score = score_faithfulness(FakeLLMClient("  5  "), "q", "context", "answer")
    assert score == 5


def test_score_faithfulness_raises_on_unparseable_response() -> None:
    with pytest.raises(ValueError, match="unparseable"):
        score_faithfulness(FakeLLMClient("I cannot evaluate this."), "q", "context", "answer")
