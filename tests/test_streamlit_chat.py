import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "streamlit_app"))

from api_client import ApiError  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

PAGE_PATH = str(Path(__file__).resolve().parent.parent / "streamlit_app" / "pages" / "1_Chat.py")


@patch(
    "api_client.post_chat",
    return_value={
        "answer": "The paper proposes X.",
        "rejected": False,
        "trace": ["guardrail:on_topic", "generate:answered"],
    },
)
def test_chat_happy_path_shows_answer_and_trace(mock_post_chat: object) -> None:
    at = AppTest.from_file(PAGE_PATH)
    at.run()
    at.chat_input[0].set_value("What does the paper propose?").run()

    assert at.exception == []
    markdown_values = [m.value for m in at.markdown]
    assert "What does the paper propose?" in markdown_values
    assert "The paper proposes X." in markdown_values
    trace_texts = [t.value for t in at.text]
    assert "guardrail:on_topic" in trace_texts


@patch(
    "api_client.post_chat",
    return_value={
        "answer": "I can only answer questions about research papers.",
        "rejected": True,
        "trace": ["guardrail:off_topic"],
    },
)
def test_chat_rejected_shows_warning_not_markdown(mock_post_chat: object) -> None:
    at = AppTest.from_file(PAGE_PATH)
    at.run()
    at.chat_input[0].set_value("what's the weather?").run()

    assert at.exception == []
    warning_values = [w.value for w in at.warning]
    assert "I can only answer questions about research papers." in warning_values


@patch("api_client.post_chat", side_effect=ApiError("backend unreachable"))
def test_chat_api_error_shows_error_message(mock_post_chat: object) -> None:
    at = AppTest.from_file(PAGE_PATH)
    at.run()
    at.chat_input[0].set_value("anything").run()

    assert at.exception == []
    error_values = [e.value for e in at.error]
    assert "backend unreachable" in error_values


@patch(
    "api_client.post_chat",
    return_value={"answer": "answer one", "rejected": False, "trace": []},
)
def test_chat_history_persists_across_turns(mock_post_chat: object) -> None:
    at = AppTest.from_file(PAGE_PATH)
    at.run()
    at.chat_input[0].set_value("first question").run()
    at.chat_input[0].set_value("second question").run()

    markdown_values = [m.value for m in at.markdown]
    assert "first question" in markdown_values
    assert "second question" in markdown_values
    assert markdown_values.count("answer one") == 2
