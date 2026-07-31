from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.rag.evaluation import (
    EvaluationCaseError,
    load_evaluation_cases,
    summarize_results,
)


def _write_cases(path: Path, cases: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")


def test_load_evaluation_cases_accepts_versioned_behavior_contract(tmp_path: Path) -> None:
    dataset = tmp_path / "rag_cases.json"
    _write_cases(
        dataset,
        [
            {
                "id": "hr-consequence-001",
                "category": "consequence",
                "question": "Nếu đi làm muộn thì có sao không?",
                "expected": {
                    "outcome": "answerable",
                    "document_contains": "Nội Quy",
                    "section_contains": "Thời gian làm việc",
                },
            },
            {
                "id": "missing-policy-001",
                "category": "unanswerable",
                "question": "Công ty thưởng Tết bao nhiêu?",
                "expected": {"outcome": "unanswerable"},
            },
        ],
    )

    cases = load_evaluation_cases(dataset)

    assert [case.case_id for case in cases] == [
        "hr-consequence-001",
        "missing-policy-001",
    ]
    assert cases[0].expected_section == "Thời gian làm việc"
    assert cases[1].expected_section is None


@pytest.mark.parametrize(
    ("cases", "message"),
    [
        (
            [
                {
                    "id": "missing-question",
                    "category": "fact",
                    "expected": {"outcome": "answerable"},
                }
            ],
            "question",
        ),
        (
            [
                {
                    "id": "duplicate",
                    "category": "fact",
                    "question": "Một",
                    "expected": {"outcome": "answerable"},
                },
                {
                    "id": "duplicate",
                    "category": "fact",
                    "question": "Hai",
                    "expected": {"outcome": "answerable"},
                },
            ],
            "duplicate",
        ),
        (
            [
                {
                    "id": "answerable-without-target",
                    "category": "fact",
                    "question": "Giờ làm việc?",
                    "expected": {
                        "outcome": "answerable",
                        "document_contains": "Nội Quy",
                    },
                }
            ],
            "section_contains",
        ),
    ],
)
def test_load_evaluation_cases_rejects_invalid_contract(
    tmp_path: Path,
    cases: list[dict[str, object]],
    message: str,
) -> None:
    dataset = tmp_path / "rag_cases.json"
    _write_cases(dataset, cases)

    with pytest.raises(EvaluationCaseError, match=message):
        load_evaluation_cases(dataset)


def test_summarize_results_reports_retrieval_and_category_metrics() -> None:
    report = summarize_results(
        [
            {
                "id": "fact-1",
                "category": "fact",
                "outcome": "answerable",
                "retrieval_applicable": True,
                "hit": True,
                "rank": 1,
                "latency_ms": 100.0,
            },
            {
                "id": "fact-2",
                "category": "fact",
                "outcome": "answerable",
                "retrieval_applicable": True,
                "hit": False,
                "rank": None,
                "latency_ms": 300.0,
            },
            {
                "id": "oos-1",
                "category": "out_of_scope",
                "outcome": "out_of_scope",
                "retrieval_applicable": False,
                "hit": None,
                "rank": None,
                "latency_ms": 0.0,
            },
        ]
    )

    assert report["count"] == 3
    assert report["retrieval_case_count"] == 2
    assert report["recall_at_k"] == 0.5
    assert report["mrr"] == 0.5
    assert report["average_retrieval_latency_ms"] == 200.0
    assert report["categories"]["fact"] == {"count": 2, "hits": 1}
    assert report["categories"]["out_of_scope"] == {"count": 1, "hits": 0}


def test_checked_in_dataset_covers_required_behavior_categories() -> None:
    dataset = Path(__file__).resolve().parents[1] / "evaluation" / "rag_cases.json"

    cases = load_evaluation_cases(dataset)
    categories = {case.category for case in cases}

    assert {
        "fact",
        "paraphrase",
        "colloquial",
        "consequence",
        "procedure",
        "broad",
        "partial",
        "unanswerable",
        "out_of_scope",
        "cross_domain",
        "document_scope",
    }.issubset(categories)


def test_checked_in_dataset_covers_end_to_end_regressions() -> None:
    dataset = Path(__file__).resolve().parents[1] / "evaluation" / "rag_cases.json"

    cases = load_evaluation_cases(dataset)
    case_ids = {case.case_id for case in cases}
    categories = {case.category for case in cases}

    assert {"routing", "conversation", "ambiguous", "language"}.issubset(categories)
    assert {
        "routing-github-001",
        "routing-current-time-001",
        "unanswerable-room-count-001",
        "ambiguous-leave-quit-001",
        "conversation-emotion-001",
        "language-vietnamese-001",
    }.issubset(case_ids)
