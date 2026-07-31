from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Literal, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.deps import get_rag_pipeline
from app.config import get_settings
from app.domain.models import RetrievalFilters
from app.rag.evaluation import (
    EvaluationCase,
    EvaluationSource,
    classify_first_failure,
    evaluate_response,
    filter_evaluation_cases,
    load_evaluation_cases,
    render_e2e_summary,
    summarize_e2e_results,
)


async def main() -> None:
    args = _parse_args()
    settings = get_settings()
    project_root = Path(__file__).resolve().parents[1]
    dataset_path = project_root / "tests" / "evaluation" / "rag_cases.json"
    cases = filter_evaluation_cases(
        load_evaluation_cases(dataset_path),
        case_id=args.case_id,
        category=args.category,
        limit=args.limit,
    )
    if not cases:
        raise SystemExit("No evaluation cases matched the requested filters.")

    pipeline = get_rag_pipeline()
    details: list[dict[str, Any]] = []
    for case in cases:
        details.append(await _evaluate_case(pipeline, case))

    report = {"summary": summarize_e2e_results(details), "details": details}
    report_dir = settings.data_dir / "evaluation"
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "rag_e2e_report.json"
    markdown_path = report_dir / "rag_e2e_summary.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_e2e_summary(report), encoding="utf-8")

    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")


async def _evaluate_case(pipeline: Any, case: EvaluationCase) -> dict[str, Any]:
    try:
        response = await pipeline.answer(
            case.question,
            _filters_for_case(case),
            case.history or [],
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "id": case.case_id,
            "category": case.category,
            "passed": False,
            "first_failure_stage": "dependency_error",
            "failure_reasons": [type(exc).__name__],
        }

    status = str(response.get("status") or "")
    answer = str(response.get("answer") or "")
    citations = _citation_ids(response)
    selected_sources = _citation_sources(response)
    trace = response.get("trace")
    if not isinstance(trace, dict):
        trace = {}
    response_evaluation = evaluate_response(
        case,
        answer=answer,
        status=status,
        citations=citations,
    )
    classification = classify_first_failure(
        case,
        trace=trace,
        retrieved_sources=selected_sources,
        selected_sources=selected_sources,
        response_evaluation=response_evaluation,
    )
    return {
        "id": case.case_id,
        "category": case.category,
        "question": case.question,
        "passed": classification.first_failure_stage == "none",
        "first_failure_stage": classification.first_failure_stage,
        "failure_reasons": classification.failure_reasons,
        "status": status,
        "expected_status": case.expected_outcome,
        "required_fact_recall": response_evaluation.required_fact_recall,
        "forbidden_fact_violations": response_evaluation.forbidden_fact_violations,
        "citation_valid": response_evaluation.citation_valid,
        "vietnamese_valid": response_evaluation.vietnamese_valid,
        "qwen_calls": _estimate_qwen_calls(trace, response),
        "timing_ms": response.get("timing_ms", {}),
        "trace": trace,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live end-to-end RAG evaluation.")
    parser.add_argument("--case-id", help="Run one case by ID.")
    parser.add_argument("--category", help="Run cases in one category.")
    parser.add_argument("--limit", type=int, help="Run only the first N matching cases.")
    return parser.parse_args()


def _filters_for_case(case: EvaluationCase) -> RetrievalFilters:
    return RetrievalFilters(
        document_ids=case.document_ids or [],
        document_scope=cast(Literal["all", "selected"], case.document_scope),
    )


def _citation_ids(response: dict[str, Any]) -> list[str]:
    citations = response.get("citations")
    if not isinstance(citations, list):
        return []
    return [
        item["citation_id"]
        for item in citations
        if isinstance(item, dict)
        and isinstance(item.get("citation_id"), str)
        and item["citation_id"].strip()
    ]


def _citation_sources(response: dict[str, Any]) -> list[EvaluationSource]:
    citations = response.get("citations")
    if not isinstance(citations, list):
        return []
    sources: list[EvaluationSource] = []
    for item in citations:
        if not isinstance(item, dict):
            continue
        document = item.get("document_name")
        section = item.get("section")
        chunk_id = item.get("chunk_id")
        if isinstance(document, str) and isinstance(section, str):
            sources.append(
                EvaluationSource(
                    document=document,
                    section=section,
                    chunk_id=chunk_id if isinstance(chunk_id, str) else None,
                )
            )
    return sources


def _estimate_qwen_calls(trace: dict[str, Any], response: dict[str, Any]) -> int:
    calls = 0
    if trace.get("llm_router_used") is True:
        calls += 1
    if trace.get("adaptive_rewrite_used") is True:
        calls += 1
    timing = response.get("timing_ms")
    if isinstance(timing, dict) and isinstance(timing.get("llm"), int | float):
        if timing["llm"] > 0:
            calls += 1
    return calls


if __name__ == "__main__":
    asyncio.run(main())
