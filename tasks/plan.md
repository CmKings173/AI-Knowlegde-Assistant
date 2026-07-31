# Implementation Plan: RAG End-to-End Evaluation Harness

## Overview

Implement the approved spec in
`docs/superpowers/specs/2026-07-31-rag-end-to-end-evaluation-design.md`.
The change extends the existing retrieval-only evaluator into a layered
evaluation system that can run the production RAG pipeline and classify failures
by first bad stage: router, retrieval, evidence, generation, or validation.

## Architecture Decisions

- Keep `tests/evaluation/rag_cases.json` as the canonical dataset and preserve
  compatibility with `scripts/evaluate_retrieval.py`.
- Add optional end-to-end expectation fields instead of replacing the old
  `expected` block.
- Put deterministic scoring and failure classification in `app/rag/evaluation.py`
  so unit tests do not need Qdrant or Ollama.
- Add `scripts/evaluate_rag.py` as the live GX10 runner that calls production
  `RAGPipeline`.
- Do not add Langfuse, Ragas, DeepEval, Redis, a judge model, or a reranker in
  this phase.
- Generated reports live under `data/evaluation/` and are not versioned.

## Dependency Graph

```text
Dataset model extensions
-> deterministic text normalization + expectation checks
-> per-case e2e result + first-failure classifier
-> aggregate metrics/report writer
-> live evaluate_rag.py runner
-> dataset coverage upgrade
-> documentation/progress update
-> final quality gate
```

## Task 1: Extend evaluation dataset contract

**Description:** Extend `EvaluationCase` parsing so existing retrieval-only cases
still load, while optional end-to-end fields are validated when present.

**Acceptance criteria:**

- [ ] Existing `tests/evaluation/rag_cases.json` loads unchanged.
- [ ] Cases can include `history`, `document_scope`, `document_ids`,
      `expected_capability`, `expected_intent`, `expected_outcome`,
      `expected_documents`, `expected_sections`, `required_fact_groups`,
      `forbidden_fact_groups`, and `citation_required`.
- [ ] Invalid optional fields fail with a clear `EvaluationCaseError`.

**Verification:**

- [ ] RED then GREEN:
      `uv run python -m pytest tests/unit/test_rag_e2e_evaluation.py tests/unit/test_retrieval_evaluation.py -q`

**Dependencies:** None.

**Files likely touched:**

- `app/rag/evaluation.py`
- `tests/unit/test_rag_e2e_evaluation.py`
- `tests/unit/test_retrieval_evaluation.py`

**Estimated scope:** Medium, 3 files.

## Task 2: Add deterministic expectation scoring

**Description:** Add pure functions that score a final answer and trace against
case expectations using normalized Vietnamese-friendly matching.

**Acceptance criteria:**

- [ ] Required fact groups support any-of matching.
- [ ] Forbidden fact groups detect unsupported content.
- [ ] Citation-required cases fail when no citation appears.
- [ ] Vietnamese compliance can detect obvious CJK/English regressions by reusing
      the existing language guard.
- [ ] Missing optional expectations skip only related checks.

**Verification:**

- [ ] RED then GREEN:
      `uv run python -m pytest tests/unit/test_rag_e2e_evaluation.py -q`

**Dependencies:** Task 1.

**Files likely touched:**

- `app/rag/evaluation.py`
- `tests/unit/test_rag_e2e_evaluation.py`

**Estimated scope:** Medium, 2 files.

## Task 3: Classify first failure stage

**Description:** Given expected case data, observed pipeline trace, retrieved
candidates, selected context, and final answer checks, classify the earliest
stage that likely failed.

**Acceptance criteria:**

- [ ] Wrong capability for an expected RAG case is classified as `router`.
- [ ] Expected document/section absent from top-K is classified as `retrieval`.
- [ ] Expected evidence retrieved but dropped from selected context is classified
      as `evidence`.
- [ ] Correct context but wrong/missing final facts is classified as `generation`.
- [ ] Parse/literal/citation validation problems are classified as `validation`.

**Verification:**

- [ ] RED then GREEN:
      `uv run python -m pytest tests/unit/test_rag_e2e_evaluation.py -q`

**Dependencies:** Task 2.

**Files likely touched:**

- `app/rag/evaluation.py`
- `tests/unit/test_rag_e2e_evaluation.py`

**Estimated scope:** Medium, 2 files.

## Checkpoint A: Deterministic evaluator core

