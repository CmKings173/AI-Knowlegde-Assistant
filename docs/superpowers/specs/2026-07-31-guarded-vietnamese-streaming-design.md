# Design: Guarded Vietnamese Streaming

## Objective

Conversation responses PHẢI được trả bằng tiếng Việt và PHẢI có streaming thực sự
sau một đoạn kiểm tra ngắn. Không để token CJK xuất hiện trên UI rồi mới thay thế.

Phase này chỉ xử lý:

- language validation;
- guarded conversation streaming;
- retry/fallback khi model sinh sai ngôn ngữ;
- structured conversation history cho prompt streaming;
- timing chính xác cho routing và generation trong SSE response.

Phase này KHÔNG thay đổi hybrid router, retrieval, metadata filtering, citation,
embedding model, Qwen model hoặc observability platform.

## Current Problems

1. `stream_generate()` đang được đọc hết vào `answer_parts`, sau đó mới gửi một
   event `delta`; đây không phải token streaming thực sự.
2. Conversation streaming dùng `_format_history()` nên làm mất `status`,
   `capability`, `subject` và `turn_kind`.
3. Language guard hiện chỉ kiểm tra CJK sau khi model đã sinh xong.
4. Lỗi ngôn ngữ bị biến thành out-of-scope, làm sai semantics.
5. Routing xảy ra trước khi tạo timing context nên `router_ms` và `total_ms` của
   SSE response không phản ánh latency thực.

## Selected Approach

RAG tiếp tục buffer toàn bộ output để parse JSON, kiểm tra citation và grounding.
Conversation sử dụng guarded streaming:

```text
Qwen token stream
-> prefix buffer
-> VietnameseLanguageGuard
   | accepted
   |-> emit buffered text
   |-> emit subsequent safe deltas
   |-> final validation
   |
   | rejected before first delta
   |-> cancel first generation
   |-> retry once with clean retry prompt
   |-> validate retry prefix
   |-> stream retry or return Vietnamese fallback
```

Không gửi lại raw output sai ngôn ngữ vào retry prompt.

## Components

### VietnameseLanguageGuard

Module sở hữu language policy:

```text
app/rag/guards/language_guard.py
```

Contract:

```python
LanguageDecision(
    accepted: bool,
    detected: str,
    reason: str,
)
```

Hai operation:

- `validate_prefix(text)`: quyết định có được bắt đầu phát delta hay không.
- `validate_window(text)`: kiểm tra rolling window trước mỗi delta tiếp theo.
- `validate_complete(text)`: kiểm tra và ghi quyết định cuối cùng trước final response.

Policy:

- Reject ngay khi có ký tự CJK.
- Cho phép acronym, tên sản phẩm, URL, email, IP, port và code fragment.
- Không reject câu ngắn chỉ vì chưa có dấu tiếng Việt.
- Với output đủ dài nhưng chủ yếu là Latin không dấu/không có tín hiệu tiếng Việt,
  đánh dấu `uncertain_non_vietnamese`.
- Không dùng external language-detection model hoặc dependency mới.

Guard là deterministic và không tự route request.

### ConversationStreamExecutor

Tách conversation streaming khỏi `RAGPipeline`:

```text
app/rag/execution/conversation_stream.py
```

Trách nhiệm:

- gọi `stream_generate`;
- giữ prefix buffer;
- chạy language guard;
- phát SSE delta;
- retry tối đa một lần;
- tạo final response;
- ghi timing vào response hiện có.

`RAGPipeline` chỉ route và gọi executor.

### Structured history formatter

Conversation streaming PHẢI dùng cùng structured history formatter với
non-stream conversation:

```text
role
content
status
capability
subject
turn_kind
```

Assistant message từng fail language validation KHÔNG ĐƯỢC đưa raw invalid content
vào retry prompt. Chỉ truyền metadata và nội dung user cần thiết.

## Prefix Buffer

Prefix buffer mặc định:

```text
30 Unicode characters
```

Executor cũng được phép validate sớm hơn khi gặp dấu kết thúc câu hoặc newline.

Prefix chưa đạt 30 ký tự nhưng model đã kết thúc vẫn phải được validate như complete
output.

Không dùng token count vì provider trả text fragment và tokenizer có thể khác nhau.

## Streaming Semantics

Conversation SSE event order:

```text
progress(routing)
progress(generation)
delta(prefix)
delta(fragment)*
final
```

Yêu cầu:

- Không phát bất kỳ delta nào trước khi prefix được accept.
- Sau khi prefix accept, phát từng fragment do provider trả về; không gom toàn bộ câu.
- Trước mỗi fragment, kiểm tra fragment cùng rolling window gần nhất; fragment bị
  reject KHÔNG ĐƯỢC phát ra UI.
- `final.answer` bằng chính xác phép nối các delta đã phát.
- `final.status` là `conversational`.
- Client cũ vẫn hoạt động với event schema hiện tại.

