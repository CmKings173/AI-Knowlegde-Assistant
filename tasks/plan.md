# Implementation Plan: Guarded Vietnamese Streaming

## Overview

Implement the approved design in
`docs/superpowers/specs/2026-07-31-guarded-vietnamese-streaming-design.md`.
Conversation responses will validate a short prefix before emitting SSE deltas,
continue validating a rolling window, retry once before the first delta, and use
a Vietnamese fallback when validation still fails. RAG structured generation,
retrieval, citations, and the current hybrid router remain unchanged.

## Architecture Decisions

- `VietnameseLanguageGuard` is deterministic and adds no dependency or model.
- Conversation streaming moves to a focused executor instead of adding another
  branch to the 1,600-line pipeline.
- RAG continues buffering structured JSON; only Conversation uses guarded streaming.
- The retry prompt never includes raw invalid model output.
- Existing SSE event schemas remain backward compatible.
- Timing starts before routing and is passed through the executor.
- Hybrid context-dependency routing is explicitly deferred.

## Dependency Graph

```text
LanguageDecision + VietnameseLanguageGuard
-> guarded ConversationStreamExecutor
-> RAGPipeline/SSE integration
-> frontend/API regression verification
-> architecture/progress documentation
-> final multi-axis review
```

## Task 1: Deterministic Vietnamese language guard

**Description:** Add a pure guard that validates prefixes, rolling windows, and
complete responses while allowing internal-product names and technical literals.

**Acceptance criteria:**

- [ ] Vietnamese text and short technical messages are accepted.
- [ ] CJK, mixed Vietnamese/CJK, and sufficiently long English output are rejected.
- [ ] URLs, email, IP, port, acronym, and code fragments do not create false positives.

**Verification:**

- [ ] RED then GREEN:
  `uv run python -m pytest tests/unit/test_language_guard.py -q`
- [ ] Ruff passes for the new module and test.

**Dependencies:** None.

**Files likely touched:**

- `app/rag/guards/__init__.py`
- `app/rag/guards/language_guard.py`
- `tests/unit/test_language_guard.py`

**Estimated scope:** Medium, 3 files.

## Task 2: Guarded conversation stream executor

**Description:** Extract conversation streaming into an executor that buffers a
30-character prefix, validates every rolling window, emits real deltas, retries
once before the first delta, and preserves final-answer equality.

**Acceptance criteria:**

- [ ] No delta is emitted before prefix acceptance.
- [ ] Accepted provider fragments are emitted progressively and concatenate exactly
  to `final.answer`.
- [ ] Invalid prefix retries once without copying raw invalid output; a second
  failure produces the fixed Vietnamese fallback.
- [ ] Invalid mid-stream fragments are not emitted; a safe Vietnamese notice is
  emitted and recorded in the final trace.

**Verification:**

- [ ] RED then GREEN:
  `uv run python -m pytest tests/unit/test_conversation_stream.py -q`
- [ ] Tests cover provider exception and async-generator cancellation.

**Dependencies:** Task 1.

**Files likely touched:**

- `app/rag/execution/__init__.py`
- `app/rag/execution/conversation_stream.py`
- `tests/unit/test_conversation_stream.py`
- `app/rag/prompts.py`

**Estimated scope:** Medium, 4 files.

## Checkpoint A: Guard and executor

- [ ] Task 1 and Task 2 focused tests pass.
- [ ] Ruff passes.
- [ ] No external dependency or model is added.
- [ ] Commit guard and executor as independently reviewable increments.

## Task 3: Pipeline integration and accurate SSE timing

**Description:** Replace duplicated conversation-streaming branches in
`RAGPipeline` with the executor, reuse one routing decision, pass structured
history, and include routing in SSE timing.

**Acceptance criteria:**

- [ ] Production SSE routes exactly once.
- [ ] Conversation streaming prompt includes `status`, `capability`, `subject`, and
  `turn_kind`.
