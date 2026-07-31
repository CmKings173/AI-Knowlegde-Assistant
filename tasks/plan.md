# Implementation Plan: Multi-stage Router

## Overview

Triển khai spec
`docs/superpowers/specs/2026-07-31-multistage-router-design.md` trên branch
`feature-multistage-router`. Thay semantic keyword routing bằng các component typed,
giữ pipeline RAG hiện tại làm branch execution và không thêm dependency/model mới.

## Architecture Decisions

- Turn resolver không gọi LLM; trạng thái chưa chắc chắn được xử lý trong cùng một
  Qwen structured classifier call.
- Embedding classifier dùng threshold và top-1/top-2 margin; dưới ngưỡng không chọn
  route.
- Intent và capability là hai contract riêng.
- Capability Router luôn có `unsupported` và `clarify`; không ép vào ba branch gần nhất.
- Tool disabled mặc định.
- Component mới nằm ngoài `pipeline.py` để không làm file orchestration lớn hơn.

## Dependency Graph

```text
Typed contracts
  -> Turn resolver
  -> Embedding classifier
  -> Qwen parser/classifier
  -> Capability router
  -> Pipeline integration
  -> API/frontend conversation state
  -> full verification and review
```

## Phase 1: Foundation

### Task 1: Typed contracts and turn resolution

**Acceptance criteria:**

- Typed intent, affinity, capability và turn-resolution contracts tồn tại.
- Repair/continuation/follow-up/independent được phân biệt bằng state có cấu trúc.
- Không gọi LLM hoặc retriever.

**Verification:**

- `uv run pytest tests/unit/test_multistage_router.py -q`

**Files:** `app/rag/routing/models.py`, `app/rag/routing/turn_resolver.py`,
`tests/unit/test_multistage_router.py`.

### Task 2: Embedding classifier

**Acceptance criteria:**

- Prototype vectors cache sau lần đầu.
- Route chỉ confident khi đạt threshold và margin.
- Provider lỗi trả decision chưa chắc chắn, không làm request fail.

**Verification:**

- `uv run pytest tests/unit/test_multistage_router.py -q`

**Files:** `app/rag/routing/embedding_classifier.py`,
`tests/unit/test_multistage_router.py`, `app/config.py`.

## Checkpoint A

- Router foundation tests pass.
- Không dependency mới.
- Production pipeline chưa đổi hành vi.

## Phase 2: Structured fallback and capability

### Task 3: Qwen structured classifier

**Acceptance criteria:**

- Prompt phân loại intent/capability hint theo JSON contract.
- Parser từ chối malformed/unknown output.
- LLM/provider failure trả unknown decision để Capability Router clarify.

**Verification:**

- `uv run pytest tests/unit/test_multistage_router.py -q`

**Files:** `app/rag/routing/structured_classifier.py`, `app/rag/prompts.py`,
`tests/unit/test_multistage_router.py`.

### Task 4: Capability Router

**Acceptance criteria:**

- RAG, conversation, unsupported, clarify được map rõ ràng.
- Tool disabled mặc định.
- Không có default sang RAG.

**Verification:**

- `uv run pytest tests/unit/test_multistage_router.py -q`

**Files:** `app/rag/routing/capability_router.py`,
`tests/unit/test_multistage_router.py`.

## Checkpoint B

- Mọi route decision test pass.
- GitHub chỉ xuất hiện trong regression test.

## Phase 3: Pipeline integration

### Task 5: Integrate routing orchestrator

**Acceptance criteria:**

- Pipeline dùng multi-stage route trước branch execution.
- External và repair không retrieval.
- Internal knowledge vẫn đi RAG và giữ filter.
- Structured classifier chỉ gọi khi embedding chưa chắc chắn.

**Verification:**

- `uv run pytest tests/unit/test_pipeline_multistage_router.py -q`
- `uv run pytest tests/unit/test_pipeline_retrieval_v2.py -q`

**Files:** `app/rag/routing/router.py`, `app/rag/pipeline.py`,
`app/api/deps.py`, `tests/unit/test_pipeline_multistage_router.py`.

### Task 6: Branch-specific guard and conversation state

**Acceptance criteria:**

- Status contract nhất quán theo branch.
- History có optional route/status/capability metadata.
- Existing client vẫn tương thích khi metadata không có.

**Verification:**

- `uv run pytest tests/unit/test_response_validation_v2.py -q`
- `uv run pytest tests/unit/test_core_logic.py -q`
- `npm run build` trong `frontend/`

**Files:** `app/api/schemas.py`, `frontend/src/types.ts`,
`frontend/src/chat-runtime.tsx`, `app/rag/pipeline.py`, tests liên quan.

## Phase 4: Verification and documentation

### Task 7: Full gate and review

**Acceptance criteria:**

- Full unit suite, Ruff, harness và frontend build pass.
- RAG architecture/progress phản ánh đúng source.
- Không secret/runtime data/dependency mới trong diff.
- Không còn finding Critical/Required.

**Verification:**

```powershell
uv run pytest tests/unit -q
uv run ruff check . --no-cache
uv run python scripts/check_harness.py
cd frontend
npm run build
```

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---:|---|
| Hash fake không phản ánh semantic model | Cao | Fake vector kiểm soát score/margin; regression pipeline dùng structured fallback |
| Qwen classifier tăng latency | Cao | Chỉ gọi khi embedding chưa chắc chắn, output ngắn |
| Embedding classifier tự tin sai | Cao | Per-route threshold + margin, fail-safe không route gần nhất |
| Legacy tests phụ thuộc keyword router | Cao | Giữ compatibility adapter trong increment đầu, chuyển từng behavior |
| Pipeline tiếp tục phình | Cao | Component mới ở package `app/rag/routing` |
| History cũ thiếu metadata | Trung bình | Optional fields và Turn Resolver fallback an toàn |

## Open Questions

Không có câu hỏi blocking. Metrics, calibration dataset và observability được tách
ra thay đổi sau theo yêu cầu.

## Definition of Done

- Mọi behavior mới có test RED trước implementation.
- Mọi task/checkpoint hoàn tất.
- Không retrieval cho external rõ ràng và repair.
- Không regression RAG/filter/citation/continuation.
- Full verification pass và review không còn finding bắt buộc.
