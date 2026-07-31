from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALLOWED_OUTCOMES = {"answerable", "partial", "unanswerable", "out_of_scope"}
RETRIEVAL_OUTCOMES = {"answerable", "partial"}


class EvaluationCaseError(ValueError):
    """Raised when a versioned RAG evaluation case is invalid."""


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    category: str
    question: str
    outcome: str
    expected_document: str | None = None
    expected_section: str | None = None

    @property
    def retrieval_applicable(self) -> bool:
        return self.outcome in RETRIEVAL_OUTCOMES


def load_evaluation_cases(path: Path) -> list[EvaluationCase]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationCaseError(f"cannot read evaluation dataset: {exc}") from exc
    if not isinstance(payload, list):
        raise EvaluationCaseError("evaluation dataset must be a JSON array")

    cases: list[EvaluationCase] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise EvaluationCaseError(f"case {index} must be an object")
        case = _parse_case(item, index)
        if case.case_id in seen_ids:
            raise EvaluationCaseError(f"duplicate evaluation case id: {case.case_id}")
        seen_ids.add(case.case_id)
        cases.append(case)
    if not cases:
        raise EvaluationCaseError("evaluation dataset must not be empty")
    return cases


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    retrieval_results = [item for item in results if item.get("retrieval_applicable")]
    hits = sum(item.get("hit") is True for item in retrieval_results)
    reciprocal_sum = sum(
        1 / rank
        for item in retrieval_results
        if isinstance((rank := item.get("rank")), int) and rank > 0
    )
    latencies = [float(item.get("latency_ms", 0.0)) for item in retrieval_results]

    categories: dict[str, dict[str, int]] = {}
    for item in results:
        category = str(item.get("category", "unknown"))
        bucket = categories.setdefault(category, {"count": 0, "hits": 0})
        bucket["count"] += 1
        bucket["hits"] += int(item.get("hit") is True)

    retrieval_count = len(retrieval_results)
    return {
        "count": len(results),
        "retrieval_case_count": retrieval_count,
        "recall_at_k": hits / retrieval_count if retrieval_count else 0.0,
        "mrr": reciprocal_sum / retrieval_count if retrieval_count else 0.0,
        "average_retrieval_latency_ms": (
            sum(latencies) / retrieval_count if retrieval_count else 0.0
        ),
        "categories": categories,
    }


def _parse_case(item: dict[str, Any], index: int) -> EvaluationCase:
    case_id = _required_text(item, "id", index)
    category = _required_text(item, "category", index)
    question = _required_text(item, "question", index)
    expected = item.get("expected")
    if not isinstance(expected, dict):
        raise EvaluationCaseError(f"case {case_id} expected must be an object")
    outcome = _required_text(expected, "outcome", index)
    if outcome not in ALLOWED_OUTCOMES:
        raise EvaluationCaseError(f"case {case_id} has unsupported outcome: {outcome}")

    expected_document = _optional_text(expected, "document_contains")
    expected_section = _optional_text(expected, "section_contains")
    if outcome in RETRIEVAL_OUTCOMES:
        if not expected_document:
            raise EvaluationCaseError(f"case {case_id} requires document_contains")
        if not expected_section:
            raise EvaluationCaseError(f"case {case_id} requires section_contains")

    return EvaluationCase(
        case_id=case_id,
        category=category,
        question=question,
        outcome=outcome,
        expected_document=expected_document,
        expected_section=expected_section,
    )


def _required_text(item: dict[str, Any], field: str, index: int) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise EvaluationCaseError(f"case {index} requires non-empty {field}")
    return value.strip()


def _optional_text(item: dict[str, Any], field: str) -> str | None:
    value = item.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise EvaluationCaseError(f"{field} must be a non-empty string when provided")
    return value.strip()
