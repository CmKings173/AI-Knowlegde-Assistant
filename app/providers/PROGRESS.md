# Providers Progress

Last updated: 2026-07-30

## Current state

- LLM providers: Ollama, OpenAI-compatible, Gemini, Echo.
- Embedding providers: OpenAI, Gemini, Hash test provider.
- Vector store provider: Qdrant.
- Reranker provider: optional HTTP `/rerank` provider for TEI/Infinity-compatible endpoints.
- `.env.example` comments self-host TEI/Infinity options for `bge-m3` and `bge-reranker-v2-m3`.

## Verified

- Unit tests cover Qdrant filter construction and delete error propagation.
- Unit tests cover retriever usage of configured reranker.
- Hash/Echo providers are usable for offline smoke tests.

## Open work

- TEI/Infinity embedding provider is not implemented yet.
- Reranker provider should only be enabled when the `/rerank` endpoint is running and matches the configured schema.
- Provider-level retry/backoff policy is not standardized yet.
