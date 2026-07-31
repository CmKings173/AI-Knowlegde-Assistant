from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.rag.guards.language_guard import VietnameseLanguageGuard

ALLOWED_OUTCOMES = {"answerable", "partial", "unanswerable", "out_of_scope"}
RETRIEVAL_OUTCOMES = {"answerable", "partial"}
ALLOWED_DOCUMENT_SCOPES = {"all", "selected"}
ALLOWED_HISTORY_ROLES = {"user", "assistant"}
DEFAULT_STATUS_BY_OUTCOME = {
    "answerable": "answered",
    "partial": "partial",
    "unanswerable": "insufficient_context",
    "out_of_scope": "out_of_scope",
}
_SOURCE_PATTERN = re.compile(r"\bSOURCE_\d+\b")


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
    history: list[dict[str, str]] | None = None
    document_scope: str = "all"
    document_ids: list[str] | None = None
    expected_capability: str | None = None
    expected_intent: str | None = None
    expected_outcome: str | None = None
    expected_documents: list[str] | None = None
    expected_sections: list[str] | None = None
    required_fact_groups: list[list[str]] | None = None
    forbidden_fact_groups: list[list[str]] | None = None
    citation_required: bool | None = None

    @property
    def retrieval_applicable(self) -> bool:
        return self.outcome in RETRIEVAL_OUTCOMES


@dataclass(frozen=True)
class ResponseEvaluation:
    passed: bool
    failure_reasons: list[str]
    required_fact_recall: float | None = None
    forbidden_fact_violations: list[str] | None = None
    citation_valid: bool | None = None
    vietnamese_valid: bool | None = None
    outcome_matched: bool | None = None


@dataclass(frozen=True)
class EvaluationSource:
    document: str
    section: str
    chunk_id: str | None = None


@dataclass(frozen=True)
class FailureClassification:
    first_failure_stage: str
    failure_reasons: list[str]


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


def filter_evaluation_cases(
    cases: list[EvaluationCase],
    *,
    case_id: str | None = None,
    category: str | None = None,
    limit: int | None = None,
) -> list[EvaluationCase]:
    selected = cases
    if case_id:
        selected = [case for case in selected if case.case_id == case_id]
    if category:
        selected = [case for case in selected if case.category == category]
    if limit is not None:
        selected = selected[:limit]
    return selected


