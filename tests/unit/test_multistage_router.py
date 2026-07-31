from __future__ import annotations

import pytest

from app.rag.routing.capability_router import CapabilityRouter
from app.rag.routing.embedding_classifier import (
    EmbeddingRouteClassifier,
    RoutePrototype,
)
from app.rag.routing.models import (
    Capability,
    RequestIntent,
    RouteAffinity,
    RouteClassification,
    TurnKind,
    TurnResolution,
)
from app.rag.routing.structured_classifier import (
    StructuredRouteClassifier,
    parse_structured_route_output,
)
from app.rag.routing.turn_resolver import TurnResolver


class ControlledEmbeddingProvider:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[list[str]] = []

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [self.vectors[text] for text in texts]


class FailingEmbeddingProvider:
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        del texts
        raise RuntimeError("embedding unavailable")


class FakeLLM:
    def __init__(self, output: str | Exception) -> None:
        self.output = output
        self.calls: list[tuple[str, str]] = []

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


def test_turn_resolver_prioritizes_explicit_continuation() -> None:
    resolution = TurnResolver().resolve(
        "tiếp đi",
        history=[{"role": "assistant", "content": "Phần trước"}],
        has_continuation=True,
    )

    assert resolution.kind == TurnKind.CONTINUATION
    assert resolution.confidence == 1.0
    assert resolution.reason == "explicit_continuation"


def test_turn_resolver_leaves_semantic_follow_up_for_classifier() -> None:
    resolution = TurnResolver().resolve(
        "bạn nói gì thế",
        history=[
            {
                "role": "assistant",
                "content": "Tôi chưa thể tổng hợp câu trả lời.",
                "status": "generation_failed",
                "capability": "rag",
            }
        ],
        has_continuation=False,
    )

    assert resolution.kind == TurnKind.UNRESOLVED
    assert resolution.resolved_query == "bạn nói gì thế"
    assert resolution.reason == "history_requires_semantic_resolution"


def test_turn_resolver_marks_new_message_without_history_independent() -> None:
    resolution = TurnResolver().resolve(
        "quy định làm việc của công ty",
        history=[],
        has_continuation=False,
    )

    assert resolution.kind == TurnKind.INDEPENDENT
    assert resolution.confidence == 1.0


@pytest.mark.asyncio
async def test_embedding_classifier_accepts_clear_route_and_caches_prototypes() -> None:
    provider = ControlledEmbeddingProvider(
        {
            "internal example": [1.0, 0.0],
            "conversation example": [0.0, 1.0],
            "first query": [0.99, 0.01],
            "second query": [0.98, 0.02],
        }
    )
    classifier = EmbeddingRouteClassifier(
        provider,
        prototypes=[
            RoutePrototype(
                name="internal",
                intent=RequestIntent.ASK_INFORMATION,
                affinity=RouteAffinity.INTERNAL_KNOWLEDGE,
                utterances=("internal example",),
                threshold=0.8,
            ),
            RoutePrototype(
                name="conversation",
                intent=RequestIntent.SOCIAL,
                affinity=RouteAffinity.CONVERSATION,
                utterances=("conversation example",),
                threshold=0.8,
            ),
        ],
        minimum_margin=0.1,
    )

    first = await classifier.classify("first query")
    second = await classifier.classify("second query")

    assert first.is_confident
    assert first.intent == RequestIntent.ASK_INFORMATION
    assert first.affinity == RouteAffinity.INTERNAL_KNOWLEDGE
    assert second.is_confident
    assert provider.calls == [
        ["internal example", "conversation example"],
        ["first query"],
        ["second query"],
    ]


@pytest.mark.asyncio
async def test_embedding_classifier_rejects_small_top_route_margin() -> None:
    provider = ControlledEmbeddingProvider(
        {
            "internal example": [1.0, 0.0],
            "conversation example": [0.8, 0.6],
            "ambiguous query": [0.95, 0.31],
        }
    )
    classifier = EmbeddingRouteClassifier(
        provider,
        prototypes=[
            RoutePrototype(
                name="internal",
                intent=RequestIntent.ASK_INFORMATION,
                affinity=RouteAffinity.INTERNAL_KNOWLEDGE,
                utterances=("internal example",),
                threshold=0.8,
            ),
            RoutePrototype(
                name="conversation",
                intent=RequestIntent.SOCIAL,
                affinity=RouteAffinity.CONVERSATION,
                utterances=("conversation example",),
                threshold=0.8,
            ),
        ],
        minimum_margin=0.1,
    )

    decision = await classifier.classify("ambiguous query")

    assert not decision.is_confident
    assert decision.intent == RequestIntent.UNKNOWN
    assert decision.reason == "route_margin_too_small"


