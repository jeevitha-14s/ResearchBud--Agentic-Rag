def reciprocal_rank_fusion(
    rankings: list[list[int]], k: int, top_n: int
) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)

    ranked = sorted(scores.items(), key=lambda pair: -pair[1])
    return ranked[:top_n]
