# Todo: Retrieval RAG V2

## Chuẩn bị

- [x] Bảo toàn experiments tại `archive-rag-experiments-e931279`.
- [x] Revert regression trên `hotfix-restore-rag-baseline`.
- [x] Tạo branch `feature-rag-retrieval-v2`.
- [x] Viết và duyệt design spec tiếng Việt.
- [x] Duyệt implementation plan.

## Task 1: Evaluation contract

- [x] Viết test fail cho schema và report evaluation.
- [x] Thêm dataset có version theo nhóm hành vi.
- [x] Cập nhật script evaluation.
- [x] Chạy test và lint tập trung.
- [x] Commit lát cắt.

## Task 2: Retrieval provenance

- [x] Viết test fail cho dense/BM25/RRF provenance.
- [x] Giữ score và rank gốc qua fusion.
- [x] Giữ tương thích với pipeline hiện tại.
- [x] Chạy focused và regression tests.
- [x] Commit lát cắt.

## Task 3: Evidence selector

- [x] Viết test tái hiện HR context bị lẫn Windows.
- [x] Viết test recall, dedup và soft metadata.
- [x] Implement candidate quality assessor.
- [x] Implement evidence selector với reason code.
- [x] Chạy Checkpoint A và commit.

## Task 4: Adaptive retrieval

- [x] Viết test normal path không gọi rewrite.
- [x] Viết test weak path dùng cùng Qwen rewrite.
- [x] Viết test rewrite lỗi fallback query gốc.
- [x] Implement schema/prompt và multi-query fusion.
- [x] Chạy focused tests và commit.

## Task 5: Pipeline retrieval-first

- [x] Viết regression test cho câu chưa có keyword domain.
- [x] Viết test document scope, history và broad-section.
- [x] Tích hợp quality, adaptive retrieval và selector.
- [x] Thêm trace selected/rejected reason.
- [x] Chạy focused tests và commit.

## Task 6: Status và validation

- [x] Viết test phân biệt generation failure với thiếu context.
- [x] Viết test citation và critical literal.
- [x] Tắt fact guard heuristic khỏi V2 path.
- [x] Chạy Checkpoint B và commit.

## Task 7: Kiểm chứng và review

- [x] Chạy Ruff toàn repo.
- [x] Chạy toàn bộ unit tests.
- [x] Chạy harness check.
- [x] Build frontend.
- [x] Chạy evaluation với service thật nếu sẵn sàng.
- [x] Cập nhật `ARCHITECTURE.md` và `PROGRESS.md`.
- [x] Review correctness, readability, architecture, security và performance.
- [x] Xử lý toàn bộ finding Critical/Required.
- [x] Xác nhận branch sạch và chuẩn bị push.
