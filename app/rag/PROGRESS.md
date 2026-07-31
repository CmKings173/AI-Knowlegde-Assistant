# Tiến độ RAG

Last updated: 2026-07-31

## Current state — Trạng thái hiện tại

- Retrieval dùng dense Qdrant + BM25 + RRF và giữ raw score/rank provenance.
- Metadata filter chạy trước dense search, BM25 và fusion.
- `document_scope="selected"` với `document_ids=[]` không search toàn kho.
- Evidence selector loại duplicate/cross-domain noise và ghi reason code vào trace.
- Query mơ hồ có khả năng thuộc nghiệp vụ dùng retrieval-first thay vì phụ thuộc vào
  danh sách keyword domain.
- Evidence yếu mới kích hoạt adaptive rewrite bằng cùng Qwen, tối đa hai query; lỗi
  rewrite tự fallback về candidates của query gốc.
- Context bị giới hạn bởi `FINAL_CONTEXT_TOP_N` và `MAX_CONTEXT_TOKENS`.
- Prompt contract là system prompt + bounded CONTEXT + user query/history.
- Citation lạ bị từ chối; time, IP và port phải có trong source được cite.
- Heuristic fact guard đã bị loại khỏi pipeline V2.
- Parse/generation failure trả `generation_failed`, không giả thành thiếu tài liệu.
- Trace API giữ tương thích field cũ và bổ sung diagnostics retrieval V2.

## Verified — Đã kiểm chứng

- 129 backend unit tests pass tại final gate.
- Ruff toàn repo, harness check và frontend production build pass.
- Tests bao phủ provenance, evidence selection, adaptive retrieval, retrieval-first,
  metadata scope, failure status, citation và critical literals.
- Normal retrieval path không gọi rewrite; adaptive path có giới hạn số lần gọi Qwen.
- Retrieval evaluation thật đạt recall@K `1.0`, MRR `0.9583` trên 12 retrieval cases;
  average retrieval latency là `703.39 ms` trong môi trường kiểm thử ngày 2026-07-31.

## Open work — Việc còn mở

- Mở rộng evaluation từ retrieval-level sang answer-level groundedness/citation và
  benchmark concurrency trên GX10 trước khi chốt production SLO.
- `bge-reranker-v2-m3` chưa được bật; hệ thống fallback về RRF + evidence selector.
- BM25 filtered search có thể rebuild filtered index mỗi request; cần benchmark khi
  corpus hoặc concurrency tăng.
- Critical-literal validation hiện chỉ bao phủ time, IP và port; claim-level semantic
  verification cần một thiết kế/evaluation riêng nếu triển khai sau.

## Multi-stage router - 2026-07-31

- Production pipeline dùng Turn Resolver, embedding route classifier, Qwen structured
  fallback và Capability Router.
- External request và conversation repair không còn bị đẩy mặc định vào retrieval.
- Tool execution đang tắt; unsupported và classifier failure fail-safe rõ ràng.
- Structured conversation state được truyền từ frontend về backend.
- Conversation SSE giữ delta streaming và chỉ route một lần.
- Prototype embedding cache có khóa chống duplicate initialization khi request đồng thời.
- Final gate: backend unit tests, Ruff, harness check và frontend build đều pass.
- Observability, metrics và threshold calibration được tách sang phase sau theo yêu cầu.

## Guarded Vietnamese streaming - 2026-07-31

- Conversation giữ prefix 30 ký tự trước khi phát delta đầu tiên.
- Deterministic language guard chặn Han, Hiragana, Katakana, Hangul, mixed-script
  và English output không có tín hiệu tiếng Việt; technical literals và acronym
  ngắn vẫn được hỗ trợ.
- Prefix invalid retry đúng một lần bằng clean prompt; retry fail dùng fallback
  tiếng Việt thay vì out-of-scope.
- Conversation phát nhiều delta thực sự và final answer khớp nội dung đã phát.
- Structured history được dùng cho cả router và conversation streaming prompt.
- SSE timing hiện bao gồm routing.
- RAG structured JSON/citation flow không thay đổi.
- Final gate: 176 backend unit tests, Ruff, harness check và frontend production
  build đều pass.
