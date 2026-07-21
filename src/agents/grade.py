import re
from collections.abc import Callable
from typing import Any

from src.agents.state import AgentState
from src.services.llm import LLMClient
from src.services.tracing import observe

GRADE_SYSTEM_PROMPT = (
    "You grade retrieved passages for relevance to a question. You will be "
    "given a question and a numbered list of passages. Respond with ONLY a "
    "comma-separated list of the numbers of passages that are relevant to "
    "answering the question. If none are relevant, respond with NONE. Do not "
    "explain."
)


def _build_user_prompt(query: str, chunks: list[str]) -> str:
    numbered = "\n\n".join(f"[{i}] {text}" for i, text in enumerate(chunks, start=1))
    return f"Question: {query}\n\nPassages:\n{numbered}"


def _parse_relevant_indices(response: str, num_chunks: int) -> set[int]:
    if "NONE" in response.upper():
        return set()
    indices = {int(match) for match in re.findall(r"\d+", response)}
    return {i for i in indices if 1 <= i <= num_chunks}


def make_grade_node(llm_client: LLMClient) -> Callable[[AgentState], dict[str, Any]]:
    @observe(name="grade_node")
    def grade_node(state: AgentState) -> dict[str, Any]:
        retrieved = state["retrieved"]
        if not retrieved:
            return {"graded": [], "trace": [*state["trace"], "grade:no_candidates"]}

        prompt = _build_user_prompt(state["query"], [r.text for r in retrieved])
        response = llm_client.complete(GRADE_SYSTEM_PROMPT, prompt, max_tokens=100)
        relevant_indices = _parse_relevant_indices(response, len(retrieved))
        graded = [retrieved[i - 1] for i in sorted(relevant_indices)]

        return {
            "graded": graded,
            "trace": [*state["trace"], f"grade:{len(graded)}_of_{len(retrieved)}_relevant"],
        }

    return grade_node
