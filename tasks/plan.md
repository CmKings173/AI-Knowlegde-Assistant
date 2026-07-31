# Kế hoạch triển khai: Retrieval RAG V2

## Tổng quan

Triển khai thiết kế tại
`docs/superpowers/specs/2026-07-31-rag-retrieval-v2-design.md` trên branch
`feature-rag-retrieval-v2`. Mục tiêu là giữ lại điểm retrieval gốc, chọn context
theo chất lượng evidence, ưu tiên retrieval trước với câu hỏi chưa rõ và chỉ dùng
chính Qwen để rewrite khi retrieval ban đầu yếu. Không thêm reranker model,
Infinity, Redis hoặc keyword vá riêng từng câu hỏi.

## Quyết định kiến trúc

- Baseline hành vi là commit `4721cf0`; trạng thái thử nghiệm cũ đã được bảo toàn.
- RRF chỉ tạo candidate, không được dùng như confidence score.
- Metadata người dùng chọn là hard filter; metadata suy luận chỉ là tín hiệu mềm.
- Logic đánh giá candidate và chọn evidence là pure Python để kiểm thử độc lập.
- Normal path gọi Qwen một lần; adaptive path dùng cùng Qwen để rewrite tối đa hai
  query trước khi generation.
- Fact guard heuristic không thuộc V2; validation chỉ kiểm tra điều deterministic.
- Mỗi lát cắt bắt đầu bằng test fail, sau đó mới có implementation tối thiểu.

## Dependency graph

```text
Evaluation schema/cases
        ↓
Retrieval provenance model
        ↓
Candidate quality + evidence selector
        ↓
Adaptive multi-query retrieval
        ↓
Retrieval-first pipeline orchestration
        ↓
Status/citation hardening
        ↓
End-to-end evaluation + review
```

## Task 1: Bộ evaluation có version trong Git

**Mô tả:** Chuyển evaluation từ dữ liệu runtime bị ignore thành contract được
version hóa; bổ sung các nhóm exact, paraphrase, colloquial, consequence,
procedure, broad, partial, unanswerable, out-of-scope, cross-domain và
document-scope.

**Tiêu chí chấp nhận:**

- Dataset có schema được validate và không chứa secret.
- Script báo lỗi rõ khi case thiếu ID, câu hỏi hoặc expected outcome.
- Report phân biệt retrieval hit, expected section, latency và nhóm hành vi.

**Kiểm chứng:**

- `uv run pytest tests/unit/test_retrieval_evaluation.py -q`
- `uv run ruff check scripts tests/unit/test_retrieval_evaluation.py --no-cache`

**Phụ thuộc:** Không.

**File dự kiến:**

- `tests/evaluation/rag_cases.json`
- `scripts/evaluate_retrieval.py`
- `tests/unit/test_retrieval_evaluation.py`

**Phạm vi:** Trung bình.

## Task 2: Giữ retrieval provenance qua RRF

**Mô tả:** Giữ dense score/rank, BM25 score/rank và RRF score cho mỗi chunk mà
không ghi đè mất tín hiệu gốc.

**Tiêu chí chấp nhận:**

- Candidate xuất hiện ở một hoặc cả hai retriever có provenance chính xác.
- RRF ranking hiện tại vẫn tương thích.
- Không lưu các trường transient vào Qdrant payload.

**Kiểm chứng:**

- `uv run pytest tests/unit/test_retrieval_v2.py -q`
- `uv run pytest tests/unit/test_core_logic.py -q`

**Phụ thuộc:** Task 1.

**File dự kiến:**

- `app/domain/models.py`
- `app/rag/hybrid_search.py`
- `app/rag/retriever.py`
- `tests/unit/test_retrieval_v2.py`

**Phạm vi:** Trung bình.

## Task 3: Candidate quality và evidence selector

**Mô tả:** Tạo module pure Python đánh giá độ nhất quán của candidate và chọn
context thay cho việc cắt `chunks[:N]`.

**Tiêu chí chấp nhận:**

- Loại chunk sai domain khi evidence đúng đã rõ và nhất quán.
- Giữ candidate mạnh từ query gốc, không hard-filter theo metadata suy luận.
- Deduplicate chunk và cho phép trả ít hơn giới hạn top-N.
- Kết quả giải thích được bằng reason code cho từng chunk.

**Kiểm chứng:**

- `uv run pytest tests/unit/test_evidence_selector.py -q`
- Regression test phải tái hiện context HR bị lẫn Windows trước khi code GREEN.

**Phụ thuộc:** Task 2.

**File dự kiến:**

- `app/rag/evidence_selector.py`
- `app/config.py`
- `tests/unit/test_evidence_selector.py`

**Phạm vi:** Trung bình.

## Checkpoint A

- Toàn bộ unit test backend pass.
- Ruff pass.
- Diff của ba task đầu được review về correctness, độ đơn giản và hiệu năng.
- Chưa thay đổi hành vi production pipeline nếu selector chưa được tích hợp.

## Task 4: Adaptive multi-query retrieval bằng cùng Qwen

**Mô tả:** Khi quality assessor báo candidate yếu hoặc lẫn domain, dùng Qwen trả
JSON rewrite tối đa hai query; hợp nhất query gốc và rewrite trong retrieval lần
hai. Rewrite lỗi phải fallback.

**Tiêu chí chấp nhận:**

- Query gốc luôn được giữ.
- Tối đa hai rewrite, có giới hạn ký tự và loại query rỗng/trùng.
- Timeout, JSON lỗi hoặc rewrite lỗi không làm request thất bại.
- Normal path không gọi rewrite.

