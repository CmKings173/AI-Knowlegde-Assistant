# Progress

Last updated: 2026-07-29

## Current state

- FastAPI backend, React assistant-ui frontend, dynamic DOCX ingestion, Qdrant
  vector store, BM25, RRF hybrid retrieval, citations, and related image return
  are implemented.
- API can run through the Python entrypoint; UI can run with `uv run python ui.py`
  or `npm run dev` from `frontend/`.
- Docker UI now builds the React frontend and serves it through Nginx, proxying API
  calls to the `api` service.
- React UI selects all ingested documents by default; document checkboxes are now
  optional scope filters.
- RAG pipeline logs intent, branch, retrieval, context, and response metadata for
  request tracing without logging secrets or continuation tokens.
- Short messages after chat history, including "tiep di", are routed as follow-up
  turns instead of returning the static greeting.
- Conversational turns now use the LLM without retrieval instead of returning a
  static greeting, so replies can use recent chat history and sound less mechanical.
- Metadata filtering is implemented before dense search, BM25 search, and RRF fusion.
- Agent harness has been added so future sessions can recover project state from repo.
- Retrieval threshold is calibrated for RRF score scale (`MIN_RETRIEVAL_SCORE=0.01`).
- Document images are served through a constrained API endpoint instead of mounting
  the whole document storage tree.
- Delete now removes global chunk snapshots and does not silently proceed if Qdrant
  delete cannot confirm collection state.

## Verified recently

- `uv run ruff check . --no-cache`
- `uv run pytest tests/unit`
- `npm run build` from `frontend/`
- Dynamic ingestion smoke test passed with fake vector store for a copied seed DOCX:
  parse, image extraction, chunks, manifest, idempotent re-add.

## Known limitations

- Docker/Qdrant real runtime was not fully verified on the Windows machine because
  Docker Desktop/Linux engine was unstable.
- Reranker model is configured but not implemented; retrieval currently uses dense
  search + BM25 + RRF top-k.
- No authentication, authorization, rate limit, Redis cache, or production queue yet.
- Frontend currently uses request/response chat over the existing REST API; token
  streaming is not implemented yet.

## Open engineering follow-ups

- Add stronger ingestion job semantics/background queue for concurrent uploads.
- Optimize BM25 metadata filtering for large corpora; current implementation may
  rebuild a filtered BM25 index per filtered request.
- Add claim-level answer verification if higher anti-hallucination assurance is needed.
