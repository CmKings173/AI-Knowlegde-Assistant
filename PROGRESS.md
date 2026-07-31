# Progress

Last updated: 2026-07-31

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
- Production chat routing now uses Turn Resolver, embedding classification, Qwen
  structured fallback, and an explicit Capability Router before branch execution.
- External requests and conversation repairs no longer default to retrieval.
- Frontend history carries structured routing state for follow-up resolution.
- Conversation responses now use guarded Vietnamese streaming with prefix validation,
  one clean retry, and a fixed Vietnamese fallback.
- RAG responses remain fully buffered for structured-output and citation validation.
- RAG end-to-end evaluation harness is implemented at deterministic-core level:
  dataset schema, response scoring, first-failure-stage classification, and live
  `scripts/evaluate_rag.py` runner.

## Verified recently

- `uv run ruff check . --no-cache`
- `uv run pytest tests/unit`
- `uv run python -m pytest tests/unit/test_rag_e2e_evaluation.py tests/unit/test_retrieval_evaluation.py -q`
- `npm run build` from `frontend/`
- Dynamic ingestion smoke test passed with fake vector store for a copied seed DOCX:
  parse, image extraction, chunks, manifest, idempotent re-add.

## Known limitations

- Docker/Qdrant real runtime was not fully verified on the Windows machine because
  Docker Desktop/Linux engine was unstable.
- Reranker model is configured but not implemented; retrieval currently uses dense
  search + BM25 + RRF top-k.
- No authentication, authorization, rate limit, Redis cache, or production queue yet.
- Live e2e RAG evaluation still needs to be run on GX10 or another environment
  with Qdrant, embeddings, and Ollama available.

## Open engineering follow-ups

- Add stronger ingestion job semantics/background queue for concurrent uploads.
- Optimize BM25 metadata filtering for large corpora; current implementation may
  rebuild a filtered BM25 index per filtered request.
- Add claim-level answer verification if higher anti-hallucination assurance is needed.
