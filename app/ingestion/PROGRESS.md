# Ingestion Progress

Last updated: 2026-07-30

## Current state

- Unified ingestion pipeline xử lý seed docs và documents thêm sau.
- Pipeline lưu original file, parse DOCX/MD/TXT, extract DOCX images, chunk, embed, index Qdrant và publish manifest.
- Idempotency theo file hash đã có.
- Reindex xóa vector cũ trước khi index chunk mới.

## Verified

- Dynamic ingestion smoke test đã pass với fake vector store cho DOCX seed copy.
- Unit tests cover chunking, metadata, citation, harness và stability behavior.

## Open work

- Cần verify lại end-to-end với Qdrant thật khi Docker environment ổn định.
- Cần background job/queue nếu nhiều người upload đồng thời.
- Cần harden thêm rollback/transaction semantics cho failure giữa các bước parse/embed/index.
