# API Architecture

API service expose giao diện ổn định cho frontend, scripts và các client nội bộ.

## Trách nhiệm

- Validate request boundary bằng Pydantic schemas.
- Route chat, debug retrieval, document add/list/reindex/delete và health check.
- Convert API request shape thành domain objects nội bộ.
- Giữ endpoint behavior backward compatible khi có thể.
- Serve extracted document images qua endpoint có validate path.

## Giao diện

- `POST /api/v1/chat`
- `POST /api/v1/debug/retrieve`
- `GET /api/v1/documents`
- `POST /api/v1/documents`
- `POST /api/v1/documents/upload`
- `POST /api/v1/documents/{document_id}/reindex`
- `DELETE /api/v1/documents/{document_id}`
- `GET /api/v1/documents/{document_id}/images/{file_name}`
- `GET /health`

## Phụ thuộc

- `app.ingestion` để ingest/reindex documents.
- `app.rag` để trả lời chat và debug retrieve.
- `app.providers` để dùng embedding/vector store/LLM.
- `app.documents` để đọc/ghi manifest, image metadata và storage.

## Ràng buộc

- PHẢI upload bằng ingestion pipeline, không được store-only.
- PHẢI giữ `ChatRequest.filters` optional để không phá client cũ.
- PHẢI tôn trọng `DEBUG_ENDPOINTS_ENABLED`.
- KHÔNG ĐƯỢC leak secret, raw internal errors hoặc unintended storage paths.
