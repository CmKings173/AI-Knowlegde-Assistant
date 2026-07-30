# Docker and Deployment Progress

Last updated: 2026-07-30

## Current state

- Compose chạy `qdrant`, `api`, `ui`.
- API image dùng uv/Python 3.11.
- UI image dùng React build + Nginx runtime.
- Qdrant có Docker volume `qdrant_data`.

## Verified

- Source configuration đã được audit bằng static inspection.
- Docker runtime trên Windows trước đó chưa ổn định nên chưa xác nhận full e2e bằng compose.

## Open work

- Cần verify Docker Compose thực tế trên GX10/HX10.
- Cần thêm reverse proxy ngoài cùng nếu muốn `http://ai.vtd.local`.
- Cần quyết định secrets/env management cho production nội bộ.
