from collections.abc import Callable
from typing import Any

from src.agents.state import AgentState
from src.services.llm import LLMClient
from src.services.tracing import observe

GENERATE_SYSTEM_PROMPT = (
    "You answer questions using only the provided context passages from "
    "research papers. Cite the paper title and arXiv ID for every claim you "
    "make, in the form (Title, arXiv:ID). If the context doesn't contain "
    "enough information to answer, say so explicitly instead of guessing."
)

NO_CONTEXT_ANSWER = (
    "I couldn't find relevant information in the ingested papers to answer this question."
)


def _build_user_prompt(query: str, chunks: list[tuple[str, str, str]]) -> str:
    context = "\n\n".join(
        f"[{title}, arXiv:{arxiv_id}]\n{text}" for title, arxiv_id, text in chunks
    )
    return f"Question: {query}\n\nContext:\n{context}"


def make_generate_node(llm_client: LLMClient) -> Callable[[AgentState], dict[str, Any]]:
    @observe(name="generate_node")
    def generate_node(state: AgentState) -> dict[str, Any]:
        graded = state["graded"]
        if not graded:
            return {
                "answer": NO_CONTEXT_ANSWER,
                "trace": [*state["trace"], "generate:no_context"],
            }

        prompt = _build_user_prompt(
            state["original_query"],
            [(r.title, r.arxiv_id, r.text) for r in graded],
        )
        answer = llm_client.complete(GENERATE_SYSTEM_PROMPT, prompt, max_tokens=1024)

        return {
            "answer": answer,
            "trace": [*state["trace"], "generate:answered"],
        }

    return generate_node
