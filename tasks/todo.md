# Todo: Multi-stage Router

## Specification

- [x] Chốt phạm vi Conversation, Unsupported và Tool-disabled.
- [x] Chốt luồng Turn Resolver -> Embedding -> Qwen fallback -> Capability Router.
- [x] Ghi design spec và implementation plan.

## Contracts and routing stages

- [x] Tạo typed contracts cho turn, intent, affinity và capability.
- [x] Implement Turn Resolver không gọi LLM riêng.
- [x] Implement Embedding Route Classifier với threshold, margin và cache.
- [x] Chống khởi tạo cache prototype lặp khi có request đồng thời.
- [x] Implement Qwen Structured Classifier với JSON schema và fail-safe.
- [x] Implement Capability Router không mặc định đẩy vào RAG.

## Pipeline and conversation state

- [x] Tích hợp router mới vào production dependency injection.
- [x] External request không gọi retrieval.
- [x] Conversation repair không gọi retrieval.
- [x] Internal knowledge vẫn đi qua RAG và metadata filtering hiện có.
- [x] Truyền `status`, `capability`, `subject`, `turn_kind` qua chat history.
- [x] Giữ SSE delta cho nhánh conversation và chỉ route một lần.
- [x] Giữ legacy router cho các caller chưa inject router mới.

## Verification

- [x] Unit tests toàn backend.
- [x] Ruff toàn repository.
- [x] Harness check.
- [x] Frontend production build.
- [x] Review correctness, readability, architecture, security và performance.
- [x] Không còn finding Critical/Required trong phạm vi thay đổi.

## Deferred by scope

- [ ] Metrics, tracing, Langfuse/OpenTelemetry và production SLO.
- [ ] Calibration threshold bằng evaluation dataset thực tế.
- [ ] Tool registry và tool execution.
- [ ] Xóa legacy intent router sau giai đoạn tương thích.
