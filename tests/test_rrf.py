from src.services.rrf import reciprocal_rank_fusion


def test_single_ranking_preserves_order() -> None:
    result = reciprocal_rank_fusion([[10, 20, 30]], k=60, top_n=3)
    ids = [item_id for item_id, _ in result]
    assert ids == [10, 20, 30]


def test_item_ranked_first_in_both_lists_wins() -> None:
    result = reciprocal_rank_fusion([[1, 2, 3], [1, 3, 2]], k=60, top_n=3)
    assert result[0][0] == 1


def test_item_present_in_both_lists_outranks_single_list_item() -> None:
    # id=5 ranked #2 in both lists; id=99 ranked #1 in only one list.
    result = reciprocal_rank_fusion([[99, 5], [7, 5]], k=60, top_n=3)
    ids = [item_id for item_id, _ in result]
    assert ids.index(5) < ids.index(99)


def test_fused_score_matches_rrf_formula() -> None:
    result = reciprocal_rank_fusion([[1]], k=60, top_n=1)
    assert result[0] == (1, 1.0 / 61)


def test_respects_top_n_limit() -> None:
    result = reciprocal_rank_fusion([[1, 2, 3, 4, 5]], k=60, top_n=2)
    assert len(result) == 2


def test_disjoint_rankings_all_appear() -> None:
    result = reciprocal_rank_fusion([[1, 2], [3, 4]], k=60, top_n=10)
    ids = {item_id for item_id, _ in result}
    assert ids == {1, 2, 3, 4}
