from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
    "AGENTS.md": [
        "What this system is",
        "How the repo is organized",
        "How to run it",
        "How to verify it",
        "Current progress",
    ],
    "CONSTRAINTS.md": [
        "Store-only upload is invalid",
        "Metadata filters must be applied before dense search",
        "Do not commit secrets",
    ],
    "PROGRESS.md": [
        "Current state",
        "Verified recently",
        "Known limitations",
    ],
    "app/api/ARCHITECTURE.md": ["Responsibilities", "Current endpoints", "Constraints"],
    "app/ingestion/ARCHITECTURE.md": ["Pipeline", "Seed documents", "idempotent"],
    "app/rag/ARCHITECTURE.md": ["Retrieval flow", "Prompt contract", "Reranker"],
    "app/providers/ARCHITECTURE.md": ["LLM providers", "Embedding providers", "Vector store"],
    "docs/decisions/ADR-001-agent-harness.md": ["Status", "Decision", "Consequences"],
}


def main() -> int:
    failures: list[str] = []
    for relative_path, required_terms in REQUIRED_FILES.items():
        path = ROOT / relative_path
        if not path.is_file():
            failures.append(f"missing: {relative_path}")
            continue
        content = path.read_text(encoding="utf-8")
        for term in required_terms:
            if term not in content:
                failures.append(f"{relative_path}: missing term {term!r}")

    if failures:
        print("Harness check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Harness check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
