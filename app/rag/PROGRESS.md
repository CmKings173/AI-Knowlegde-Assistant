# RAG Progress

Last updated: 2026-07-30

## Current state

- Retrieval uses dense Qdrant search + BM25 lexical search + RRF fusion.
- Metadata filtering is applied before dense search, BM25 search and RRF.
- `document_scope="selected"` with `document_ids=[]` does not search the whole corpus; it returns a clarify response.
- Final context is bounded by `FINAL_CONTEXT_TOP_N` and `MAX_CONTEXT_TOKENS`.
- Prompt contract is system prompt + bounded CONTEXT + user query.
- Citation validator removes unknown `SOURCE_n`.
- Out-of-scope policy returns deterministic responses by subtype and recent history to avoid repetitive robotic refusals.
- Fact guard checks cited context first, then falls back to full CONTEXT to avoid false positives when the fact is present but the model citation is incomplete.

## Verified

- Unit tests cover RRF, citation validation, refusal logic, out-of-scope UX, fact guard false positives and metadata filtering.
- `MIN_RETRIEVAL_SCORE` is `0.01` to match RRF score scale.

## Open work

- Reranker model is still a placeholder; `bge-reranker-v2-m3` is not enabled as a real provider yet.
- BM25 filtered search may rebuild a filtered index per request; optimize when corpus grows.
- Add stronger claim-level verification if hallucination resistance needs to go beyond the current fact guard.
