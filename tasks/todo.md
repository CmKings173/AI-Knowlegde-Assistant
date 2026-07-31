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

- [ ] Write RED tests for router, retrieval, evidence, generation, and validation failures.
- [ ] Implement stable failure stage and reason codes.
- [ ] Run focused evaluation tests.
- [ ] Commit the increment.

## Checkpoint A

- [ ] `uv run python -m pytest tests/unit/test_rag_e2e_evaluation.py tests/unit/test_retrieval_evaluation.py -q`
- [ ] Existing retrieval-only evaluator remains backward compatible.

## Task 4: Live runner

- [ ] Write tests for case filtering and report aggregation.
- [ ] Add `scripts/evaluate_rag.py`.
- [ ] Write JSON report to `data/evaluation/rag_e2e_report.json`.
- [ ] Write Markdown summary to `data/evaluation/rag_e2e_summary.md`.
- [ ] Handle missing live dependencies clearly.
- [ ] Commit the increment.

## Task 5: Dataset coverage upgrade

- [ ] Add optional e2e expectations to existing cases.
- [ ] Add source-reviewed regression cases for current known failures.
- [ ] Verify retrieval evaluator still loads and runs.
- [ ] Commit the increment.

## Checkpoint B

- [ ] Deterministic tests pass.
- [ ] Live runner can run at least `--limit 3` in a configured environment.
- [ ] Generated reports are not committed.

## Task 6: Documentation and final review

- [ ] Update `app/rag/PROGRESS.md`.
- [ ] Update root `PROGRESS.md`.
- [ ] Run full backend unit suite.
- [ ] Run Ruff.
- [ ] Run harness check.
- [ ] Run `git diff --check`.
- [ ] Perform final code review.
- [ ] Resolve all Critical and Required findings.
- [ ] Confirm clean working tree after commits.
