from __future__ import annotations

import json

from app.providers.llm.base import LLMProvider
from app.rag.prompts import (
    MULTISTAGE_ROUTER_SYSTEM_PROMPT,
    build_multistage_router_prompt,
)
from app.rag.routing.models import (
    RequestIntent,
    RouteAffinity,
    RouteClassification,
    TurnKind,
    TurnResolution,
)

_MIN_CONFIDENCE = 0.65
ROUTE_OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": [value.value for value in RequestIntent],
        },
        "affinity": {
            "type": "string",
            "enum": [value.value for value in RouteAffinity],
        },
        "subject": {"type": "string"},
        "context_dependency": {
            "type": "string",
            "enum": [value.value for value in TurnKind],
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reason": {"type": "string"},
    },
    "required": [
        "intent",
        "affinity",
        "subject",
        "context_dependency",
        "confidence",
        "reason",
    ],
    "additionalProperties": False,
}


class StructuredRouteClassifier:
    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm_provider = llm_provider

    async def classify(
        self,
        question: str,
        history: list[dict[str, str]],
        turn: TurnResolution,
    ) -> RouteClassification:
        try:
            user_prompt = build_multistage_router_prompt(question, history, turn)
            generate_structured = getattr(
                self.llm_provider,
                "generate_structured",
                None,
            )
            if callable(generate_structured):
                output = await generate_structured(
                    MULTISTAGE_ROUTER_SYSTEM_PROMPT,
                    user_prompt,
                    ROUTE_OUTPUT_SCHEMA,
                )
            else:
                output = await self.llm_provider.generate(
                    MULTISTAGE_ROUTER_SYSTEM_PROMPT,
                    user_prompt,
                )
        except Exception:  # noqa: BLE001 - external provider failure is a safe clarify
            return _unknown("structured_classifier_unavailable")
        parsed = parse_structured_route_output(output)
        if parsed is None:
            return _unknown("structured_classifier_invalid_output")
        return parsed


def parse_structured_route_output(output: str) -> RouteClassification | None:
    cleaned = _strip_json_fence(output.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    try:
        intent = RequestIntent(data.get("intent"))
        affinity = RouteAffinity(data.get("affinity"))
        turn_kind = TurnKind(data.get("context_dependency"))
    except (TypeError, ValueError):
        return None
    confidence = data.get("confidence")
    if not isinstance(confidence, int | float) or isinstance(confidence, bool):
        return None
    confidence = float(confidence)
    if not 0.0 <= confidence <= 1.0:
        return None
    reason = data.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return None
    subject = data.get("subject", "")
    if not isinstance(subject, str):
        return None
    return RouteClassification(
        intent=intent,
        affinity=affinity,
        confidence=confidence,
        reason=reason.strip()[:160],
        subject=subject.strip()[:200],
        is_confident=confidence >= _MIN_CONFIDENCE,
        classifier="qwen",
        turn_kind=turn_kind,
    )


def _unknown(reason: str) -> RouteClassification:
    return RouteClassification(
        intent=RequestIntent.UNKNOWN,
        affinity=RouteAffinity.UNKNOWN,
        confidence=0.0,
        reason=reason,
        is_confident=False,
        classifier="qwen",
    )


def _strip_json_fence(value: str) -> str:
    if not value.startswith("```"):
        return value
    lines = value.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