- [ ] `timing_ms.router` measures router time and `timing_ms.total` covers the whole
  SSE request.
- [ ] RAG, Unsupported, Clarify, continuation, and metadata-filter behavior do not
  change.

**Verification:**

- [ ] RED then GREEN:
  `uv run python -m pytest tests/unit/test_pipeline_multistage_router.py -q`
- [ ] Regression:
  `uv run python -m pytest tests/unit/test_pipeline_retrieval_v2.py tests/unit/test_response_validation_v2.py -q`

**Dependencies:** Task 2.

**Files likely touched:**

- `app/rag/pipeline.py`
- `app/api/deps.py`
- `app/rag/prompts.py`
- `tests/unit/test_pipeline_multistage_router.py`

**Estimated scope:** Medium, 4 files.

## Task 4: API and frontend SSE regression

**Description:** Verify the existing frontend consumes multiple delta events without
duplicating the final answer and that the public API schema remains compatible.

**Acceptance criteria:**

- [ ] Multiple delta events append in order.
- [ ] Final event updates metadata without duplicating streamed text.
- [ ] Existing clients need no request or event-schema migration.

**Verification:**

- [ ] Backend route tests for progress/delta/final ordering pass.
- [ ] `npm run build` passes in `frontend/`.
- [ ] Existing frontend static/runtime tests pass.

**Dependencies:** Task 3.

**Files likely touched:**

- `tests/unit/test_frontend_copy.py`
- `frontend/src/chat-runtime.tsx` only if a real regression is reproduced.
- `frontend/src/types.ts` only if the existing contract is insufficient.

**Estimated scope:** Small, 1-3 files.

## Checkpoint B: End-to-end contract

- [ ] Conversation produces multiple deltas with a fake fragment provider.
- [ ] No rejected fragment reaches the simulated client.
- [ ] `final.answer` equals concatenated deltas.
- [ ] RAG continues to produce validated final output without raw JSON streaming.

## Task 5: Documentation and final review

**Description:** Update architecture/progress to match the implemented behavior and
run the repository quality gates followed by five-axis code review.

**Acceptance criteria:**

- [ ] Architecture documents describe guarded streaming and fallback semantics.
- [ ] No Critical or Required code-review findings remain.
- [ ] Working tree is clean after atomic commits.

**Verification:**

- [ ] `uv run python -m pytest tests/unit -q`
- [ ] `uv run ruff check . --no-cache`
- [ ] `uv run python scripts/check_harness.py`
- [ ] `npm run build` from `frontend/`
- [ ] `git diff --check`

**Dependencies:** Task 4.

**Files likely touched:**

- `app/rag/ARCHITECTURE.md`
- `app/rag/PROGRESS.md`
- `PROGRESS.md`
- `tasks/todo.md`

**Estimated scope:** Medium, 4 files.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---:|---|
| False rejection of short technical text | Medium | Accept short output; whitelist literal shapes and acronyms |
| Invalid language appears after accepted prefix | High | Validate rolling window before every delta; never emit rejected fragment |
| Retry doubles latency | Medium | Retry only before first delta and at most once |
| Final answer differs from visible deltas | High | Build final answer only from emitted delta list; assert equality |
| Client disconnect leaves generation running | Medium | Close async generator in `finally`; cancellation tests |
| Pipeline grows further | High | Extract executor first; pipeline only orchestrates |
| Scope drifts into router redesign | High | Keep router behavior unchanged and record it as deferred |

## Open Questions

None. The approved defaults are a 30-character prefix, one retry, deterministic
guard, no new dependency/model, guarded streaming for Conversation, and buffered
structured generation for RAG.

## Definition of Done

- Every behavior change follows RED -> GREEN -> REFACTOR.
- Each task leaves tests green and is committed separately.
- All acceptance criteria from the approved design spec pass.
- Full backend unit suite, Ruff, harness check, and frontend build pass.
- Review has no unresolved Critical or Required findings.
