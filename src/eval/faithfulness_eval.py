from src.agents.generate import NO_CONTEXT_ANSWER
from src.agents.graph import CompiledGraph, run_graph
from src.eval.dataset import FAITHFULNESS_CASES, FaithfulnessCase
from src.eval.judge import score_faithfulness
from src.eval.reports import CategorySummary, FaithfulnessCaseResult, FaithfulnessReport
from src.services.bm25_index import Bm25Index
from src.services.embeddings import Embedder
from src.services.llm import LLMClient
from src.services.naive_rag import naive_rag_answer
from src.services.vector_index import VectorIndex

# Naive RAG has no guardrail/grading — it always "answers" and its
# faithfulness score depends entirely on the LLM voluntarily declining in
# prose when the context is weak. Agentic RAG can structurally refuse
# (guardrail rejection, or grading filtering all chunks) without ever
# calling the generation LLM. Comparing raw mean faithfulness scores across
# pipelines that answered a different number of questions is misleading —
# per-category answer rate is the metric that actually shows what the
# guardrail/grading buys.


def _score_naive(
    case: FaithfulnessCase,
    bm25_index: Bm25Index,
    vector_index: VectorIndex,
    embedder: Embedder,
    llm_client: LLMClient,
) -> tuple[bool, int | None, str | None]:
    result = naive_rag_answer(bm25_index, vector_index, embedder, llm_client, case.query)
    if not result.retrieved:
        return False, None, "no context retrieved"
    context = "\n\n".join(r.text for r in result.retrieved)
    score = score_faithfulness(llm_client, case.query, context, result.answer)
    return True, score, None


def _score_agentic(
    case: FaithfulnessCase, graph: CompiledGraph, llm_client: LLMClient
) -> tuple[bool, int | None, str | None]:
    result = run_graph(graph, case.query)
    if result["rejected"]:
        return False, None, "guardrail rejected"
    if result["answer"] == NO_CONTEXT_ANSWER:
        return False, None, "no relevant context after grading"
    context = "\n\n".join(r.text for r in result["graded"])
    score = score_faithfulness(llm_client, case.query, context, result["answer"])
    return True, score, None


def _rate(flags: list[bool]) -> float:
    return sum(flags) / len(flags) if flags else 0.0


def _mean(scores: list[int]) -> float | None:
    return sum(scores) / len(scores) if scores else None


def _summarize_category(category: str, results: list[FaithfulnessCaseResult]) -> CategorySummary:
    naive_scores = [r.naive_score for r in results if r.naive_score is not None]
    agentic_scores = [r.agentic_score for r in results if r.agentic_score is not None]
    return CategorySummary(
        category=category,
        naive_answer_rate=_rate([r.naive_answered for r in results]),
        naive_mean_faithfulness=_mean(naive_scores),
        agentic_answer_rate=_rate([r.agentic_answered for r in results]),
        agentic_mean_faithfulness=_mean(agentic_scores),
    )


def run_faithfulness_eval(
    graph: CompiledGraph,
    bm25_index: Bm25Index,
    vector_index: VectorIndex,
    embedder: Embedder,
    llm_client: LLMClient,
) -> FaithfulnessReport:
    results = []
    for case in FAITHFULNESS_CASES:
        naive_answered, naive_score, naive_note = _score_naive(
            case, bm25_index, vector_index, embedder, llm_client
        )
        agentic_answered, agentic_score, agentic_note = _score_agentic(case, graph, llm_client)
        results.append(
            FaithfulnessCaseResult(
                query=case.query,
                category=case.category,
                naive_answered=naive_answered,
                naive_score=naive_score,
                naive_note=naive_note,
                agentic_answered=agentic_answered,
                agentic_score=agentic_score,
                agentic_note=agentic_note,
            )
        )

    categories = sorted({r.category for r in results})
    summaries = [
        _summarize_category(category, [r for r in results if r.category == category])
        for category in categories
    ]
    return FaithfulnessReport(results=results, category_summaries=summaries)
