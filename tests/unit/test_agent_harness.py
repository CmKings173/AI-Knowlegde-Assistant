from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_agent_landing_page_answers_fresh_session_questions() -> None:
    agents = read("AGENTS.md")

    for required in [
        "What this system is",
        "How the repo is organized",
        "How to run it",
        "How to verify it",
        "Current progress",
    ]:
        assert required in agents


def test_harness_system_of_record_files_exist() -> None:
    for relative_path in [
        "CONSTRAINTS.md",
        "PROGRESS.md",
        "app/api/ARCHITECTURE.md",
        "app/ingestion/ARCHITECTURE.md",
        "app/rag/ARCHITECTURE.md",
        "app/providers/ARCHITECTURE.md",
        "docs/decisions/ADR-001-agent-harness.md",
    ]:
        assert (ROOT / relative_path).is_file()


def test_harness_check_is_standardized_in_makefile() -> None:
    makefile = read("Makefile")

    assert "harness-check:" in makefile
    assert "scripts/check_harness.py" in makefile
    assert "check:" in makefile