def summarize_e2e_results(details: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(details)
    passed = sum(item.get("passed") is True for item in details)
    failure_stages: dict[str, int] = {}
    citation_values: list[bool] = []
    vietnamese_values: list[bool] = []
    required_fact_recalls: list[float] = []
    qwen_calls: list[float] = []
    total_latencies: list[float] = []
    retrieval_latencies: list[float] = []
    llm_latencies: list[float] = []

    for item in details:
        stage = str(item.get("first_failure_stage") or "none")
        failure_stages[stage] = failure_stages.get(stage, 0) + 1
        if isinstance(item.get("citation_valid"), bool):
            citation_values.append(bool(item["citation_valid"]))
        if isinstance(item.get("vietnamese_valid"), bool):
            vietnamese_values.append(bool(item["vietnamese_valid"]))
        if isinstance(item.get("required_fact_recall"), int | float):
            required_fact_recalls.append(float(item["required_fact_recall"]))
        if isinstance(item.get("qwen_calls"), int | float):
            qwen_calls.append(float(item["qwen_calls"]))
        timing = item.get("timing_ms")
        if isinstance(timing, dict):
            _append_number(timing.get("total"), total_latencies)
            _append_number(timing.get("retrieval"), retrieval_latencies)
            _append_number(timing.get("llm"), llm_latencies)

    return {
        "count": count,
        "passed": passed,
        "failed": count - passed,
        "pass_rate": passed / count if count else 0.0,
        "failure_stages": failure_stages,
        "average_required_fact_recall": _average(required_fact_recalls),
        "citation_valid_rate": _true_rate(citation_values),
        "vietnamese_valid_rate": _true_rate(vietnamese_values),
        "average_qwen_calls": _average(qwen_calls),
        "latency_ms": {
            "total": _latency_summary(total_latencies),
            "retrieval": _latency_summary(retrieval_latencies),
            "llm": _latency_summary(llm_latencies),
        },
    }


def render_e2e_summary(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    details = report.get("details", [])
    lines = [
        "# RAG End-to-End Evaluation Summary",
        "",
        f"- Cases: {summary.get('count', 0)}",
        f"- Passed: {summary.get('passed', 0)}",
        f"- Pass rate: {float(summary.get('pass_rate', 0.0)):.2%}",
        f"- Failure stages: {json.dumps(summary.get('failure_stages', {}), sort_keys=True)}",
        "",
        "## Failed Cases",
        "",
    ]
    failed = [item for item in details if item.get("passed") is not True]
    if not failed:
        lines.append("None.")
    for item in failed:
        reasons = ", ".join(str(reason) for reason in item.get("failure_reasons", []))
        lines.append(
            f"- `{item.get('id')}`: {item.get('first_failure_stage')} - {reasons}"
        )
    lines.append("")
    return "\n".join(lines)


def classify_first_failure(
    case: EvaluationCase,
    *,
    trace: dict[str, Any],
    retrieved_sources: list[EvaluationSource],
    selected_sources: list[EvaluationSource],
    response_evaluation: ResponseEvaluation | None,
) -> FailureClassification:
    expected_capability = case.expected_capability
    if expected_capability is None and case.retrieval_applicable:
        expected_capability = "rag"
    actual_capability = _optional_string(trace.get("capability"))
    if expected_capability and actual_capability != expected_capability:
        return FailureClassification(
            first_failure_stage="router",
            failure_reasons=[f"capability_mismatch:{actual_capability or 'missing'}"],
        )

    expected_sources = _expected_sources(case)
    if expected_sources:
        if not _sources_contain_expected(retrieved_sources, expected_sources):
            return FailureClassification(
                first_failure_stage="retrieval",
                failure_reasons=["expected_source_missing_from_retrieval"],
            )
        if not _sources_contain_expected(selected_sources, expected_sources):
            return FailureClassification(
                first_failure_stage="evidence",
                failure_reasons=["expected_source_dropped_from_context"],
            )

    validation_reasons = _validation_failure_reasons(trace, response_evaluation)
    if validation_reasons:
        return FailureClassification("validation", validation_reasons)

    if response_evaluation and not response_evaluation.passed:
        return FailureClassification(
            "generation",
            response_evaluation.failure_reasons,
        )

    return FailureClassification("none", [])


def evaluate_response(
    case: EvaluationCase,
    *,
    answer: str,
    status: str,
    citations: list[str] | None = None,
) -> ResponseEvaluation:
    failure_reasons: list[str] = []
    normalized_answer = _normalize_text(answer)
    expected_status = case.expected_outcome or DEFAULT_STATUS_BY_OUTCOME.get(case.outcome)
    outcome_matched = expected_status is None or status == expected_status
    if not outcome_matched:
        failure_reasons.append(f"unexpected_status:{status}")

    required_recall = _required_fact_recall(case, normalized_answer, failure_reasons)
    forbidden_violations = _forbidden_fact_violations(case, normalized_answer)
    failure_reasons.extend(forbidden_violations)

    citation_valid = _citation_valid(case, answer, citations)
    if citation_valid is False:
        failure_reasons.append("missing_citation")

    language_decision = VietnameseLanguageGuard().validate_complete(answer)
    vietnamese_valid = language_decision.accepted
    if not vietnamese_valid:
        failure_reasons.append(f"invalid_language:{language_decision.reason}")

    return ResponseEvaluation(
        passed=not failure_reasons,
        failure_reasons=failure_reasons,
        required_fact_recall=required_recall,
        forbidden_fact_violations=forbidden_violations,
        citation_valid=citation_valid,
        vietnamese_valid=vietnamese_valid,
        outcome_matched=outcome_matched,
    )


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
    history = _optional_history(item, "history", case_id)
    document_scope = _optional_choice(
        item,
        "document_scope",
        ALLOWED_DOCUMENT_SCOPES,
        case_id,
        default="all",
    )
    document_ids = _optional_text_list(item, "document_ids", case_id)
    expected = item.get("expected")
    if not isinstance(expected, dict):
        raise EvaluationCaseError(f"case {case_id} expected must be an object")
    outcome = _required_text(expected, "outcome", index)
    if outcome not in ALLOWED_OUTCOMES:
        raise EvaluationCaseError(f"case {case_id} has unsupported outcome: {outcome}")

    expected_document = _optional_text(expected, "document_contains")
    expected_section = _optional_text(expected, "section_contains")
    expected_capability = _optional_text(expected, "expected_capability")
    expected_intent = _optional_text(expected, "expected_intent")
    expected_outcome = _optional_text(expected, "expected_outcome")
    expected_documents = _optional_text_list(expected, "expected_documents", case_id)
    expected_sections = _optional_text_list(expected, "expected_sections", case_id)
    required_fact_groups = _optional_fact_groups(
        expected,
        "required_fact_groups",
        case_id,
    )
    forbidden_fact_groups = _optional_fact_groups(
        expected,
        "forbidden_fact_groups",
        case_id,
    )
    citation_required = _optional_bool(expected, "citation_required", case_id)
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
        history=history,
        document_scope=document_scope,
        document_ids=document_ids,
        expected_capability=expected_capability,
        expected_intent=expected_intent,
        expected_outcome=expected_outcome,
        expected_documents=expected_documents,
        expected_sections=expected_sections,
        required_fact_groups=required_fact_groups,
        forbidden_fact_groups=forbidden_fact_groups,
        citation_required=citation_required,
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


def _optional_choice(
    item: dict[str, Any],
    field: str,
    allowed: set[str],
    case_id: str,
    *,
    default: str,
) -> str:
    value = item.get(field, default)
    if not isinstance(value, str) or value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise EvaluationCaseError(f"case {case_id} {field} must be one of: {choices}")
    return value


def _optional_bool(item: dict[str, Any], field: str, case_id: str) -> bool | None:
    value = item.get(field)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise EvaluationCaseError(f"case {case_id} {field} must be a boolean")
    return value


def _optional_text_list(
    item: dict[str, Any],
    field: str,
    case_id: str,
) -> list[str] | None:
    value = item.get(field)
    if value is None:
        return None
    if not isinstance(value, list):
        raise EvaluationCaseError(f"case {case_id} {field} must be a list")
    items: list[str] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, str) or not entry.strip():
            raise EvaluationCaseError(
                f"case {case_id} {field}[{index}] must be a non-empty string"
            )
        items.append(entry.strip())
    return items


def _optional_fact_groups(
    item: dict[str, Any],
    field: str,
    case_id: str,
) -> list[list[str]] | None:
    value = item.get(field)
    if value is None:
        return None
    if not isinstance(value, list):
        raise EvaluationCaseError(f"case {case_id} {field} must be a list of lists")
    groups: list[list[str]] = []
    for group_index, group in enumerate(value):
        if not isinstance(group, list) or not group:
            raise EvaluationCaseError(
                f"case {case_id} {field}[{group_index}] must be a non-empty list"
            )
        parsed_group: list[str] = []
        for item_index, entry in enumerate(group):
            if not isinstance(entry, str) or not entry.strip():
                raise EvaluationCaseError(
                    f"case {case_id} {field}[{group_index}][{item_index}] "
                    "must be a non-empty string"
                )
            parsed_group.append(entry.strip())
        groups.append(parsed_group)
    return groups


def _optional_history(
    item: dict[str, Any],
    field: str,
    case_id: str,
) -> list[dict[str, str]] | None:
    value = item.get(field)
    if value is None:
        return None
    if not isinstance(value, list):
        raise EvaluationCaseError(f"case {case_id} {field} must be a list")
    history: list[dict[str, str]] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise EvaluationCaseError(f"case {case_id} {field}[{index}] must be an object")
        role = entry.get("role")
        content = entry.get("content")
        if role not in ALLOWED_HISTORY_ROLES:
            raise EvaluationCaseError(
                f"case {case_id} {field}[{index}].role must be user or assistant"
            )
        if not isinstance(content, str) or not content.strip():
            raise EvaluationCaseError(
                f"case {case_id} {field}[{index}].content must be non-empty"
            )
        parsed = {"role": role, "content": content.strip()}
        for optional_field in ("status", "capability", "subject", "turn_kind"):
            optional_value = entry.get(optional_field)
            if optional_value is None:
                continue
            if not isinstance(optional_value, str) or not optional_value.strip():
                raise EvaluationCaseError(
                    f"case {case_id} {field}[{index}].{optional_field} "
                    "must be a non-empty string"
                )
            parsed[optional_field] = optional_value.strip()
        history.append(parsed)
    return history


def _required_fact_recall(
    case: EvaluationCase,
    normalized_answer: str,
    failure_reasons: list[str],
) -> float | None:
    if not case.required_fact_groups:
        return None
    hits = 0
    for index, group in enumerate(case.required_fact_groups):
        if any(_normalize_text(variant) in normalized_answer for variant in group):
            hits += 1
            continue
        failure_reasons.append(f"missing_required_fact_group:{index}")
    return hits / len(case.required_fact_groups)


def _forbidden_fact_violations(
    case: EvaluationCase,
    normalized_answer: str,
) -> list[str]:
    if not case.forbidden_fact_groups:
        return []
    violations: list[str] = []
    for index, group in enumerate(case.forbidden_fact_groups):
        if all(_normalize_text(variant) in normalized_answer for variant in group):
            violations.append(f"forbidden_fact_group:{index}")
    return violations


def _citation_valid(
    case: EvaluationCase,
    answer: str,
    citations: list[str] | None,
) -> bool | None:
    if case.citation_required is not True:
        return None
    citation_ids = [item for item in (citations or []) if item.strip()]
    return bool(citation_ids or _SOURCE_PATTERN.search(answer))


def _normalize_text(value: str) -> str:
    value = value.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )
    return " ".join(without_marks.casefold().split())


