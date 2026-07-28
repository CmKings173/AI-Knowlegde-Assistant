# API Architecture

The API layer exposes the stable interface for UI, scripts, and external clients.

## Responsibilities

- Validate request boundaries with Pydantic schemas.
- Route chat, document ingestion, document list, reindex, delete, health, and debug
  retrieval requests.
- Keep endpoint behavior backward compatible where possible.
- Convert API request shapes into internal domain objects.

## Current endpoints

- `POST /api/v1/chat`
- `POST /api/v1/debug/retrieve`
- `GET /api/v1/documents`
- `POST /api/v1/documents`
- `POST /api/v1/documents/{document_id}/reindex`
- `DELETE /api/v1/documents/{document_id}`
- `GET /health`

## Constraints

- `ChatRequest.filters` is optional and must remain backward compatible.
- Upload must trigger ingestion, not just file storage.
- Debug endpoints must respect `DEBUG_ENDPOINTS_ENABLED`.
- Do not leak secrets, raw internal errors, or unintended storage paths.
