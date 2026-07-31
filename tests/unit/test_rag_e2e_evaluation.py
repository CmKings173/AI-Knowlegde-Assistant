from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.rag.evaluation import EvaluationCaseError, load_evaluation_cases


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
