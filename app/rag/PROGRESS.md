# RAG Progress

Last updated: 2026-07-31

## Current state

- Retrieval uses dense Qdrant search, BM25, and RRF while preserving raw
  dense/BM25/RRF provenance.
- Metadata filtering runs before dense search, BM25 search, and fusion.
- `document_scope="selected"` with empty `document_ids` does not search the whole
  knowledge base.
- Evidence selector removes duplicate and cross-domain noise and records reason
  codes in trace.
- Ambiguous internal queries use retrieval-first behavior instead of relying on
  an ever-growing domain keyword list.
- Weak evidence can trigger adaptive rewrite with the same Qwen model, up to two
  rewritten queries; rewrite failure falls back to candidates from the original
  query.
- Context is bounded by `FINAL_CONTEXT_TOP_N` and `MAX_CONTEXT_TOKENS`.
- Prompt contract is system prompt + bounded context + user query/history.
- Citation is mandatory for sourced answers; time, IP, and port literals must
  appear in cited evidence.
- The old heuristic fact guard has been removed from RAG V2 because it produced
  false positives.
- Parse/generation failures return `generation_failed` and are not disguised as
  missing documents.
- Trace API keeps compatibility fields and adds diagnostics for retrieval V2,
  multi-stage routing, guarded streaming, and evaluation.

## Verified

- Previous full gate passed with backend unit tests, Ruff, harness check, and
  frontend production build.
- Retrieval evaluation previously reached recall@K `1.0`, MRR `0.9583` on 12
  retrieval cases, with average retrieval latency `703.39 ms`.
- Focused e2e evaluation tests passed: `26 passed` for
  `tests/unit/test_rag_e2e_evaluation.py` and
  `tests/unit/test_retrieval_evaluation.py`.

## Multi-stage router

- Production pipeline uses Turn Resolver, embedding route classifier, Qwen
  structured fallback, and Capability Router.
- External requests and conversation repair no longer default to retrieval.
- Tool execution remains disabled.
- Structured conversation state is sent from frontend to backend.
- Conversation SSE keeps delta streaming and routes once per request.
- Prototype embedding cache has duplicate-initialization protection for
  concurrent requests.
- Observability, metrics, and threshold calibration remain separate follow-up
  work.

## Guarded Vietnamese streaming

- Conversation keeps a 30-character prefix buffer before emitting the first
  delta.
- Deterministic language guard rejects CJK and invalid mixed-script output while
  allowing short technical literals and acronyms.
- Invalid prefix retries exactly once with a clean prompt; repeated failure uses
  a fixed Vietnamese fallback instead of changing to out-of-scope.
- Mid-stream invalid fragments are not emitted.
- Conversation final answer equals the concatenation of emitted deltas.
- RAG still buffers structured JSON for citation/literal validation.

## RAG end-to-end evaluation harness

- Deterministic e2e evaluation core is implemented: extended case schema,
  response scoring, citation/language checks, and first-failure-stage
  classification.
- Live runner is available:
  `uv run python scripts/evaluate_rag.py`.
- Runner supports `--case-id`, `--category`, and `--limit`.
- Runner writes generated reports to `data/evaluation/rag_e2e_report.json` and
  `data/evaluation/rag_e2e_summary.md`.
- Retrieval-only evaluator remains backward compatible with
  `tests/evaluation/rag_cases.json`.

## Open work

- Run live e2e evaluation on GX10 with Qdrant, embedding provider, and Ollama:
  `uv run python scripts/evaluate_rag.py --limit 3`, then full dataset.
- Add a typed evaluation trace collector if deeper separation between retrieval
  and evidence selection is needed beyond citation-level selected sources.
- Benchmark concurrency on GX10 before final production SLO.
- `bge-reranker-v2-m3` is not enabled; fallback remains RRF + evidence selector.
- BM25 filtered search may rebuild a filtered index per request; benchmark when
  corpus or concurrency grows.
- Claim-level semantic verification needs a separate design if added later.