RAG giữ nguyên:

```text
progress(routing)
progress(retrieval/generation)
final
```

RAG không stream raw JSON token.

## Retry and Fallback

Nếu prefix đầu tiên bị reject:

1. Không phát raw output.
2. Hủy/đóng generator hiện tại.
3. Gọi model lại đúng một lần.
4. Retry prompt không chứa raw invalid output.
5. Retry prompt yêu cầu tạo lại từ đầu bằng tiếng Việt có dấu.
6. Retry cũng phải qua prefix guard.

Nếu retry vẫn fail:

- trả fallback tiếng Việt cố định;
- status vẫn là `conversational`;
- trace ghi `language_guard_decision`, `language_retry_used` và
  `language_fallback_used`;
- không dùng `out_of_scope` vì đây là generation failure, không phải capability error.

Fallback:

```text
Mình chưa thể tạo câu trả lời tiếng Việt ổn định lúc này. Bạn vui lòng thử lại.
```

Nếu output đổi sang CJK sau khi prefix đã được phát:

- dừng phát fragment sai;
- phát một delta thông báo tiếng Việt an toàn rằng câu trả lời bị dừng;
- final trả đúng phép nối phần tiếng Việt trước đó và delta thông báo;
- không retry vì không thể thu hồi delta đã gửi;
- trace ghi `language_stream_interrupted=true`.

## Timing

SSE timing bắt đầu trước Turn Resolver và kết thúc sau final response.

Các field hiện có:

- `router`: gồm Turn Resolver, embedding classifier và Qwen classifier fallback;
- `llm`: tổng thời gian generation, gồm retry nếu có;
- `total`: toàn bộ thời gian từ lúc bắt đầu xử lý tới final;
- retrieval/rerank giữ nguyên.

Phase này chưa thêm Langfuse, OpenTelemetry, Prometheus hoặc metric backend mới.

## Security and Prompt Handling

- User query và history tiếp tục bị giới hạn tại API schema.
- History là dữ liệu không tin cậy; system prompt có quyền ưu tiên cao hơn.
- Không log raw invalid output hoặc toàn bộ history.
- Chỉ log reason code, độ dài output, retry/fallback flag và timing.
- Không log system prompt, API key hoặc continuation token.

## Error Handling

- Provider error trước delta: trả fallback tiếng Việt hiện có theo error contract.
- Provider error sau delta: kết thúc stream bằng error/final phù hợp, không phát lại
  nội dung đã gửi.
- Client disconnect phải đóng async generator và không tiếp tục retry.
- Guard exception fail-safe: không phát prefix chưa được kiểm tra.

## Tests

### Language guard unit tests

- Vietnamese có dấu được accept.
- CJK bị reject.
- English paragraph đủ dài bị reject.
- `NAS`, `Outlook`, URL, email, IP, port và code fragment không gây false positive.
- Câu ngắn `OK`, `NAS lỗi rồi` không bị reject.
- Mixed Vietnamese/CJK bị reject.

### Streaming executor tests

- Không delta trước khi prefix accept.
- Sau prefix, fragment được phát liên tục thay vì gom toàn bộ.
- `final.answer` bằng phép nối delta.
- Prefix CJK kích hoạt đúng một retry.
- Raw invalid output không xuất hiện trong retry prompt.
- Retry hợp lệ được stream.
- Retry fail trả fallback tiếng Việt.
- CJK giữa stream dừng fragment sai và ghi interrupted trace.
- Fragment sai ngôn ngữ không xuất hiện trong bất kỳ delta nào.
- Khi stream bị dừng, safe notice được phát thành delta và `final.answer` vẫn bằng
  phép nối tất cả delta.
- Provider exception và client cancellation đóng generator.

### Pipeline/API regression tests

- Conversation repair dùng structured history.
- RAG vẫn buffer JSON và giữ citation validation.
- External request vẫn không retrieval.
- Routing chỉ chạy một lần.
- SSE timing bao gồm routing.
- Frontend tiếp tục ghép delta và final không duplicate text.

## Acceptance Criteria

- Không có CJK trong bất kỳ conversation delta nào.
- Conversation hợp lệ phát nhiều delta khi provider trả nhiều fragment.
- First delta chỉ bị trì hoãn tới khi prefix được validate.
- Retry tối đa một lần và không chứa raw invalid output.
- Fallback luôn là tiếng Việt và không bị gắn `out_of_scope`.
- Structured conversation state tới được streaming prompt.
- SSE `router` và `total` timing phản ánh toàn bộ request.
- Không thêm dependency hoặc model.
- Full backend tests, Ruff, harness check và frontend build pass.

## Deferred

- Hybrid context-dependency routing.
- Router threshold calibration.
- Metrics/observability platform.
- Tool execution.
- Progressive grounded RAG token streaming.
