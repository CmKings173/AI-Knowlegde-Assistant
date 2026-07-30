# Frontend Architecture

Frontend là giao diện người dùng cho AI Knowledge Assistant.

## Trách nhiệm

- Hiển thị giao diện chat nội bộ.
- Gửi câu hỏi tới FastAPI qua `/api/v1/chat`.
- Hiển thị câu trả lời, citation và ảnh liên quan.
- Cho phép người dùng upload tài liệu qua API documents.
- Build thành static assets để Nginx serve trong UI container.

## Giao diện

- Runtime dev: `npm run dev` trên port `5173`.
- Production build: `npm run build`.
- Docker UI: static files được copy vào `/usr/share/nginx/html`.
- API calls đi qua Nginx proxy trong `docker/nginx.ui.conf`.

## Phụ thuộc

- React `^19.2.8`.
- TypeScript `^5.9.3`.
- Vite `^8.1.5`.
- `@assistant-ui/react` `^0.15.1`.
- FastAPI backend qua `/api`.

## Ràng buộc

- PHẢI coi mọi response từ API là dữ liệu không tin cậy trước khi render.
- KHÔNG ĐƯỢC hard-code API host trong production UI; dùng proxy hoặc env/config.
- PHẢI giữ citation và ảnh liên quan khi hiển thị câu trả lời RAG.
- KHÔNG ĐƯỢC đưa secret/API key vào bundle frontend.
