# Providers Progress

Last updated: 2026-07-30

## Current state

- LLM providers: Ollama, OpenAI-compatible, Gemini, Echo.
- Embedding providers: OpenAI, Gemini, Hash test provider.
- Vector store provider: Qdrant.
- `.env.example` đã comment sẵn option self-host TEI/Infinity cho `bge-m3` và `bge-reranker-v2-m3`.

## Verified

- Unit tests cover Qdrant filter construction and delete error propagation.
- Hash/Echo providers dùng được cho smoke tests offline.

## Open work

- Chưa implement TEI/Infinity embedding provider.
- Chưa implement real reranker provider.
- Chưa có provider-level retry/backoff policy chuẩn hóa.
