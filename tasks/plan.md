# Implementation Plan: Generic Evidence-Gated Retrieval

## Overview

Improve RAG hallucination resistance without adding endless domain-specific keyword rules. The system now prefers generic evidence controls: optional reranking, pre-generation evidence relevance checks for high-risk procedural/policy queries, and post-generation support-term validation for cited procedural claims.

## Architecture Decisions

- Keep deterministic intent rules as fast paths only; do not add a growing HR/leave-specific rule list.
- Use semantic routing for uncertain cases.
- Add a lightweight evidence relevance gate for high-risk procedural/policy deterministic queries.
- Extend fact validation so important procedural claims in the answer must be present in the cited context.
- Wire reranking as an optional `/rerank` provider, disabled by default until a real self-hosted endpoint is configured.

## Task List

### Phase 1: Guard the reported hallucination

- [x] Add regression tests for a query where retrieved context is near but not sufficient.
- [x] Extend fact/evidence validation so cited context must contain important answer claims such as manager permission/reason/procedure terms.

### Phase 2: Generic retrieval quality controls

- [x] Add a reusable relevance gate that can reject weak procedural/policy evidence before LLM generation.
- [x] Surface the relevance gate decision in response trace.
- [x] Keep the gate narrow enough to avoid blocking normal technical-guide retrieval.

### Phase 3: Reranker readiness and docs

- [x] Wire the existing reranker abstraction into retriever behavior when enabled.
- [x] Document self-hosted `bge-reranker-v2-m3` configuration for GX10.
- [x] Update RAG/provider progress docs and ADR.

### Checkpoint

- [x] `uv run ruff check . --no-cache`
- [x] `uv run pytest`
- [x] `uv run python scripts/check_harness.py`
- [x] `npm run build` from `frontend/`

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Relevance gate is too strict | False `insufficient_context` responses | Gate only high-risk procedural/policy deterministic queries; semantic-router cases rely on reranker/fact guard. |
| Reranker endpoint unavailable | Retrieval failure when enabled | Default remains disabled; enable only after health-testing `/rerank`. |
| Claim guard becomes keyword-heavy | Maintenance burden | Guard generic procedural support terms, not every business intent. |

## Open Questions

- Which self-host endpoint will be used in production: TEI, Infinity, or another compatible `/rerank` API?