@pytest.mark.asyncio
async def test_embedding_classifier_fails_safe_when_provider_is_unavailable() -> None:
    classifier = EmbeddingRouteClassifier(
        FailingEmbeddingProvider(),
        prototypes=[
            RoutePrototype(
                name="internal",
                intent=RequestIntent.ASK_INFORMATION,
                affinity=RouteAffinity.INTERNAL_KNOWLEDGE,
                utterances=("internal example",),
                threshold=0.8,
            )
        ],
    )

    decision = await classifier.classify("a query")

    assert not decision.is_confident
    assert decision.intent == RequestIntent.UNKNOWN
    assert decision.affinity == RouteAffinity.UNKNOWN
    assert decision.reason == "embedding_unavailable"


def test_structured_route_parser_accepts_branch_independent_contract() -> None:
    parsed = parse_structured_route_output(
        """
        {
          "intent": "request_instruction",
          "affinity": "external",
          "subject": "GitHub",
          "context_dependency": "independent",
          "confidence": 0.94,
          "reason": "public platform outside internal knowledge"
        }
        """
    )

    assert parsed is not None
    assert parsed.intent == RequestIntent.REQUEST_INSTRUCTION
    assert parsed.affinity == RouteAffinity.EXTERNAL
    assert parsed.subject == "GitHub"
    assert parsed.is_confident
    assert parsed.classifier == "qwen"
    assert parsed.turn_kind == TurnKind.INDEPENDENT


@pytest.mark.parametrize(
    "output",
    [
        "not json",
        '{"intent":"made_up","affinity":"external"}',
        '{"intent":"social","affinity":"made_up"}',
        '{"intent":"social","affinity":"conversation","confidence":"high"}',
    ],
)
def test_structured_route_parser_rejects_invalid_contract(output: str) -> None:
    assert parse_structured_route_output(output) is None


@pytest.mark.asyncio
async def test_structured_classifier_uses_history_and_fails_safe() -> None:
    history = [
        {
            "role": "assistant",
            "content": "Tôi chưa thể tổng hợp câu trả lời.",
            "status": "generation_failed",
            "capability": "rag",
        }
    ]
    llm = FakeLLM("invalid output")
    classifier = StructuredRouteClassifier(llm)

    decision = await classifier.classify(
        "bạn nói gì thế",
        history,
        TurnResolution(
            kind=TurnKind.UNRESOLVED,
            resolved_query="bạn nói gì thế",
            confidence=0.0,
            reason="history_requires_semantic_resolution",
        ),
    )

    assert decision.intent == RequestIntent.UNKNOWN
    assert decision.reason == "structured_classifier_invalid_output"
    assert "generation_failed" in llm.calls[0][1]
    assert len(llm.calls) == 1


def test_capability_router_maps_supported_branches_without_defaulting_to_rag() -> None:
    router = CapabilityRouter(tools_enabled=False)

    internal = router.decide(
        RouteClassification(
            intent=RequestIntent.REQUEST_INSTRUCTION,
            affinity=RouteAffinity.INTERNAL_KNOWLEDGE,
            confidence=0.9,
            reason="internal",
            is_confident=True,
        )
    )
    external = router.decide(
        RouteClassification(
            intent=RequestIntent.REQUEST_INSTRUCTION,
            affinity=RouteAffinity.EXTERNAL,
            confidence=0.9,
            reason="external",
            is_confident=True,
        )
    )
    repair = router.decide(
        RouteClassification(
            intent=RequestIntent.CONVERSATION_REPAIR,
            affinity=RouteAffinity.CONVERSATION,
            confidence=0.9,
            reason="repair",
            is_confident=True,
        )
    )
    action = router.decide(
        RouteClassification(
            intent=RequestIntent.REQUEST_ACTION,
            affinity=RouteAffinity.TOOL,
            confidence=0.9,
            reason="tool",
            is_confident=True,
        )
    )
    unknown = router.decide(
        RouteClassification(
            intent=RequestIntent.UNKNOWN,
            affinity=RouteAffinity.UNKNOWN,
            confidence=0.0,
            reason="unknown",
        )
    )

    assert internal.capability == Capability.RAG
    assert external.capability == Capability.UNSUPPORTED
    assert repair.capability == Capability.CONVERSATION
    assert action.capability == Capability.UNSUPPORTED
    assert action.reason == "tool_execution_disabled"
    assert unknown.capability == Capability.CLARIFY
