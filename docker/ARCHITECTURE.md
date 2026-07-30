# Docker and Deployment Architecture

Docker layer định nghĩa topology chạy production-like của hệ thống.

## Trách nhiệm

- Build API image.
- Build UI image.
- Chạy Qdrant vector database.
- Mount runtime data vào API container.
- Expose các port phục vụ nội bộ.

## Giao diện

- Qdrant: `6333`.
- API: `8000`.
- UI: `8501`.
- UI Nginx proxy:
  - `/api/*` tới `api:8000/api/*`.
  - `/health` tới `api:8000/health`.

## Phụ thuộc

- `qdrant/qdrant:v1.12.1`.
- `ghcr.io/astral-sh/uv:python3.11-bookworm` cho API image.
- `node:22-alpine` cho frontend build stage.
- `nginx:1.27-alpine` cho UI image.
- Ollama host service khi dùng local LLM.

## Ràng buộc

- PHẢI persist Qdrant bằng Docker volume.
- PHẢI mount `./data:/app/data` cho runtime document storage.
- KHÔNG ĐƯỢC bake `.env`, uploaded docs hoặc processed docs vào image.
- NÊN thêm reverse proxy ngoài cùng như Caddy/Nginx nếu muốn domain nội bộ không có port.
