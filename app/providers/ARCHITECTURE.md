# Provider Architecture

Providers isolate external/runtime dependencies from the application core.

## LLM providers

- `ollama` — local model for answer generation.
- `openai` — OpenAI-compatible chat completions.
- `gemini` — Gemini generation API.
- `echo` — fake provider for offline smoke tests.

## Embedding providers

- `openai` — `text-embedding-3-small` by default.
- `gemini` — `gemini-embedding-001` by default.
- `hash` — deterministic local embedding for tests/smoke checks only.

## Vector store

- Qdrant stores vectors plus chunk payload metadata.
- Search supports metadata filters for document, knowledge type, domain, language,
  and parent/child chunk selection.

## Constraints

- Provider failures should raise domain-specific exceptions.
- Do not make core ingestion or RAG logic depend on a specific provider.
- `hash` and `echo` are not production-quality model behavior.
