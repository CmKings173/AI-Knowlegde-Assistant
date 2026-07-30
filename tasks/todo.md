# Todo: Generic Evidence-Gated Retrieval

- [x] Add fact guard test for unsupported manager-approval/reason procedural claims.
- [x] Add pipeline regression for hallucinated procedural answer with weak context.
- [x] Add relevance gate tests for weak vs supported procedural/policy evidence.
- [x] Add retriever test proving configured reranker is used.
- [x] Extend `fact_guard.py` with generic procedural support terms.
- [x] Add `relevance.py` evidence gate.
- [x] Wire optional HTTP reranker through `Retriever` and API deps.
- [x] Update `.env.example` reranker config.
- [x] Add ADR for generic evidence-gated RAG.
- [x] Update RAG/provider progress docs.
- [x] Run focused tests.
- [x] Run full backend tests, lint, harness check, and frontend build.