**Kiểm chứng:**

- `uv run pytest tests/unit/test_adaptive_retrieval.py -q`
- Test chứng minh normal path không phát sinh LLM call bổ sung.

**Phụ thuộc:** Task 3.

**File dự kiến:**

- `app/rag/adaptive_retrieval.py`
- `app/rag/prompts.py`
- `app/rag/retriever.py`
- `tests/unit/test_adaptive_retrieval.py`

**Phạm vi:** Trung bình.

## Task 5: Tích hợp retrieval-first vào pipeline

**Mô tả:** Giảm routing keyword cho câu hỏi chưa rõ, tích hợp adaptive retrieval
và evidence selector vào knowledge path mà không phá greeting, continuation,
broad-section và explicit document scope.

**Tiêu chí chấp nhận:**

- Câu hỏi chưa rõ domain được thử retrieval trước khi bị từ chối.
- Final context dùng evidence selector, không cắt top-N mù.
- History chỉ hỗ trợ follow-up, không trở thành evidence.
- Trace ghi query, quality decision, chunk selected/rejected và lý do.

**Kiểm chứng:**

- `uv run pytest tests/unit/test_pipeline_retrieval_v2.py -q`
- `uv run pytest tests/unit/test_core_logic.py -q`

**Phụ thuộc:** Task 4.

**File dự kiến:**

- `app/rag/pipeline.py`
- `app/rag/intent_router.py`
- `app/rag/context_builder.py`
- `tests/unit/test_pipeline_retrieval_v2.py`

**Phạm vi:** Trung bình.

## Task 6: Chuẩn hóa failure status và citation validation

**Mô tả:** Không để generation lỗi giả thành thiếu tài liệu; chỉ giữ kiểm tra
literal/citation có thể chứng minh chắc chắn và loại fact guard heuristic khỏi
đường chạy V2.

**Tiêu chí chấp nhận:**

- `generation_failed`, `insufficient_context`, `partial` không bị trộn.
- Citation ID lạ hoặc không khớp inline bị từ chối.
- Thời gian, IP và port trong câu trả lời phải có trong source được cite.
- Không dùng semantic regex guard để chặn câu grounded.

**Kiểm chứng:**

- `uv run pytest tests/unit/test_response_validation_v2.py -q`
- `uv run pytest tests/unit/test_core_logic.py -q`

**Phụ thuộc:** Task 5.

**File dự kiến:**

- `app/rag/response_validator.py`
- `app/rag/pipeline.py`
- `tests/unit/test_response_validation_v2.py`

**Phạm vi:** Trung bình.

## Checkpoint B

- Unit test backend và metadata filter pass.
- Không có dependency mới.
- Normal path và adaptive path có test về số lần gọi Qwen.
- Các regression đã báo được tái hiện và xử lý theo hành vi tổng quát.

## Task 7: Evaluation end-to-end, tài liệu và review

**Mô tả:** Chạy bộ kiểm tra đầy đủ, đo baseline/V2 khi các service thật sẵn sàng,
cập nhật tài liệu RAG và thực hiện review năm trục.

**Tiêu chí chấp nhận:**

- Unit tests, lint, harness check và frontend build pass.
- Evaluation report ghi rõ metric đạt/chưa đạt; không hạ gate âm thầm.
- `ARCHITECTURE.md` và `PROGRESS.md` phản ánh đúng source.
- Không có secret, file runtime hoặc dữ liệu upload trong diff.

**Kiểm chứng:**

- `uv run ruff check . --no-cache`
- `uv run pytest tests/unit -q`
- `uv run python scripts/check_harness.py`
- `npm run build` trong `frontend/`
- `uv run python scripts/evaluate_retrieval.py` khi Qdrant/embedding hoạt động.

**Phụ thuộc:** Tasks 1–6.

**File dự kiến:**

- `app/rag/ARCHITECTURE.md`
- `app/rag/PROGRESS.md`
- `tasks/todo.md`
- Các report runtime không được commit.

**Phạm vi:** Trung bình.

## Rủi ro và kiểm soát

| Rủi ro | Mức độ | Kiểm soát |
|---|---:|---|
| Chọn context quá chặt làm mất recall | Cao | Giữ candidate mạnh của query gốc, hiệu chỉnh bằng holdout |
| Adaptive rewrite tăng latency | Cao | Chỉ chạy khi quality yếu; giới hạn một lần và hai query |
| Qwen rewrite sai | Trung bình | Giữ query gốc, schema nghiêm ngặt, fallback không lỗi request |
| Metadata ingestion sai | Cao | Inferred metadata chỉ là soft signal |
| Pipeline 1.400 dòng tiếp tục phình | Cao | Logic mới nằm trong module riêng; pipeline chỉ orchestration |
| Test fake không phản ánh production | Cao | Có tracked evaluation và smoke test với Qdrant thật |
| Evaluation phụ thuộc service ngoài | Trung bình | Unit gate luôn chạy; report E2E ghi rõ dependency bị thiếu |

## Open questions

Không còn câu hỏi blocking. Threshold cụ thể phải được đo và hiệu chỉnh từ
baseline/holdout, không được đặt chỉ dựa trên trực giác.

## Definition of Done

- Tất cả task và checkpoint hoàn thành.
- Mỗi thay đổi hành vi có test RED trước implementation.
- Full unit suite, lint, harness và frontend build pass.
- Evaluation report trung thực về các gate đạt/chưa đạt.
- Review không còn finding Critical hoặc Required.
- Feature branch sạch và sẵn sàng push; không merge trực tiếp vào `main`.
