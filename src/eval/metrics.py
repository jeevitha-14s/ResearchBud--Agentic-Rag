from src.models.search import SearchResult


def precision_at_k(results: list[SearchResult], expected_arxiv_id: str, k: int) -> float:
    top_k = results[:k]
    if not top_k:
        return 0.0
    relevant = sum(1 for r in top_k if r.arxiv_id == expected_arxiv_id)
    return relevant / len(top_k)


def recall_at_k(results: list[SearchResult], expected_arxiv_id: str, k: int) -> float:
    top_k = results[:k]
    return 1.0 if any(r.arxiv_id == expected_arxiv_id for r in top_k) else 0.0


def accuracy(predictions: list[bool], expected: list[bool]) -> float:
    if not predictions:
        return 0.0
    correct = sum(1 for p, e in zip(predictions, expected, strict=True) if p == e)
    return correct / len(predictions)
