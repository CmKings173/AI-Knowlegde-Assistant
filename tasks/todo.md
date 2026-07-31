# Todo: Multi-stage Router

## Specification

- [x] Chốt phạm vi Conversation và Unsupported với người dùng.
- [x] Chốt luồng Turn -> Embedding -> Qwen fallback -> Capability -> Guard.
- [x] Ghi design spec.
- [x] Ghi implementation plan.

## Task 1: Contracts and Turn Resolver

- [ ] Viết test RED cho typed contracts và turn resolution.
- [ ] Implement contract và resolver tối thiểu.
- [ ] Chạy focused tests.

## Task 2: Embedding Classifier

- [ ] Viết test RED cho threshold, margin, cache và provider error.
- [ ] Implement classifier không dependency mới.
- [ ] Chạy Checkpoint A.

## Task 3: Qwen Structured Classifier

- [ ] Viết test RED cho valid/malformed/unknown JSON.
- [ ] Implement prompt, parser và provider fallback.
- [ ] Chạy focused tests.

## Task 4: Capability Router

- [ ] Viết test RED cho RAG/Conversation/Unsupported/Clarify/Tool disabled.
- [ ] Implement capability decisions không default sang RAG.
- [ ] Chạy Checkpoint B.

## Task 5: Pipeline Integration

- [ ] Viết regression test GitHub không retrieval.
- [ ] Viết regression test conversation repair không retrieval.
- [ ] Viết test internal knowledge vẫn retrieval.
- [ ] Viết test uncertain embedding gọi Qwen đúng một lần.
- [ ] Integrate multi-stage orchestrator.
- [ ] Chạy pipeline focused tests.

## Task 6: Guard and Conversation State

- [ ] Viết test branch-specific status.
- [ ] Thêm optional conversation-state contract.
- [ ] Truyền metadata từ frontend history.
- [ ] Build frontend.

## Task 7: Final Verification

- [ ] Full backend unit suite.
- [ ] Ruff toàn repo.
- [ ] Harness check.
- [ ] Frontend production build.
- [ ] Cập nhật architecture/progress.
- [ ] Review correctness/readability/architecture/security/performance.
- [ ] Xử lý mọi finding Critical/Required.
