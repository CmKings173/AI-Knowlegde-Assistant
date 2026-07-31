# Todo: Guarded Vietnamese Streaming

## Task 1: Language guard

- [x] Write RED tests for Vietnamese, CJK, English, mixed text, and technical literals.
- [x] Implement `VietnameseLanguageGuard`.
- [x] Run focused tests and Ruff.
- [x] Commit the increment.

## Task 2: Conversation stream executor

- [x] Write RED tests for prefix buffering and progressive deltas.
- [x] Write RED tests for retry, fallback, mid-stream interruption, and cancellation.
- [x] Implement `ConversationStreamExecutor`.
- [x] Run focused tests and commit the increment.

## Checkpoint A

- [x] Language guard and executor tests pass.
- [x] No dependency or model added.

## Task 3: Pipeline integration

- [x] Write RED tests for structured history and router timing.
- [x] Replace duplicated pipeline streaming blocks with the executor.
- [x] Reuse one routing decision.
- [x] Run pipeline and retrieval regression tests.
- [x] Commit the increment.

## Task 4: API/frontend regression

- [x] Verify multiple delta ordering.
- [x] Verify final answer is not duplicated.
- [x] Build frontend.
- [x] Commit only if source changes are required (no additional source change needed).

## Checkpoint B

- [x] Conversation streams guarded deltas end to end.
- [x] RAG structured/citation flow is unchanged.

## Task 5: Final quality gate

- [x] Update architecture and progress documents.
- [x] Run all backend unit tests (176 passed).
- [x] Run Ruff and harness check.
- [x] Build frontend production bundle.
- [x] Run five-axis code review.
- [x] Resolve all Critical and Required findings.
- [x] Confirm clean working tree after the final commit.

## Deferred

- [ ] Hybrid context-dependency routing.
- [ ] Router threshold calibration.
- [ ] Metrics and observability platform.
- [ ] Tool execution.
