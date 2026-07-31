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

- [ ] Verify multiple delta ordering.
- [ ] Verify final answer is not duplicated.
- [ ] Build frontend.
- [ ] Commit only if source changes are required.

## Checkpoint B

- [ ] Conversation streams guarded deltas end to end.
- [ ] RAG structured/citation flow is unchanged.

## Task 5: Final quality gate

- [ ] Update architecture and progress documents.
- [ ] Run all backend unit tests.
- [ ] Run Ruff and harness check.
- [ ] Build frontend production bundle.
- [ ] Run five-axis code review.
- [ ] Resolve all Critical and Required findings.
- [ ] Confirm clean working tree.

## Deferred

- [ ] Hybrid context-dependency routing.
- [ ] Router threshold calibration.
- [ ] Metrics and observability platform.
- [ ] Tool execution.
