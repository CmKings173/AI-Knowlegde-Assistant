# Todo: RAG End-to-End Evaluation Harness

## Task 1: Dataset contract

- [x] Write RED tests for optional e2e fields on evaluation cases.
- [x] Extend `EvaluationCase` without breaking existing retrieval cases.
- [x] Validate malformed optional fields with useful errors.
- [x] Run focused evaluation tests.
- [x] Commit the increment.

## Task 2: Deterministic scoring

- [x] Write RED tests for required fact groups.
- [x] Write RED tests for forbidden fact groups.
- [x] Write RED tests for citation-required and Vietnamese compliance checks.
- [x] Implement deterministic scoring helpers.
- [x] Run focused evaluation tests.
- [x] Commit the increment.

## Task 3: First-failure classification

- [x] Write RED tests for router, retrieval, evidence, generation, and validation failures.
- [x] Implement stable failure stage and reason codes.
- [x] Run focused evaluation tests.
- [x] Commit the increment.

## Checkpoint A

- [x] `uv run python -m pytest tests/unit/test_rag_e2e_evaluation.py tests/unit/test_retrieval_evaluation.py -q`
- [x] Existing retrieval-only evaluator remains backward compatible.

## Task 4: Live runner

- [x] Write tests for case filtering and report aggregation.
- [x] Add `scripts/evaluate_rag.py`.
- [x] Write JSON report to `data/evaluation/rag_e2e_report.json`.
- [x] Write Markdown summary to `data/evaluation/rag_e2e_summary.md`.
- [x] Handle missing live dependencies clearly.
- [x] Commit the increment.

## Task 5: Dataset coverage upgrade

- [x] Add optional e2e expectations to existing cases.
- [x] Add source-reviewed regression cases for current known failures.
- [x] Verify retrieval evaluator still loads in focused tests.
- [x] Commit the increment.

## Checkpoint B

- [x] Deterministic tests pass.
- [ ] Live runner can run at least `--limit 3` in a configured environment.
- [x] Generated reports are not committed.

## Task 6: Documentation and final review

- [x] Update `app/rag/PROGRESS.md`.
- [x] Update root `PROGRESS.md`.
- [x] Run full backend unit suite.
- [x] Run Ruff.
- [x] Run harness check.
- [x] Run `git diff --check`.
- [x] Perform final code review.
- [x] Resolve all Critical and Required findings.
- [ ] Confirm clean working tree after commits.
