from src.eval.metrics import accuracy, precision_at_k, recall_at_k
from src.models.search import SearchResult


def _result(arxiv_id: str) -> SearchResult:
    return SearchResult(
        chunk_id=1, paper_id=1, arxiv_id=arxiv_id, title="Paper", text="text", score=1.0
    )


def test_precision_at_k_all_relevant() -> None:
    results = [_result("A"), _result("A"), _result("A")]
    assert precision_at_k(results, "A", k=3) == 1.0


def test_precision_at_k_partial_relevant() -> None:
    results = [_result("A"), _result("B"), _result("A")]
    assert precision_at_k(results, "A", k=3) == 2 / 3


def test_precision_at_k_none_relevant() -> None:
    results = [_result("B"), _result("C")]
    assert precision_at_k(results, "A", k=2) == 0.0


def test_precision_at_k_empty_results() -> None:
    assert precision_at_k([], "A", k=5) == 0.0


def test_precision_at_k_respects_k_smaller_than_results() -> None:
    results = [_result("A"), _result("B"), _result("B")]
    assert precision_at_k(results, "A", k=1) == 1.0


def test_recall_at_k_hit() -> None:
    results = [_result("B"), _result("A"), _result("C")]
    assert recall_at_k(results, "A", k=3) == 1.0


def test_recall_at_k_miss() -> None:
    results = [_result("B"), _result("C")]
    assert recall_at_k(results, "A", k=2) == 0.0


def test_recall_at_k_hit_outside_k_window_is_a_miss() -> None:
    results = [_result("B"), _result("A")]
    assert recall_at_k(results, "A", k=1) == 0.0


def test_accuracy_all_correct() -> None:
    assert accuracy([True, False, True], [True, False, True]) == 1.0


def test_accuracy_partial() -> None:
    assert accuracy([True, True, False], [True, False, False]) == 2 / 3


def test_accuracy_empty() -> None:
    assert accuracy([], []) == 0.0
