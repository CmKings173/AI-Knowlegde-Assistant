# ADR-002: Retrieval-first RAG V2 với adaptive retrieval có điều kiện

## Status

Accepted

## Date

2026-07-31

## Context

Router dựa nhiều vào keyword đã bỏ sót câu hỏi diễn đạt tự nhiên như “xin nghỉ hẳn”.
RRF top-k thuần túy cũng có thể đưa chunk khác domain vào context. Heuristic fact
guard sau generation từng hiểu sai định dạng thời gian và biến câu trả lời grounded
thành `generation_failed`. Hệ thống chỉ vận hành một model Qwen nên không phù hợp
thêm classifier LLM hoặc reranker bắt buộc vào critical path.

## Decision

- Giữ metadata filtering trước dense, BM25 và RRF.
- Giữ raw dense/BM25 rank và score sau fusion.
- Với intent mơ hồ nhưng có khả năng thuộc kho, retrieve trước rồi quyết định dựa
  trên evidence thay vì mở rộng keyword vô hạn.
- Dùng evidence selector để deduplicate, ưu tiên domain nhất quán và loại noise.
- Chỉ khi evidence yếu mới dùng cùng Qwen rewrite tối đa hai query rồi fuse lại.
- Reranker model là tùy chọn; RRF + selector là fallback production.
- Loại heuristic fact guard khỏi V2. Chỉ kiểm tra deterministic citation và literal
  time/IP/port trong source được cite.
- Phân biệt rõ `generation_failed`, `insufficient_context`, `partial` và `clarify`.

## Alternatives Considered

### Mở rộng keyword cho từng domain

Dễ triển khai nhưng không mở rộng được cho mọi cách diễn đạt và tạo vòng vá lỗi vô
hạn. Không chọn.

### Luôn gọi Qwen để classify và rewrite

Có thể tăng recall nhưng tăng latency và áp lực lên Ollama cho 70–100 người dùng.
Không chọn; chỉ gọi adaptive khi evidence yếu.

### Bắt buộc reranker model

Có thể cải thiện precision nhưng tạo thêm service/model và failure mode. Chưa chọn
làm dependency bắt buộc; có thể bật sau khi benchmark.

### Giữ heuristic fact guard

Đã gây false positive với thời gian và citation chưa hoàn hảo, làm mất câu trả lời
có căn cứ. Không chọn.

## Consequences

- Query thông thường vẫn có latency gần baseline; query khó có thể thêm một lần gọi
  Qwen để rewrite.
- Retrieval quyết định dựa vào evidence và provenance thay vì keyword đơn lẻ.
- Hệ thống ổn định khi reranker không khả dụng.
- Ngưỡng evidence phải được hiệu chỉnh bằng evaluation trên dữ liệu thật.
- Deterministic literal validation không thay thế semantic claim verification; prompt,
  evidence quality và citation vẫn là các lớp chống hallucination chính.
