import logging
import sys

from src.agents.graph import build_graph
from src.config import settings
from src.db.connection import get_connection
from src.db.repository import PaperRepository
from src.eval.dataset import EXPECTED_ARXIV_IDS
from src.eval.faithfulness_eval import run_faithfulness_eval
from src.eval.guardrail_eval import run_guardrail_eval
from src.eval.reports import FaithfulnessReport, GuardrailReport, RetrievalReport
from src.eval.retrieval_eval import run_retrieval_eval
from src.services.bm25_index import Bm25Index
from src.services.embeddings import EmbeddingModel
from src.services.llm import get_llm_client
from src.services.vector_index import VectorIndex

logging.basicConfig(level=logging.WARNING)


def _check_corpus() -> None:
    with get_connection() as conn:
        papers = PaperRepository(conn)
        missing = [aid for aid in EXPECTED_ARXIV_IDS if papers.get_by_arxiv_id(aid) is None]
    if missing:
        print(
            f"Eval corpus incomplete — missing arXiv IDs: {missing}\n"
            f"Ingest them first, e.g.:\n"
            f'  uv run python -m src.ingest --query "id:{" OR id:".join(missing)}" '
            f"--max-results {len(missing)}",
            file=sys.stderr,
        )
        raise SystemExit(1)


def _print_retrieval_report(report: RetrievalReport) -> None:
    print("\n=== Retrieval Eval (hybrid search) ===")
    for r in report.results:
        status = "OK" if r.recall == 1.0 else "MISS"
        print(f"  [{status}] {r.query[:65]:<65} precision={r.precision:.2f} recall={r.recall:.2f}")
    print(f"  Mean precision: {report.mean_precision:.2f}  Mean recall: {report.mean_recall:.2f}")


def _print_guardrail_report(report: GuardrailReport) -> None:
    print("\n=== Guardrail Accuracy Eval ===")
    for r in report.results:
        status = "OK" if r.predicted == r.expected else "WRONG"
        print(f"  [{status}] {r.query[:65]:<65} expected={r.expected} got={r.predicted}")
    print(f"  Accuracy: {report.accuracy:.2f}")


def _print_faithfulness_report(report: FaithfulnessReport) -> None:
    print("\n=== Faithfulness: Naive RAG vs. Agentic RAG ===")
    print(
        "Naive RAG always answers; its faithfulness depends on the LLM "
        "voluntarily declining in prose. Agentic RAG can structurally refuse "
        "(guardrail rejection or grading filtering all chunks) without ever "
        "calling the generation LLM — that's a guarantee, not a hope. "
        "Answer rate below is the metric that shows this; mean faithfulness "
        "is only comparable within the same category."
    )
    for r in report.results:
        naive_str = (
            f"{r.naive_score}/5" if r.naive_score is not None else f"declined ({r.naive_note})"
        )
        agentic_str = (
            f"{r.agentic_score}/5"
            if r.agentic_score is not None
            else f"declined ({r.agentic_note})"
        )
        print(f"\n  [{r.category}] {r.query}")
        print(f"    naive:    {naive_str}")
        print(f"    agentic:  {agentic_str}")

    print("\n  Per-category summary:")
    for s in report.category_summaries:
        naive_mean = (
            f"{s.naive_mean_faithfulness:.2f}/5" if s.naive_mean_faithfulness is not None else "n/a"
        )
        agentic_mean = (
            f"{s.agentic_mean_faithfulness:.2f}/5"
            if s.agentic_mean_faithfulness is not None
            else "n/a"
        )
        print(f"    {s.category}:")
        print(
            f"      naive:    answer_rate={s.naive_answer_rate:.0%}  mean_faithfulness={naive_mean}"
        )
        print(
            f"      agentic:  answer_rate={s.agentic_answer_rate:.0%}  "
            f"mean_faithfulness={agentic_mean}"
        )


def main() -> None:
    _check_corpus()

    bm25_index = Bm25Index.load(settings.bm25_index_path)
    vector_index = VectorIndex()
    embedder = EmbeddingModel()
    llm_client = get_llm_client()
    graph = build_graph(bm25_index, vector_index, embedder, llm_client)

    _print_retrieval_report(run_retrieval_eval(bm25_index, vector_index, embedder))
    _print_guardrail_report(run_guardrail_eval(llm_client))
    _print_faithfulness_report(
        run_faithfulness_eval(graph, bm25_index, vector_index, embedder, llm_client)
    )


if __name__ == "__main__":
    main()
