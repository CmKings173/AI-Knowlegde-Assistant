# ADR-002: Use generic evidence gates instead of endless domain-specific routing rules

## Status

Accepted

## Date

2026-07-30

## Context

The assistant must answer internal-policy and SOP questions only when retrieved
context directly supports the response. A reported failure showed the pipeline
retrieving a nearby chunk about working hours, then generating an unsupported
procedure about manager approval and reason submission while citing that chunk.

Adding one ambiguity rule per business topic would not scale. Examples such as
leave, resignation, NAS, email, asset handover, discipline, and HR requests would
turn routing into an ever-growing keyword list.

## Decision

Use generic evidence controls in the RAG pipeline:

- Keep deterministic routing as a fast path only for confident cases.
- Use semantic routing for uncertain cases instead of adding many domain rules.
- Apply a lightweight evidence relevance gate for high-risk procedural/policy
  queries before LLM generation.
- Use reranking after hybrid retrieval when a reranker service is configured.
- Extend fact validation so important procedural claims in the answer must be
  present in the cited context.

Reranking is optional and disabled by default. The production target is a
self-hosted `bge-reranker-v2-m3` endpoint served by TEI, Infinity, or another
compatible `/rerank` API.

## Alternatives considered

### Add HR/leave-specific ambiguity rules

- Pros: Fast to patch the reported example.
- Cons: Does not generalize; future topics need more rules.
- Rejected because it creates unbounded maintenance work.

### Rely on prompt wording only

- Pros: Simple and no extra code.
- Cons: The model can still attach valid-looking citations to unsupported claims.
- Rejected because citation grounding needs code-level enforcement.

### Require reranker for all deployments

- Pros: Better ranking quality.
- Cons: Adds operational dependency and can block local smoke tests.
- Rejected in favor of optional reranker with safe default disabled.

## Consequences

- Some weakly supported procedural/policy questions may now return
  `insufficient_context` instead of attempting an answer.
- Reranker service health becomes important once `RERANKER_ENABLED=true`.
- Future improvements should focus on claim-level support and reranker quality,
  not on expanding router keyword lists.
