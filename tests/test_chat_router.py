from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


@patch("src.routers.chat._get_graph")
def test_chat_returns_answer_and_trace(mock_get_graph: MagicMock) -> None:
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "answer": "final answer",
        "rejected": False,
        "trace": [
            "guardrail:on_topic",
            "retrieve:1_chunks",
            "grade:1_of_1_relevant",
            "generate:answered",
        ],
    }
    mock_get_graph.return_value = mock_graph

    response = client.post("/chat", json={"query": "what does this paper say?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "final answer"
    assert body["rejected"] is False
    assert len(body["trace"]) == 4


@patch("src.routers.chat._get_graph")
def test_chat_returns_rejection_for_off_topic(mock_get_graph: MagicMock) -> None:
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "answer": "I can only answer questions about research papers.",
        "rejected": True,
        "trace": ["guardrail:off_topic"],
    }
    mock_get_graph.return_value = mock_graph

    response = client.post("/chat", json={"query": "what's the weather?"})

    assert response.status_code == 200
    assert response.json()["rejected"] is True


@patch("src.routers.chat._get_graph", side_effect=FileNotFoundError)
def test_chat_returns_503_when_index_missing(mock_get_graph: MagicMock) -> None:
    response = client.post("/chat", json={"query": "anything"})
    assert response.status_code == 503
