from collections.abc import Callable
from typing import Any

from src.agents.state import AgentState
from src.services.llm import LLMClient

GUARDRAIL_SYSTEM_PROMPT = (
    "You are a strict classifier. Decide whether the user's question is about "
    "academic research papers, arXiv, or a research topic that arXiv papers "
    "would plausibly cover. Respond with exactly one word: ON_TOPIC or "
    "OFF_TOPIC. Do not explain."
)

REJECTION_MESSAGE = (
    "I can only answer questions about research papers and topics covered by "
    "arXiv. Please ask something related to that."
)


def make_guardrail_node(llm_client: LLMClient) -> Callable[[AgentState], dict[str, Any]]:
    def guardrail_node(state: AgentState) -> dict[str, Any]:
        query = state["query"].strip()
        if not query:
            return {
                "is_on_topic": False,
                "rejected": True,
                "answer": REJECTION_MESSAGE,
                "trace": [*state["trace"], "guardrail:empty_query"],
            }

        response = llm_client.complete(GUARDRAIL_SYSTEM_PROMPT, query, max_tokens=10)
        is_on_topic = "ON_TOPIC" in response.upper()

        update: dict[str, Any] = {
            "is_on_topic": is_on_topic,
            "trace": [*state["trace"], f"guardrail:{'on_topic' if is_on_topic else 'off_topic'}"],
        }
        if not is_on_topic:
            update["rejected"] = True
            update["answer"] = REJECTION_MESSAGE
        return update

    return guardrail_node
