from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TurnKind(StrEnum):
    INDEPENDENT = "independent"
    FOLLOW_UP = "follow_up"
    REPAIR = "repair"
    CONTINUATION = "continuation"
    UNRESOLVED = "unresolved"


class RequestIntent(StrEnum):
    ASK_INFORMATION = "ask_information"
    REQUEST_INSTRUCTION = "request_instruction"
    REQUEST_ACTION = "request_action"
    CONVERSATION_REPAIR = "conversation_repair"
    CONTINUE_PREVIOUS = "continue_previous"
    SOCIAL = "social"
    UNKNOWN = "unknown"


class RouteAffinity(StrEnum):
    INTERNAL_KNOWLEDGE = "internal_knowledge"
    CONVERSATION = "conversation"
    EXTERNAL = "external"
    TOOL = "tool"
    UNKNOWN = "unknown"


class Capability(StrEnum):
    RAG = "rag"
    TOOL = "tool"
    CONVERSATION = "conversation"
    UNSUPPORTED = "unsupported"
    CLARIFY = "clarify"


@dataclass(frozen=True)
class TurnResolution:
    kind: TurnKind
    resolved_query: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class RouteClassification:
    intent: RequestIntent
    affinity: RouteAffinity
    confidence: float
    reason: str
    subject: str = ""
    is_confident: bool = False
    top_score: float | None = None
    margin: float | None = None
    classifier: str = "embedding"
    turn_kind: TurnKind = TurnKind.UNRESOLVED


@dataclass(frozen=True)
class CapabilityDecision:
    capability: Capability
    confidence: float
    reason: str
