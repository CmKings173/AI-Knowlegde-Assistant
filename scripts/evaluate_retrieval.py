from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.deps import get_retriever
from app.config import get_settings


async def main() -> None:
    settings = get_settings()
    dataset_path = settings.data_dir / "evaluation" / "golden_questions.json"
    if not dataset_path.exists():
        raise SystemExit(f"Golden dataset not found: {dataset_path}")
    questions = json.loads(dataset_path.read_text(encoding="utf-8"))
    retriever = get_retriever()
    hits = 0
    reciprocal_sum = 0.0
    exact_section = 0
    latencies: list[float] = []
    details = []

    for item in questions:
        started = time.perf_counter()
        result = await retriever.retrieve(item["question"])
        latency_ms = (time.perf_counter() - started) * 1000
        latencies.append(latency_ms)
        expected_doc = item["expected_document"].lower()
        expected_section = item["expected_section"].lower()
        rank = None
        for index, chunk in enumerate(result.chunks[: settings.final_context_top_n], start=1):
            doc_match = expected_doc in chunk.document_name.lower()
            section_match = expected_section in chunk.section.lower()
            if doc_match and section_match:
                rank = index
                break
        if rank is not None:
            hits += 1
            reciprocal_sum += 1 / rank
            exact_section += 1
        details.append(
            {
                "id": item["id"],
                "hit": rank is not None,
                "rank": rank,
                "latency_ms": latency_ms,
            }
        )

    total = len(questions) or 1
    report = {
        "count": len(questions),
        "hit_rate_at_k": hits / total,
        "recall_at_k": hits / total,
        "mrr": reciprocal_sum / total,
        "exact_section_match": exact_section / total,
        "average_retrieval_latency_ms": sum(latencies) / total,
        "details": details,
    }
    report_path = settings.data_dir / "evaluation" / "retrieval_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {key: value for key, value in report.items() if key != "details"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
