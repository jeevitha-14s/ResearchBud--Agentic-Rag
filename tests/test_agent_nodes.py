from src.agents.generate import NO_CONTEXT_ANSWER, make_generate_node
from src.agents.grade import make_grade_node
from src.agents.graph import initial_state
from src.agents.guardrail import REJECTION_MESSAGE, make_guardrail_node
from src.agents.rewrite import make_rewrite_node
from src.models.search import SearchResult


class FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        self.calls.append((system, user))
        return self.response


def _result(chunk_id: int, text: str) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        paper_id=1,
        arxiv_id="1111.11111",
        title="A Paper",
        text=text,
        score=1.0,
    )


def test_guardrail_accepts_on_topic_query() -> None:
    node = make_guardrail_node(FakeLLMClient("ON_TOPIC"))
    state = initial_state("what does this paper say about transformers?")

    update = node(state)

    assert update["is_on_topic"] is True
    assert "rejected" not in update


def test_guardrail_rejects_off_topic_query() -> None:
    node = make_guardrail_node(FakeLLMClient("OFF_TOPIC"))
    state = initial_state("what's the weather today?")

    update = node(state)

    assert update["is_on_topic"] is False
    assert update["rejected"] is True
    assert update["answer"] == REJECTION_MESSAGE


def test_guardrail_rejects_empty_query_without_llm_call() -> None:
    llm = FakeLLMClient("ON_TOPIC")
    node = make_guardrail_node(llm)
    state = initial_state("   ")

    update = node(state)

    assert update["rejected"] is True
    assert llm.calls == []


def test_grade_filters_to_relevant_chunks() -> None:
    node = make_grade_node(FakeLLMClient("1, 3"))
    state = initial_state("query")
    state["retrieved"] = [_result(1, "a"), _result(2, "b"), _result(3, "c")]

    update = node(state)

    assert [r.chunk_id for r in update["graded"]] == [1, 3]


def test_grade_handles_none_response() -> None:
    node = make_grade_node(FakeLLMClient("NONE"))
    state = initial_state("query")
    state["retrieved"] = [_result(1, "a")]

    update = node(state)

    assert update["graded"] == []


def test_grade_treats_unparseable_response_as_no_relevant_chunks() -> None:
    node = make_grade_node(FakeLLMClient("I'm not sure how to answer that."))
    state = initial_state("query")
    state["retrieved"] = [_result(1, "a"), _result(2, "b")]

    update = node(state)

    assert update["graded"] == []


def test_rewrite_increments_count_and_updates_query() -> None:
    node = make_rewrite_node(FakeLLMClient("better search query"))
    state = initial_state("original query")

    update = node(state)

    assert update["query"] == "better search query"
    assert update["rewrite_count"] == 1


def test_generate_returns_no_context_answer_when_nothing_graded() -> None:
    node = make_generate_node(FakeLLMClient("should not be used"))
    state = initial_state("query")
    state["graded"] = []

    update = node(state)

    assert update["answer"] == NO_CONTEXT_ANSWER


def test_generate_calls_llm_with_graded_context() -> None:
    llm = FakeLLMClient("Here is the answer (A Paper, arXiv:1111.11111).")
    node = make_generate_node(llm)
    state = initial_state("query")
    state["original_query"] = "query"
    state["graded"] = [_result(1, "relevant text")]

    update = node(state)

    assert update["answer"] == "Here is the answer (A Paper, arXiv:1111.11111)."
    assert len(llm.calls) == 1
    assert "relevant text" in llm.calls[0][1]
