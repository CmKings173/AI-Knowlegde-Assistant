# Provider Architecture

Providers cô lập dependency ngoài/runtime khỏi core ingestion và RAG logic.

## Trách nhiệm

- Cung cấp LLM generation qua interface chung.
- Cung cấp embedding generation qua interface chung.
- Cung cấp vector store operations qua interface chung.
- Chuyển lỗi provider thành domain-specific exceptions khi phù hợp.

## Giao diện

- `LLMProvider.generate(system_prompt, user_prompt)`.
- `EmbeddingProvider.embed_texts(texts)`.
- `VectorStore.ensure_collection(vector_size)`.
- `VectorStore.upsert_chunks(chunks, vectors)`.
- `VectorStore.search(vector, top_k, filters=None)`.
- `VectorStore.delete_document(document_id)`.
- `VectorStore.list_chunks(limit=10000)`.

## Phụ thuộc

- Ollama API cho local LLM.
- OpenAI-compatible API cho LLM/embedding.
- Gemini API cho LLM/embedding.
- Qdrant service cho vector search/index.
- Hash/Echo fake providers cho smoke tests.

## Current providers

- LLM: `ollama`, `openai`, `gemini`, `echo`.
- Embedding: `openai`, `gemini`, `hash`.
- Vector store: `qdrant`.

## Ràng buộc

- PHẢI giữ core logic không phụ thuộc provider cụ thể.
- KHÔNG ĐƯỢC dùng `hash` hoặc `echo` như production-quality model behavior.
- PHẢI propagate lỗi Qdrant khi delete/reindex cần consistency.
- TEI/Infinity self-host options mới được document trong `.env.example`, chưa implement.
