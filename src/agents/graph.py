from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.generate import make_generate_node
from src.agents.grade import make_grade_node
from src.agents.guardrail import make_guardrail_node
from src.agents.retrieve import make_retrieve_node
from src.agents.rewrite import make_rewrite_node
from src.agents.state import AgentState
from src.config import settings
from src.services.bm25_index import Bm25Index
from src.services.embeddings import Embedder
from src.services.llm import LLMClient
from src.services.vector_index import VectorIndex

CompiledGraph = CompiledStateGraph[Any, Any, Any, Any]


def _route_after_guardrail(state: AgentState) -> str:
    return "retrieve" if state["is_on_topic"] else "end"


def _route_after_grade(state: AgentState) -> str:
    enough_relevant = len(state["graded"]) >= settings.min_relevant_chunks
    exhausted_rewrites = state["rewrite_count"] >= settings.max_rewrites
    return "generate" if enough_relevant or exhausted_rewrites else "rewrite"


def build_graph(
    bm25_index: Bm25Index,
    vector_index: VectorIndex,
    embedder: Embedder,
    llm_client: LLMClient,
) -> CompiledGraph:
    graph = StateGraph(AgentState)

    graph.add_node("guardrail", make_guardrail_node(llm_client))
    graph.add_node("retrieve", make_retrieve_node(bm25_index, vector_index, embedder))
    graph.add_node("grade", make_grade_node(llm_client))
    graph.add_node("rewrite", make_rewrite_node(llm_client))
    graph.add_node("generate", make_generate_node(llm_client))

    graph.set_entry_point("guardrail")
    graph.add_conditional_edges(
        "guardrail", _route_after_guardrail, {"retrieve": "retrieve", "end": END}
    )
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges(
        "grade", _route_after_grade, {"generate": "generate", "rewrite": "rewrite"}
    )
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("generate", END)

    return graph.compile()


def initial_state(query: str) -> AgentState:
    return AgentState(
        query=query,
        original_query=query,
        is_on_topic=False,
        retrieved=[],
        graded=[],
        rewrite_count=0,
        answer="",
        rejected=False,
        trace=[],
    )
