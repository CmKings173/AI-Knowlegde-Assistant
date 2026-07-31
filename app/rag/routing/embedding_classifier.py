from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass

from app.providers.embeddings.base import EmbeddingProvider
from app.rag.routing.models import (
    RequestIntent,
    RouteAffinity,
    RouteClassification,
    TurnKind,
)


@dataclass(frozen=True)
class RoutePrototype:
    name: str
    intent: RequestIntent
    affinity: RouteAffinity
    utterances: tuple[str, ...]
    threshold: float
    turn_kind: TurnKind = TurnKind.INDEPENDENT


@dataclass(frozen=True)
class _ScoredRoute:
    prototype: RoutePrototype
    score: float


class EmbeddingRouteClassifier:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        prototypes: list[RoutePrototype],
        *,
        minimum_margin: float = 0.08,
    ) -> None:
        if not prototypes:
            raise ValueError("at least one route prototype is required")
        if any(not prototype.utterances for prototype in prototypes):
            raise ValueError("route prototypes must contain utterances")
        self.embedding_provider = embedding_provider
        self.prototypes = prototypes
        self.minimum_margin = minimum_margin
        self._prototype_vectors: list[list[list[float]]] | None = None
        self._prototype_lock = asyncio.Lock()

    async def classify(self, query: str) -> RouteClassification:
        try:
            await self._ensure_prototype_vectors()
            query_vectors = await self.embedding_provider.embed_texts([query])
            if len(query_vectors) != 1:
                raise ValueError("query embedding count mismatch")
            ranked = self._rank(query_vectors[0])
        except Exception:  # noqa: BLE001 - provider boundaries fail closed
            return _unknown("embedding_unavailable")

        winner = ranked[0]
        runner_up_score = ranked[1].score if len(ranked) > 1 else -1.0
        margin = winner.score - runner_up_score
        if winner.score < winner.prototype.threshold:
            return _unknown(
                "route_score_below_threshold",
                top_score=winner.score,
                margin=margin,
            )
        if len(ranked) > 1 and margin < self.minimum_margin:
            return _unknown(
                "route_margin_too_small",
                top_score=winner.score,
                margin=margin,
            )
        return RouteClassification(
            intent=winner.prototype.intent,
            affinity=winner.prototype.affinity,
            confidence=winner.score,
            reason=f"embedding_route:{winner.prototype.name}",
            is_confident=True,
            top_score=winner.score,
            margin=margin,
            turn_kind=winner.prototype.turn_kind,
        )

    async def _ensure_prototype_vectors(self) -> None:
        if self._prototype_vectors is not None:
            return
        async with self._prototype_lock:
            if self._prototype_vectors is not None:
                return
            utterances = [
                utterance
                for prototype in self.prototypes
                for utterance in prototype.utterances
            ]
            vectors = await self.embedding_provider.embed_texts(utterances)
            if len(vectors) != len(utterances):
                raise ValueError("prototype embedding count mismatch")
            grouped: list[list[list[float]]] = []
            offset = 0
            for prototype in self.prototypes:
                end = offset + len(prototype.utterances)
                grouped.append(vectors[offset:end])
                offset = end
            self._prototype_vectors = grouped

    def _rank(self, query_vector: list[float]) -> list[_ScoredRoute]:
        if self._prototype_vectors is None:
            raise RuntimeError("prototype vectors are not initialized")
        scored = [
            _ScoredRoute(
                prototype=prototype,
                score=max(
                    _cosine_similarity(query_vector, vector)
                    for vector in route_vectors
                ),
            )
            for prototype, route_vectors in zip(
                self.prototypes,
                self._prototype_vectors,
                strict=True,
            )
        ]
        return sorted(scored, key=lambda item: item.score, reverse=True)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("embedding dimensions must match and be non-empty")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (
        left_norm * right_norm
    )


def _unknown(
    reason: str,
    *,
    top_score: float | None = None,
    margin: float | None = None,
) -> RouteClassification:
    return RouteClassification(
        intent=RequestIntent.UNKNOWN,
        affinity=RouteAffinity.UNKNOWN,
        confidence=0.0,
        reason=reason,
        is_confident=False,
        top_score=top_score,
        margin=margin,
    )
