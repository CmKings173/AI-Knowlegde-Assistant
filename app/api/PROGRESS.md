# API Progress

Last updated: 2026-07-30

## Current state

- Chat endpoint supports optional metadata filters.
- Chat filters include `document_scope` to distinguish searching all documents from searching only selected documents.
- Debug retrieve endpoint respects `DEBUG_ENDPOINTS_ENABLED`.
- Documents API supports add/upload, list, reindex, delete and safe image serving.
- Upload reads in chunks and enforces `MAX_UPLOAD_MB`.

## Verified

- Unit tests pass in `tests/unit`.
- Metadata filter schema conversion is covered, including `document_scope="selected"`.
- Stability tests cover image URL, upload/retrieval threshold and related delete behavior.

## Open work

- Add authentication/authorization before broader internal production rollout.
- Disable debug endpoints by default in production config.
- Standardize all `HTTPException` responses if a stricter API error contract is needed.
