from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SERVICE_DIRS = [
    "app/api",
    "app/ingestion",
    "app/rag",
    "app/providers",
    "frontend",
    "docker",
]

REQUIRED_FILES = {
    "AGENTS.md": [
        "What this system is",
        "How the repo is organized",
        "Tech stack versions",
        "How to run it",
        "How to verify it",
        "Current progress",
    ],
    "CONSTRAINTS.md": [
        "PHẢI",
        "KHÔNG ĐƯỢC",
        "DocumentIngestionPipeline",
        "Metadata filtering",
        "Serve extracted images",
    ],
    "PROGRESS.md": [
        "Current state",
        "Verified recently",
        "Known limitations",
    ],
    "docs/decisions/ADR-001-agent-harness.md": ["Status", "Decision", "Consequences"],
}

SERVICE_REQUIRED_TERMS = {
    "ARCHITECTURE.md": ["Trách nhiệm", "Giao diện", "Phụ thuộc"],
    "PROGRESS.md": ["Current state", "Verified", "Open work"],
}


def main() -> int:
    failures: list[str] = []
    failures.extend(_check_required_files())
    failures.extend(_check_service_files())

    if failures:
        print("Harness check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Harness check passed.")
    return 0


def _check_required_files() -> list[str]:
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
    return failures


def _check_service_files() -> list[str]:
    failures: list[str] = []
    for service_dir in SERVICE_DIRS:
        for file_name, required_terms in SERVICE_REQUIRED_TERMS.items():
            relative_path = f"{service_dir}/{file_name}"
            path = ROOT / relative_path
            if not path.is_file():
                failures.append(f"missing: {relative_path}")
                continue
            content = path.read_text(encoding="utf-8")
            for term in required_terms:
                if term not in content:
                    failures.append(f"{relative_path}: missing term {term!r}")
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
