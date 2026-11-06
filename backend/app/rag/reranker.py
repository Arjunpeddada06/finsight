"""Result fusion / reranking. Reciprocal Rank Fusion needs no model and works well for vector + keyword lists."""
from collections.abc import Hashable, Sequence


def reciprocal_rank_fusion(rankings: Sequence[Sequence[Hashable]], k: int = 60) -> dict[Hashable, float]:
    """Each ranking is an ordered list of ids (best first). Returns id -> fused score (higher is better)."""
    scores: dict[Hashable, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return scores
