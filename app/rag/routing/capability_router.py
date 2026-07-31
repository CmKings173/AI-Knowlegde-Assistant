from __future__ import annotations

from app.rag.routing.models import (
    Capability,
    CapabilityDecision,
    RequestIntent,
    RouteAffinity,
    RouteClassification,
)


class CapabilityRouter:
    def __init__(self, *, tools_enabled: bool = False) -> None:
        self.tools_enabled = tools_enabled

    def decide(self, classification: RouteClassification) -> CapabilityDecision:
        if not classification.is_confident:
            return CapabilityDecision(
                capability=Capability.CLARIFY,
                confidence=classification.confidence,
                reason="classification_not_confident",
            )
        if classification.intent in {
            RequestIntent.CONVERSATION_REPAIR,
            RequestIntent.CONTINUE_PREVIOUS,
            RequestIntent.SOCIAL,
        }:
            return CapabilityDecision(
                capability=Capability.CONVERSATION,
                confidence=classification.confidence,
                reason="conversation_intent",
            )
        if classification.intent == RequestIntent.REQUEST_ACTION:
            if self.tools_enabled and classification.affinity == RouteAffinity.TOOL:
                return CapabilityDecision(
                    capability=Capability.TOOL,
                    confidence=classification.confidence,
                    reason="registered_tool_capability",
                )
            return CapabilityDecision(
                capability=Capability.UNSUPPORTED,
                confidence=classification.confidence,
                reason="tool_execution_disabled",
            )
        if (
            classification.intent
            in {
                RequestIntent.ASK_INFORMATION,
                RequestIntent.REQUEST_INSTRUCTION,
                RequestIntent.SUMMARIZE_SECTION,
            }
            and classification.affinity == RouteAffinity.INTERNAL_KNOWLEDGE
        ):
            return CapabilityDecision(
                capability=Capability.RAG,
                confidence=classification.confidence,
                reason="internal_knowledge_capability",
            )
        if classification.affinity == RouteAffinity.CONVERSATION:
            return CapabilityDecision(
                capability=Capability.CONVERSATION,
                confidence=classification.confidence,
                reason="conversation_affinity",
            )
        if classification.affinity in {
            RouteAffinity.EXTERNAL,
            RouteAffinity.TOOL,
        }:
            return CapabilityDecision(
                capability=Capability.UNSUPPORTED,
                confidence=classification.confidence,
                reason="unsupported_capability",
            )
        return CapabilityDecision(
            capability=Capability.CLARIFY,
            confidence=classification.confidence,
            reason="no_capability_match",
        )