- [ ] Existing retrieval evaluator remains green.
- [ ] New e2e metric and classification tests pass without Qdrant/Ollama.
- [ ] Commit the deterministic evaluator core.

## Task 4: Add live RAG evaluation runner

**Description:** Add `scripts/evaluate_rag.py` that runs selected cases through
the production pipeline, collects final answers/traces, scores each case, and
writes JSON/Markdown reports.

**Acceptance criteria:**

- [ ] Supports `--case-id`, `--category`, and `--limit`.
- [ ] Calls the configured production `RAGPipeline`.
- [ ] Writes `data/evaluation/rag_e2e_report.json`.
- [ ] Writes `data/evaluation/rag_e2e_summary.md`.
- [ ] Fails clearly when live dependencies are unavailable.

**Verification:**

- [ ] Unit-test report aggregation and command helpers without external services.
- [ ] Manual live command on GX10:
      `uv run python scripts/evaluate_rag.py --limit 3`

**Dependencies:** Task 3.

**Files likely touched:**

- `scripts/evaluate_rag.py`
- `app/rag/evaluation.py`
- `tests/unit/test_rag_e2e_evaluation.py`

**Estimated scope:** Medium, 3 files.

## Task 5: Upgrade dataset coverage safely

**Description:** Add end-to-end expectations to existing cases and add a small
set of source-reviewed regression cases. Do not invent facts that are not visible
in checked-in/runtime processed document content.

**Acceptance criteria:**

- [ ] Existing categories remain covered.
- [ ] New regressions cover GitHub, current-time, room-count, lateness,
      leave/quit ambiguity, conversation, and language behavior.
- [ ] Retrieval-only script still works against the upgraded dataset.
- [ ] No production routing code depends on dataset keywords.

**Verification:**

- [ ] `uv run python -m pytest tests/unit/test_retrieval_evaluation.py tests/unit/test_rag_e2e_evaluation.py -q`
- [ ] `uv run python scripts/evaluate_retrieval.py` when Qdrant is available.

**Dependencies:** Task 4.

**Files likely touched:**

- `tests/evaluation/rag_cases.json`
- `tests/unit/test_retrieval_evaluation.py`
- `tests/unit/test_rag_e2e_evaluation.py`

**Estimated scope:** Medium, 3 files.

## Checkpoint B: Live runner ready

- [ ] Deterministic unit tests pass.
- [ ] Retrieval-only evaluator remains backward compatible.
- [ ] Live runner can produce a report in a configured environment.
- [ ] Commit live runner and dataset upgrade.

## Task 6: Documentation and final review

**Description:** Update durable project progress and run the repository quality
gate. Record any known limitation, especially whether live GX10 evaluation was
run in this environment or must be run by the user on GX10.

**Acceptance criteria:**

- [ ] `app/rag/PROGRESS.md` records the e2e evaluation harness.
- [ ] `PROGRESS.md` records branch-level status.
- [ ] No Critical or Required review findings remain.
- [ ] Working tree is clean after commits.

**Verification:**

- [ ] `uv run python -m pytest tests/unit -q`
- [ ] `uv run ruff check . --no-cache`
- [ ] `uv run python scripts/check_harness.py`
- [ ] `git diff --check`

**Dependencies:** Task 5.

**Files likely touched:**

- `app/rag/PROGRESS.md`
- `PROGRESS.md`
- `tasks/todo.md`

**Estimated scope:** Small, 3 files.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---:|---|
| Dataset expectations become brittle | Medium | Use normalized any-of fact groups and optional fields |
| Live eval is mistaken for unit tests | Medium | Keep external-service command separate from unit suite |
| Trace lacks enough retrieval/evidence detail | High | Add a typed internal evaluation trace collector instead of parsing logs |
| Existing retrieval evaluator breaks | High | Run old tests and keep old expected block valid |
| Cases become production rules | High | Store cases only in tests/evaluation; never import them in routing |
| Live run fails locally without Qdrant/Ollama | Medium | Fail clearly and document GX10 command |

## Open Questions

None blocking. If local processed document content is unavailable or incomplete,
Task 5 will add only cases whose expectations can be source-reviewed and leave
the rest as documented GX10 curation notes, without weakening the
evaluator itself.

## Definition of Done

- Every behavior change follows RED -> GREEN -> REFACTOR.
- Existing retrieval evaluation remains supported.
- New live e2e evaluator reports aggregate metrics and per-case first failure
  stage.
- Backend unit suite, Ruff, harness check, and diff check pass.
- Durable progress docs are updated.
