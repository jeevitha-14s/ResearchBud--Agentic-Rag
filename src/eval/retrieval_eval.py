from src.eval.dataset import RETRIEVAL_CASES
from src.eval.metrics import precision_at_k, recall_at_k
from src.eval.reports import RetrievalCaseResult, RetrievalReport
from src.services.bm25_index import Bm25Index
from src.services.embeddings import Embedder
from src.services.search import hybrid_search
from src.services.vector_index import VectorIndex


def run_retrieval_eval(
    bm25_index: Bm25Index, vector_index: VectorIndex, embedder: Embedder, top_k: int = 5
) -> RetrievalReport:
    results = []
    for case in RETRIEVAL_CASES:
        retrieved = hybrid_search(bm25_index, vector_index, embedder, case.query, top_k)
        results.append(
            RetrievalCaseResult(
                query=case.query,
                expected_arxiv_id=case.expected_arxiv_id,
                precision=precision_at_k(retrieved, case.expected_arxiv_id, top_k),
                recall=recall_at_k(retrieved, case.expected_arxiv_id, top_k),
            )
        )

    mean_precision = sum(r.precision for r in results) / len(results)
    mean_recall = sum(r.recall for r in results) / len(results)
    return RetrievalReport(results=results, mean_precision=mean_precision, mean_recall=mean_recall)
