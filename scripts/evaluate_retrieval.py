from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.deps import get_retriever
from app.config import get_settings
from app.rag.evaluation import load_evaluation_cases, summarize_results


async def main() -> None:
    settings = get_settings()
    project_root = Path(__file__).resolve().parents[1]
    dataset_path = project_root / "tests" / "evaluation" / "rag_cases.json"
    if not dataset_path.exists():
        raise SystemExit(f"Golden dataset not found: {dataset_path}")
    cases = load_evaluation_cases(dataset_path)
    retriever = get_retriever()
    details: list[dict[str, Any]] = []

    for case in cases:
        if not case.retrieval_applicable:
            details.append(
                {
                    "id": case.case_id,
                    "category": case.category,
                    "outcome": case.outcome,
                    "retrieval_applicable": False,
                    "hit": None,
                    "rank": None,
                    "latency_ms": 0.0,
                }
            )
            continue
        started = time.perf_counter()
        result = await retriever.retrieve(case.question)
        latency_ms = (time.perf_counter() - started) * 1000
        expected_doc = (case.expected_document or "").lower()
        expected_section = (case.expected_section or "").lower()
        rank = None
        for index, chunk in enumerate(result.chunks[: settings.final_context_top_n], start=1):
            doc_match = expected_doc in chunk.document_name.lower()
            section_match = expected_section in chunk.section.lower()
            if doc_match and section_match:
                rank = index
                break
        details.append(
            {
                "id": case.case_id,
                "category": case.category,
                "outcome": case.outcome,
                "retrieval_applicable": True,
                "hit": rank is not None,
                "rank": rank,
                "latency_ms": latency_ms,
            }
        )

    report = {**summarize_results(details), "details": details}
    report_path = settings.data_dir / "evaluation" / "retrieval_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {key: value for key, value in report.items() if key != "details"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
