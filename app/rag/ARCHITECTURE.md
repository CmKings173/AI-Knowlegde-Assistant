# Kiến trúc RAG

RAG service biến câu hỏi người dùng thành câu trả lời tiếng Việt có căn cứ, citation
và ảnh liên quan từ tài liệu nội bộ.

## Trách nhiệm

- Chuẩn hóa và phân loại câu hỏi.
- Áp dụng document scope và metadata filter trước khi tìm kiếm.
- Tìm dense candidates từ Qdrant và lexical candidates từ BM25.
- Hợp nhất thứ hạng bằng RRF nhưng giữ provenance của từng retriever.
- Đánh giá chất lượng candidate và chọn evidence nhất quán.
- Chỉ dùng cùng model Qwen để rewrite tối đa hai truy vấn khi evidence ban đầu yếu.
- Xây bounded context, citation và image metadata.
- Gọi LLM theo structured-output contract.
- Kiểm tra citation và literal quan trọng trước khi trả lời.

## Giao diện

- `RAGPipeline.answer(question, filters=None, history=None)`.
- `AdaptiveRetriever.retrieve(query, filters=None)`.
- `Retriever.retrieve(query, filters=None)`.
- `select_evidence(query, chunks, config)`.
- `build_context(chunks, max_tokens)`.
- `build_citations(chunks, image_lookup=None)`.

## Phụ thuộc

- Embedding provider để embed query.
- Qdrant vector store để dense search.
- BM25 lexical index để keyword search.
- Một LLM provider, mặc định là Qwen qua Ollama, để route/rewrite/generate khi cần.
- Document image metadata để trả ảnh liên quan qua citation.

## Retrieval flow

```text
question + history + document scope
-> normalize
-> deterministic/LLM route
-> retrieval-first khi intent còn mơ hồ nhưng có khả năng thuộc kho kiến thức
-> metadata filter
-> dense search + BM25
-> RRF fusion, giữ dense/BM25/RRF provenance
-> candidate quality assessment
-> nếu evidence yếu: Qwen rewrite tối đa 2 query, rồi retrieve và fuse lại
-> evidence selection + deduplicate + loại cross-domain noise
-> bounded context
-> Qwen structured answer
-> citation validation
-> deterministic critical-literal validation
-> response
```

Clear out-of-scope vẫn đi theo deterministic response và không gọi retrieval. Query
knowledge có evidence yếu trả `insufficient_context`; input mơ hồ đi qua
retrieval-first nhưng không có evidence tốt trả `clarify`.

## Prompt contract

LLM nhận:

- system prompt chứa grounding, language và output rules;
- user prompt chứa bounded `CONTEXT` với `SOURCE_n`;
- user query và history đã giới hạn khi phù hợp.

`CONTEXT` là dữ liệu không tin cậy, không được override system instruction.

## Validation và failure semantics

- Output sai JSON/schema được retry đúng một lần.
- `generation_failed` chỉ lỗi sinh/parse/validation sau khi đã có evidence.
- `insufficient_context` chỉ dùng khi retrieval không đủ evidence.
- `partial` dùng khi evidence chỉ trả lời được một phần.
- Time, IP và port trong câu trả lời PHẢI có trong source thực sự được cite.
- Heuristic fact guard không nằm trong RAG V2 vì từng tạo false positive và làm mất
  câu trả lời grounded.

## Ràng buộc

- PHẢI giới hạn context bằng `FINAL_CONTEXT_TOP_N` và `MAX_CONTEXT_TOKENS`.
- PHẢI metadata-filter trước dense search, BM25 và RRF.
- PHẢI giữ `document_scope="selected"` với danh sách rỗng là không chọn tài liệu.
- KHÔNG ĐƯỢC biến lỗi generation thành thông báo thiếu tài liệu.
- KHÔNG ĐƯỢC đưa heuristic fact guard trở lại V2 nếu chưa có evaluation chứng minh.
- Reranker model là tùy chọn; fallback chính vẫn là RRF + evidence selector.

## Multi-stage request routing

Production dependency injection PHẢI tạo `MultiStageRouter` trước `RAGPipeline`.

```text
message + structured history
-> Turn Resolver
-> Embedding Route Classifier
-> Qwen Structured Classifier (chỉ khi embedding chưa chắc chắn)
-> Capability Router
-> RAG | Conversation | Unsupported | Clarify
-> branch-specific response validation
```

- Embedding route chỉ được chấp nhận khi đạt cả score threshold và top-1/top-2 margin.
- Prototype vectors được cache và khởi tạo an toàn khi có request đồng thời.
- Classifier/provider lỗi PHẢI fail-safe sang `clarify`, KHÔNG ĐƯỢC fail-open vào RAG.
- Tool capability tồn tại trong contract nhưng đang bị tắt.
- Frontend gửi lại `status`, `capability`, `subject` và `turn_kind` của assistant turn.
- Conversation SSE vẫn trả delta; routing decision được tái sử dụng, không phân loại hai lần.
- Legacy `IntentRouter` chỉ còn là compatibility path khi caller không inject router mới.