def _append_number(value: object, target: list[float]) -> None:
    if isinstance(value, int | float):
        target.append(float(value))


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _true_rate(values: list[bool]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _latency_summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"average": None, "p50": None, "p95": None, "max": None}
    sorted_values = sorted(values)
    return {
        "average": sum(sorted_values) / len(sorted_values),
        "p50": _percentile(sorted_values, 0.5),
        "p95": _percentile(sorted_values, 0.95),
        "max": sorted_values[-1],
    }


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * percentile
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = position - lower_index
    return sorted_values[lower_index] + (
        sorted_values[upper_index] - sorted_values[lower_index]
    ) * fraction


def _optional_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _expected_sources(case: EvaluationCase) -> list[EvaluationSource]:
    documents = case.expected_documents
    sections = case.expected_sections
    if documents is None and case.expected_document:
        documents = [case.expected_document]
    if sections is None and case.expected_section:
        sections = [case.expected_section]
    if not documents or not sections:
        return []
    return [
        EvaluationSource(document=document, section=section)
        for document in documents
        for section in sections
    ]


def _sources_contain_expected(
    actual_sources: list[EvaluationSource],
    expected_sources: list[EvaluationSource],
) -> bool:
    for expected in expected_sources:
        expected_document = _normalize_text(expected.document)
        expected_section = _normalize_text(expected.section)
        for actual in actual_sources:
            actual_document = _normalize_text(actual.document)
            actual_section = _normalize_text(actual.section)
            if expected_document in actual_document and expected_section in actual_section:
                return True
    return False


def _validation_failure_reasons(
    trace: dict[str, Any],
    response_evaluation: ResponseEvaluation | None,
) -> list[str]:
    parse_error = _optional_string(trace.get("parse_error"))
    if parse_error:
        return [f"parse_error:{parse_error}"]
    literal_validation_error = _optional_string(trace.get("literal_validation_error"))
    if literal_validation_error:
        return [f"literal_validation_error:{literal_validation_error}"]
    if response_evaluation is None:
        return []
    return [
        reason
        for reason in response_evaluation.failure_reasons
        if reason == "missing_citation" or reason.startswith("invalid_language:")
    ]
