# Frontend Progress

Last updated: 2026-07-30

## Current state

- Frontend React/Vite tồn tại trong `frontend/`.
- Docker UI build dùng Node build stage và Nginx runtime.
- UI Nginx proxy `/api` và `/health` về API container.

## Verified

- `npm run build` được ghi trong harness verification command.
- Dockerfile UI có production static serving path.

## Open work

- Cần kiểm tra UX đầy đủ với skill `impeccable` nếu muốn polish UI.
- Cần runtime browser verification cho chat/upload/citation images.
- Cần quyết định domain nội bộ/reverse proxy ngoài cùng nếu bỏ port `8501`.
