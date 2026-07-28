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
- `ui/` — Streamlit UI.
- `scripts/` — CLI operations for ingest, reindex, evaluation, and harness checks.
- `data/` — runtime storage; real uploads and processed docs are ignored by git.
- `tests/` — unit and future integration tests.
- `tasks/` — working plans and task notes.

Read the local `ARCHITECTURE.md` beside a module before changing that module.
Read `CONSTRAINTS.md` before changing ingestion, retrieval, storage, or deployment.
Read `PROGRESS.md` at the start and update it when durable project state changes.

## How to run it

```powershell
uv sync
docker compose up -d qdrant
uv run api
```

In another terminal:

```powershell
uv run ui
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

- Store document is not ingest document. Upload must run the unified ingestion pipeline.
- Do not hard-code the original seed documents; they are ordinary documents.
- Do not commit `.env`, `.venv`, uploaded DOCX files, processed document data, or images.
- Prefer `uv` over `pip` for local Python dependency workflows.
- Keep retrieval grounded: if context is insufficient, refuse rather than invent.
- Update nearby docs when code changes alter module responsibilities or constraints.
