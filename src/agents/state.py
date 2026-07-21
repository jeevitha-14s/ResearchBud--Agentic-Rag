from typing import TypedDict

from src.models.search import SearchResult


class AgentState(TypedDict):
    query: str
    original_query: str
    is_on_topic: bool
    retrieved: list[SearchResult]
    graded: list[SearchResult]
    rewrite_count: int
    answer: str
    rejected: bool
    trace: list[str]
