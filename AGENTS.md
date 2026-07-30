# Agent Harness

This repository is the system of record. If a decision, constraint, command, or
current status is not written here, future agents should treat it as unknown and
rediscover or ask.

## What this system is

AI Knowledge Assistant is an internal Vietnamese-first RAG chatbot for company
knowledge documents. It ingests DOCX files at runtime, extracts text/tables/images,
chunks text, embeds chunks, indexes vectors in Qdrant, and answers through a local
or API-backed LLM with citations and related images.

## How the repo is organized

- `app/api/` — FastAPI routes, request/response schemas, dependency wiring.
- `app/ingestion/` — unified document ingestion pipeline for seed and future docs.
- `app/rag/` — retrieval, context building, prompt construction, citation validation.
- `app/providers/` — LLM, embedding, and vector-store integrations.
- `frontend/` - React assistant-ui frontend.
- `ui.py` - local launcher for the React development server.
- `scripts/` — CLI operations for ingest, reindex, evaluation, and harness checks.
- `data/` — runtime storage; real uploads and processed docs are ignored by git.
- `tests/` — unit and future integration tests.
- `tasks/` — working plans and task notes.

Read the local `ARCHITECTURE.md` beside a module before changing that module.
Read `CONSTRAINTS.md` before changing ingestion, retrieval, storage, or deployment.
Read `PROGRESS.md` at the start and update it when durable project state changes.

## Tech stack versions

These versions are the current source-of-record from checked-in config:

| Area | Technology | Version / constraint |
|---|---|---|
| Runtime | Python | `>=3.11` |
| Package manager | uv | lockfile-managed via `uv.lock` |
| API | FastAPI | `>=0.115.0` |
| API server | Uvicorn | `>=0.30.0` |
| Config | pydantic-settings | `>=2.4.0` |
| DOCX parsing | python-docx | `>=1.1.2` |
| Vector DB client | qdrant-client | `>=1.11.0` |
| Vector DB service | Qdrant | `qdrant/qdrant:v1.12.1` |
| HTTP client | httpx | `>=0.27.0` |
| Lexical retrieval | rank-bm25 | `>=0.2.2` |
| Frontend runtime | Node.js | `node:22-alpine` in Docker |
| Frontend | React | `^19.2.8` |
| Frontend build | Vite | `^8.1.5` |
| Frontend language | TypeScript | `^5.9.3` |
| UI assistant components | `@assistant-ui/react` | `^0.15.1` |
| UI web server | Nginx | `nginx:1.27-alpine` |
| Local LLM | Ollama | model from `.env`, default `qwen2.5:3b-instruct` |

## How to run it

```powershell
uv sync
cd frontend
npm install
cd ..
docker compose up -d qdrant
uv run api
```

In another terminal:

```powershell
uv run python ui.py
```

Local smoke-test config can use:

```env
EMBEDDING_PROVIDER=hash
LLM_PROVIDER=echo
```

Production-like config should use Qdrant plus a real embedding provider and Ollama
or another configured LLM.

## How to verify it

Fast local gate:

```powershell
uv run ruff check . --no-cache
uv run pytest tests/unit
cd frontend
npm run build
cd ..
uv run python scripts/check_harness.py
```

Equivalent Make targets:

```powershell
make lint
make test
make harness-check
make check
```

For ingestion changes, also run a DOCX add/re-add/delete/reindex smoke test against
Qdrant when Docker is healthy.

## Current progress

`PROGRESS.md` is the durable progress file. Treat chat history as ephemeral.
Before declaring success, ensure the relevant verification commands have passed and
record any known blockers or follow-up work there.

## Hard rules for agents

- PHẢI coi repo là system of record; chat history chỉ là ngữ cảnh tạm thời.
- PHẢI đọc `CONSTRAINTS.md` trước khi đổi ingestion, retrieval, storage hoặc deployment.
- PHẢI đọc `ARCHITECTURE.md` và `PROGRESS.md` trong service/module liên quan trước khi sửa.
- PHẢI cập nhật service-level `PROGRESS.md` khi trạng thái công việc bền vững thay đổi.
- KHÔNG ĐƯỢC hard-code seed documents.
- KHÔNG ĐƯỢC commit `.env`, `.venv`, uploaded docs, processed docs hoặc extracted images.
- PHẢI dùng `uv` thay cho `pip` trong workflow Python local.
- PHẢI giữ câu trả lời RAG grounded; nếu context không đủ thì từ chối thay vì bịa.
