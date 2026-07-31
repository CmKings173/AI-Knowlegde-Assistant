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

- [ ] Viết test fail cho dense/BM25/RRF provenance.
- [ ] Giữ score và rank gốc qua fusion.
- [ ] Giữ tương thích với pipeline hiện tại.
- [ ] Chạy focused và regression tests.
- [ ] Commit lát cắt.

## Task 3: Evidence selector

- [ ] Viết test tái hiện HR context bị lẫn Windows.
- [ ] Viết test recall, dedup và soft metadata.
- [ ] Implement candidate quality assessor.
- [ ] Implement evidence selector với reason code.
- [ ] Chạy Checkpoint A và commit.

## Task 4: Adaptive retrieval

- [ ] Viết test normal path không gọi rewrite.
- [ ] Viết test weak path dùng cùng Qwen rewrite.
- [ ] Viết test rewrite lỗi fallback query gốc.
- [ ] Implement schema/prompt và multi-query fusion.
- [ ] Chạy focused tests và commit.

## Task 5: Pipeline retrieval-first

- [ ] Viết regression test cho câu chưa có keyword domain.
- [ ] Viết test document scope, history và broad-section.
- [ ] Tích hợp quality, adaptive retrieval và selector.
- [ ] Thêm trace selected/rejected reason.
- [ ] Chạy focused tests và commit.

## Task 6: Status và validation

- [ ] Viết test phân biệt generation failure với thiếu context.
- [ ] Viết test citation và critical literal.
- [ ] Tắt fact guard heuristic khỏi V2 path.
- [ ] Chạy Checkpoint B và commit.

## Task 7: Kiểm chứng và review

- [ ] Chạy Ruff toàn repo.
- [ ] Chạy toàn bộ unit tests.
- [ ] Chạy harness check.
- [ ] Build frontend.
- [ ] Chạy evaluation với service thật nếu sẵn sàng.
- [ ] Cập nhật `ARCHITECTURE.md` và `PROGRESS.md`.
- [ ] Review correctness, readability, architecture, security và performance.
- [ ] Xử lý toàn bộ finding Critical/Required.
- [ ] Xác nhận branch sạch và chuẩn bị push.
