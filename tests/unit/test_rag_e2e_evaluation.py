from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.rag.evaluation import (
    EvaluationCase,
    EvaluationCaseError,
    EvaluationSource,
    ResponseEvaluation,
    classify_first_failure,
    evaluate_response,
    load_evaluation_cases,
)


def _write_cases(path: Path, cases: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")


def test_load_evaluation_cases_accepts_optional_end_to_end_contract(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "rag_cases.json"
    _write_cases(
        dataset,
        [
            {
                "id": "routing-github-001",
                "category": "routing",
                "question": "huong dan toi dung github di",
                "history": [
                    {
                        "role": "assistant",
                        "content": "Minh co the ho tro tra cuu tai lieu noi bo.",
                        "status": "conversational",
                        "capability": "conversation",
                        "subject": "greeting",
                        "turn_kind": "independent",
                    }
                ],
                "document_scope": "selected",
                "document_ids": ["doc-a", "doc-b"],
                "expected": {
                    "outcome": "out_of_scope",
                    "expected_capability": "unsupported",
                    "expected_intent": "request_instruction",
                    "expected_outcome": "out_of_scope",
                    "expected_documents": ["Noi Quy"],
                    "expected_sections": ["Dieu 1", "Thoi gian"],
                    "required_fact_groups": [["ngoai pham vi", "khong thuoc"]],
                    "forbidden_fact_groups": [["SOURCE_1"], ["hang hoa", "tai san"]],
                    "citation_required": False,
                },
            }
        ],
    )

    [case] = load_evaluation_cases(dataset)

    assert case.case_id == "routing-github-001"
    assert case.history[0]["role"] == "assistant"
    assert case.document_scope == "selected"
    assert case.document_ids == ["doc-a", "doc-b"]
    assert case.expected_capability == "unsupported"
    assert case.expected_intent == "request_instruction"
    assert case.expected_outcome == "out_of_scope"
    assert case.expected_documents == ["Noi Quy"]
    assert case.expected_sections == ["Dieu 1", "Thoi gian"]
    assert case.required_fact_groups == [["ngoai pham vi", "khong thuoc"]]
    assert case.forbidden_fact_groups == [["SOURCE_1"], ["hang hoa", "tai san"]]
    assert case.citation_required is False


@pytest.mark.parametrize(
    ("expected_patch", "message"),
    [
        ({"expected_documents": "Noi Quy"}, "expected_documents"),
        ({"required_fact_groups": ["ngoai pham vi"]}, "required_fact_groups"),
        ({"forbidden_fact_groups": [[""]]}, "forbidden_fact_groups"),
        ({"citation_required": "yes"}, "citation_required"),
    ],
)
def test_load_evaluation_cases_rejects_invalid_end_to_end_fields(
    tmp_path: Path,
    expected_patch: dict[str, object],
    message: str,
) -> None:
    dataset = tmp_path / "rag_cases.json"
    expected: dict[str, object] = {"outcome": "out_of_scope"}
    expected.update(expected_patch)
    _write_cases(
        dataset,
        [
            {
                "id": "bad-e2e-field",
                "category": "routing",
                "question": "github",
                "expected": expected,
            }
        ],
    )

    with pytest.raises(EvaluationCaseError, match=message):
        load_evaluation_cases(dataset)


@pytest.mark.parametrize(
    ("case_patch", "message"),
    [
        ({"history": [{"role": "system", "content": "x"}]}, "history"),
        ({"document_scope": "everything"}, "document_scope"),
        ({"document_ids": ["doc-a", ""]}, "document_ids"),
    ],
)
def test_load_evaluation_cases_rejects_invalid_execution_fields(
    tmp_path: Path,
    case_patch: dict[str, object],
    message: str,
) -> None:
    dataset = tmp_path / "rag_cases.json"
    item: dict[str, object] = {
        "id": "bad-execution-field",
        "category": "routing",
        "question": "github",
        "expected": {"outcome": "out_of_scope"},
    }
    item.update(case_patch)
    _write_cases(dataset, [item])

    with pytest.raises(EvaluationCaseError, match=message):
        load_evaluation_cases(dataset)


def test_evaluate_response_scores_required_facts_with_any_of_matching() -> None:
    case = EvaluationCase(
        case_id="late-policy",
        category="fact",
        question="di muon co sao khong",
        outcome="answerable",
        required_fact_groups=[
            ["di muon", "den muon"],
            ["bao cho cap tren", "thong bao cho quan ly"],
        ],
    )

    result = evaluate_response(
        case,
        answer="Nếu đến muộn, nhân viên cần thông báo cho quản lý. [SOURCE_1]",
        status="answered",
        citations=["SOURCE_1"],
    )

    assert result.passed
    assert result.required_fact_recall == 1.0
    assert result.failure_reasons == []


def test_evaluate_response_reports_missing_required_facts() -> None:
    case = EvaluationCase(
        case_id="late-policy",
        category="fact",
        question="di muon co sao khong",
        outcome="answerable",
        required_fact_groups=[
            ["di muon", "den muon"],
            ["bao cho cap tren", "thong bao cho quan ly"],
        ],
    )

    result = evaluate_response(
        case,
        answer="Nhan vien can tuan thu noi quy cong ty. [SOURCE_1]",
        status="answered",
        citations=["SOURCE_1"],
    )

    assert not result.passed
    assert result.required_fact_recall == 0.0
    assert "missing_required_fact_group:0" in result.failure_reasons
    assert "missing_required_fact_group:1" in result.failure_reasons


def test_evaluate_response_reports_forbidden_facts_and_missing_citation() -> None:
    case = EvaluationCase(
        case_id="routing-github",
        category="routing",
        question="github",
        outcome="out_of_scope",
        forbidden_fact_groups=[["hang hoa", "tai san"]],
        citation_required=True,
    )

    result = evaluate_response(
        case,
        answer="Cau hoi nay lien quan den hang hoa tai san.",
        status="out_of_scope",
        citations=[],
    )

    assert not result.passed
    assert result.forbidden_fact_violations == ["forbidden_fact_group:0"]
    assert "missing_citation" in result.failure_reasons


def test_evaluate_response_reports_status_and_language_failures() -> None:
    case = EvaluationCase(
        case_id="language-regression",
        category="conversation",
        question="toi buon qua",
        outcome="out_of_scope",
        expected_outcome="conversational",
    )

    result = evaluate_response(
        case,
        answer="请联系管理员获取帮助。",
        status="out_of_scope",
        citations=[],
    )

    assert not result.passed
    assert "unexpected_status:out_of_scope" in result.failure_reasons
    assert "invalid_language:disallowed_cjk" in result.failure_reasons


def test_classify_first_failure_reports_router_stage_first() -> None:
    case = EvaluationCase(
        case_id="github",
        category="routing",
        question="github",
        outcome="out_of_scope",
        expected_capability="unsupported",
    )

    result = classify_first_failure(
        case,
        trace={"capability": "rag"},
        retrieved_sources=[],
        selected_sources=[],
        response_evaluation=None,
    )

    assert result.first_failure_stage == "router"
    assert result.failure_reasons == ["capability_mismatch:rag"]


def test_classify_first_failure_reports_retrieval_stage_before_evidence() -> None:
    case = EvaluationCase(
        case_id="late-policy",
        category="fact",
        question="di muon",
        outcome="answerable",
        expected_documents=["Noi Quy"],
        expected_sections=["Thoi gian"],
    )

    result = classify_first_failure(
        case,
        trace={"capability": "rag"},
        retrieved_sources=[EvaluationSource(document="Noi Quy", section="Hang hoa")],
        selected_sources=[],
        response_evaluation=None,
    )

    assert result.first_failure_stage == "retrieval"
    assert result.failure_reasons == ["expected_source_missing_from_retrieval"]


def test_classify_first_failure_reports_evidence_stage_when_retrieval_found_source() -> None:
    case = EvaluationCase(
        case_id="late-policy",
        category="fact",
        question="di muon",
        outcome="answerable",
        expected_documents=["Noi Quy"],
        expected_sections=["Thoi gian"],
    )

    result = classify_first_failure(
        case,
        trace={"capability": "rag"},
        retrieved_sources=[EvaluationSource(document="Noi Quy", section="Thoi gian")],
        selected_sources=[EvaluationSource(document="Noi Quy", section="Hang hoa")],
        response_evaluation=None,
    )

    assert result.first_failure_stage == "evidence"
    assert result.failure_reasons == ["expected_source_dropped_from_context"]


def test_classify_first_failure_reports_generation_or_validation_after_context() -> None:
    case = EvaluationCase(
        case_id="late-policy",
        category="fact",
        question="di muon",
        outcome="answerable",
        expected_documents=["Noi Quy"],
        expected_sections=["Thoi gian"],
    )
    source = EvaluationSource(document="Noi Quy", section="Thoi gian")

    generation_result = classify_first_failure(
        case,
        trace={"capability": "rag"},
        retrieved_sources=[source],
        selected_sources=[source],
        response_evaluation=ResponseEvaluation(
            passed=False,
            failure_reasons=["missing_required_fact_group:0"],
        ),
    )
    validation_result = classify_first_failure(
        case,
        trace={"capability": "rag", "parse_error": "invalid_json"},
        retrieved_sources=[source],
        selected_sources=[source],
        response_evaluation=ResponseEvaluation(
            passed=False,
            failure_reasons=["missing_citation"],
        ),
    )

    assert generation_result.first_failure_stage == "generation"
    assert generation_result.failure_reasons == ["missing_required_fact_group:0"]
    assert validation_result.first_failure_stage == "validation"
    assert validation_result.failure_reasons == ["parse_error:invalid_json"]
