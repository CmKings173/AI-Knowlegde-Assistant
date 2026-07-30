# Provider Architecture

Providers isolate external/runtime dependencies from core ingestion and RAG logic.

## Trách nhiệm

- Provide LLM generation through a common interface.
- Provide embedding generation through a common interface.
- Provide vector store operations through a common interface.
- Provide optional HTTP reranking through a common interface.
- Convert provider errors into domain-specific exceptions where appropriate.

## Giao diện

- `LLMProvider.generate(system_prompt, user_prompt)`.
- `EmbeddingProvider.embed_texts(texts)`.
- `VectorStore.ensure_collection(vector_size)`.
- `VectorStore.upsert_chunks(chunks, vectors)`.
- `VectorStore.search(vector, top_k, filters=None)`.
- `VectorStore.delete_document(document_id)`.
- `VectorStore.list_chunks(limit=10000)`.
- `Reranker.rerank(query, chunks, top_k)`.

## Phụ thuộc

- Ollama API for local LLM/embeddings.
- OpenAI-compatible API for LLM/embedding.
- Gemini API for LLM/embedding.
- Qdrant service for vector search/index.
- Optional TEI/Infinity-compatible `/rerank` endpoint for reranking.
- Hash/Echo fake providers for smoke tests.

## Current providers

- LLM: `ollama`, `openai`, `gemini`, `echo`.
- Embedding: `openai`, `gemini`, `ollama`, `hash`.
- Vector store: `qdrant`.
- Reranker: optional HTTP provider selected by `RERANKER_PROVIDER`.

## Constraints

- MUST keep core logic independent from concrete providers.
- MUST NOT use `hash` or `echo` as production-quality model behavior.
- MUST propagate Qdrant errors when delete/reindex needs consistency.
- MUST keep reranking disabled unless the configured `/rerank` endpoint is running and schema-compatible.
