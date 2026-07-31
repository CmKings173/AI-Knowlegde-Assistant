# Todo: Guarded Vietnamese Streaming

## Task 1: Language guard

- [ ] Write RED tests for Vietnamese, CJK, English, mixed text, and technical literals.
- [ ] Implement `VietnameseLanguageGuard`.
- [ ] Run focused tests and Ruff.
- [ ] Commit the increment.

## Task 2: Conversation stream executor

- [ ] Write RED tests for prefix buffering and progressive deltas.
- [ ] Write RED tests for retry, fallback, mid-stream interruption, and cancellation.
- [ ] Implement `ConversationStreamExecutor`.
- [ ] Run focused tests and commit the increment.

## Checkpoint A

- [ ] Language guard and executor tests pass.
- [ ] No dependency or model added.

## Task 3: Pipeline integration

- [ ] Write RED tests for structured history and router timing.
- [ ] Replace duplicated pipeline streaming blocks with the executor.
- [ ] Reuse one routing decision.
- [ ] Run pipeline and retrieval regression tests.
- [ ] Commit the increment.

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
