# API Progress

Last updated: 2026-07-30

## Current state

- Chat endpoint hỗ trợ optional metadata filters.
- Debug retrieve endpoint tôn trọng `DEBUG_ENDPOINTS_ENABLED`.
- Documents API hỗ trợ add/upload, list, reindex, delete và serve image an toàn.
- Upload đọc theo chunk và giới hạn `MAX_UPLOAD_MB`.

## Verified

- Unit tests pass trong `tests/unit`.
- Metadata filter schema conversion có test.
- Stability tests cover image URL, upload/retrieval threshold và delete behavior liên quan.

## Open work

- Thêm authentication/authorization trước khi mở rộng production nội bộ.
- Tắt debug endpoint mặc định trong production config.
- Chuẩn hóa error response cho mọi `HTTPException` nếu cần API contract chặt hơn.
