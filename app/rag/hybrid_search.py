from __future__ import annotations


def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[str, float]]],
    top_k: int,
    k: int = 60,
) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, (chunk_id, _score) in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]

