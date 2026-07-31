# Spec: Multi-stage Router

## Objective

Thay router intent dựa trên danh sách từ khóa bằng luồng nhiều tầng:

```text
User message + conversation state
-> Turn Resolver
-> Embedding Route Classifier
-> Qwen Structured Classifier khi kết quả embedding không chắc chắn
-> Capability Router
-> branch-specific execution
-> branch-specific response guard
-> final response
```

Mục tiêu là không ép câu hỏi ngoài phạm vi hoặc câu repair/follow-up vào RAG, không
thêm keyword riêng cho từng lỗi, và giữ latency thấp bằng cách chỉ gọi Qwen classifier
khi embedding classifier chưa đủ chắc chắn.

## Assumptions and Scope

- Conversation chỉ xử lý chào hỏi, phản hồi cảm xúc nhẹ, meta conversation,
  repair và follow-up; không trả lời kiến thức bên ngoài.
- Yêu cầu ngoài kho nội bộ được từ chối nhẹ nhàng và điều hướng về nghiệp vụ nội bộ.
- Tool là capability dự phòng và bị tắt khi chưa có tool registry.
- Dùng embedding provider và Qwen/LLM provider hiện có; không thêm model,
  LlamaIndex, Redis, reranker hoặc dependency mới.
- Observability, metrics, rate limit và model serving không thuộc thay đổi này.
- Metadata filtering, dynamic ingestion, retrieval, citation và image behavior hiện
  tại phải được giữ nguyên.

## Contracts

### Turn resolution

`TurnResolution` gồm:

- `kind`: `independent`, `follow_up`, `repair`, `continuation`.
- `resolved_query`: truy vấn hiện tại hoặc truy vấn độc lập đã được resolve.
- `confidence`: `[0, 1]`.
- `reason`: reason code ổn định.

Turn resolver ưu tiên continuation token và conversation-state metadata. Nó không
gọi LLM riêng. Trường hợp chưa chắc chắn được chuyển tiếp cho structured classifier.

### Intent classification

Intent mô tả hành động của người dùng, không mô tả capability:

- `ask_information`
- `request_instruction`
- `request_action`
- `conversation_repair`
- `continue_previous`
- `social`
- `unknown`

Embedding classifier trả intent candidate, affinity candidate, top score, margin và
`is_confident`. Chỉ chấp nhận khi score đạt threshold của route và margin so với
route thứ hai đạt ngưỡng. Prototype vectors được cache và query embedding chỉ tạo
một lần trong classification.

Qwen structured classifier chỉ chạy khi embedding chưa chắc chắn hoặc turn chưa
resolve. Output phải là JSON hợp lệ chứa intent, capability hint, subject,
context dependency, confidence và reason. Output lỗi phải fail-safe sang `clarify`,
không ép vào RAG.

### Capability decision

Capability Router có năm kết quả:

- `rag`
- `tool`
- `conversation`
- `unsupported`
- `clarify`

Không có fallback "route gần nhất". `request_action` chỉ đi `tool` khi tool registry
được bật và capability tồn tại; mặc định trả `unsupported`.

### Branch-specific status

- RAG: `answered`, `partial`, `insufficient_context`, `conflict`,
  `generation_failed`.
- Tool: `answered`, `tool_failed`, `permission_denied`.
- Conversation: `conversational`.
- Unsupported: `out_of_scope`.
- Clarify: `clarify`.

Response guard validate status theo branch. Guard không route lại request và không
biến generation error thành insufficient context.

## Required Behavior

| Input | Expected path |
|---|---|
| `hướng dẫn tôi dùng github đi` | instruction -> unsupported, không retrieval |
| `bạn nói gì thế` sau một answer | repair -> conversation, không retrieval |
| `bây giờ là mấy giờ` | unsupported khi chưa có clock tool, không retrieval |
| câu hỏi nội quy rõ ràng | RAG |
| câu hỏi nội bộ nhưng không có fact trong tài liệu | RAG -> insufficient context |
| greeting | conversation |
| `tiếp đi` với continuation token | continuation hiện tại |
| request mơ hồ và classifier lỗi | clarify |

Không được hard-code `github` như một special case trong production routing logic.
Tên này chỉ được dùng trong regression/evaluation tests.

## Tech Stack

- Python `>=3.11`
- FastAPI `>=0.115`
- Pydantic settings `>=2.4`
- Embedding provider hiện có: Ollama/OpenAI/Gemini/Hash
- LLM provider hiện có: Ollama/OpenAI/Gemini/Echo
- Pytest và pytest-asyncio

## Commands

```powershell
uv run pytest tests/unit/test_multistage_router.py -q
uv run pytest tests/unit/test_pipeline_multistage_router.py -q
uv run pytest tests/unit -q
uv run ruff check . --no-cache
uv run python scripts/check_harness.py
```

Frontend chỉ cần build nếu contract history/trace được thay đổi:

```powershell
cd frontend
npm run build
```

## Project Structure

- `app/rag/routing/`: contract và các stage routing độc lập.
- `app/rag/pipeline.py`: orchestration và branch execution.
- `app/rag/prompts.py`: structured classifier prompt.
- `app/api/schemas.py`: optional conversation-state fields.
- `frontend/src/`: truyền conversation-state metadata nếu contract thay đổi.
- `tests/unit/`: unit và pipeline regression tests.

## Code Style

Typed dataclass/enum được ưu tiên cho boundary nội bộ:

```python
@dataclass(frozen=True)
class CapabilityDecision:
    capability: Capability
    confidence: float
    reason: str
```

Không dùng dictionary không typed để truyền quyết định giữa các stage.

## Testing Strategy

- Unit test pure logic cho turn resolver, confidence/margin và capability mapping.
- Async unit test embedding classifier bằng fake embedding provider.
- Parser test cho Qwen structured output, gồm malformed/unknown values.
- Pipeline regression test chứng minh external/repair không gọi retriever.
- Pipeline test chứng minh internal knowledge vẫn retrieval và metadata scope không đổi.
- Full unit suite, Ruff, harness và frontend build là final gate.

## Boundaries

### Always

- Viết test RED trước mỗi thay đổi hành vi.
- Fail-safe về `clarify` hoặc `unsupported`; không fail-open sang RAG.
- Giữ provider abstraction và metadata filtering hiện tại.
- Giữ context, citation và literal validation của RAG.

### Ask first

- Thêm dependency/model mới.
- Bật tool execution.
- Thay public API theo hướng breaking.
- Xóa legacy intent router sau khi refactor nếu còn code tham chiếu.

### Never

- Hard-code seed documents hoặc case GitHub trong production logic.
- Luôn chọn route gần nhất khi score dưới threshold.
- Gọi Qwen ở cả Turn Resolver và Structured Classifier cho cùng request.
- Log secret hoặc toàn bộ tài liệu nội bộ.

## Success Criteria

- Các regression case trong bảng Required Behavior pass.
- Câu ngoài phạm vi rõ ràng và conversation repair không gọi retrieval.
- Qwen classifier chỉ chạy khi embedding classifier không chắc chắn.
- Structured classifier lỗi không làm API 500 và không ép request vào RAG.
- Tool capability bị tắt an toàn.
- Existing RAG, broad section, continuation, citation và metadata filter tests pass.
- Không thêm dependency.

## Open Questions

Không có câu hỏi blocking. Route thresholds là cấu hình khởi đầu an toàn và phải được
calibrate bằng evaluation dataset ở thay đổi observability/evaluation sau.
