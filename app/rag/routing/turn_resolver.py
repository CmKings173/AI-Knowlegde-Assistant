from __future__ import annotations

from app.rag.routing.models import TurnKind, TurnResolution


class TurnResolver:
    """Resolve protocol-level turn state without making semantic guesses."""

    def resolve(
        self,
        question: str,
        history: list[dict[str, str]],
        *,
        has_continuation: bool,
    ) -> TurnResolution:
        if has_continuation:
            return TurnResolution(
                kind=TurnKind.CONTINUATION,
                resolved_query=question,
                confidence=1.0,
                reason="explicit_continuation",
            )
        if not history:
            return TurnResolution(
                kind=TurnKind.INDEPENDENT,
                resolved_query=question,
                confidence=1.0,
                reason="no_history",
            )
        return TurnResolution(
            kind=TurnKind.UNRESOLVED,
            resolved_query=question,
            confidence=0.0,
            reason="history_requires_semantic_resolution",
        )

