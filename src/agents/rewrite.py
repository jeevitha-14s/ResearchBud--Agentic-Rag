from collections.abc import Callable
from typing import Any

from src.agents.state import AgentState
from src.services.llm import LLMClient

REWRITE_SYSTEM_PROMPT = (
    "You rewrite search queries to improve retrieval from a corpus of arXiv "
    "research papers. Given a question that didn't retrieve enough relevant "
    "results, rewrite it as a more effective search query — use different "
    "phrasing, add relevant technical terms, or broaden/narrow scope as "
    "appropriate. Respond with ONLY the rewritten query, nothing else."
)


def make_rewrite_node(llm_client: LLMClient) -> Callable[[AgentState], dict[str, Any]]:
    def rewrite_node(state: AgentState) -> dict[str, Any]:
        rewritten = llm_client.complete(REWRITE_SYSTEM_PROMPT, state["query"], max_tokens=100)
        rewritten = rewritten.strip() or state["query"]

        return {
            "query": rewritten,
            "rewrite_count": state["rewrite_count"] + 1,
            "trace": [*state["trace"], f"rewrite:{rewritten!r}"],
        }

    return rewrite_node
