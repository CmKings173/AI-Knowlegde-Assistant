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
- Intent routing treats deterministic rules as fast-path only for confident cases; low-confidence non-domain statements, ambiguous questions and casual follow-ups are escalated to the semantic LLM router before choosing conversation/refusal.
- Semantic router prompt explicitly treats ordinary HR/internal policy language such as xin nghỉ, nghỉ việc, vắng mặt, bàn giao and kỷ luật as internal knowledge candidates that should use RAG.
- Fact guard checks cited context first, then falls back to full CONTEXT to avoid false positives when the fact is present but the model citation is incomplete.
- Fact guard rejects unsupported procedural support terms such as manager approval and reason-submission claims when cited context does not contain them.
- High-risk procedural/policy deterministic queries run through a lightweight evidence relevance gate before LLM generation.
- Optional HTTP reranker wiring is available behind `RERANKER_ENABLED`; default remains disabled until a self-hosted `/rerank` endpoint is configured.

## Verified

- Unit tests cover RRF, optional reranker wiring, citation validation, refusal logic, out-of-scope UX, semantic-router rescue for HR policy wording, relevance gate behavior, fact guard false positives and metadata filtering.
- `MIN_RETRIEVAL_SCORE` is `0.01` to match RRF score scale.

## Open work

- Reranker service is not enabled by default; production needs TEI/Infinity or another compatible `/rerank` endpoint before setting `RERANKER_ENABLED=true`.
- BM25 filtered search may rebuild a filtered index per request; optimize when corpus grows.
- Add stronger LLM/NLI claim-level verification if hallucination resistance needs to go beyond the current procedural support-term guard.
