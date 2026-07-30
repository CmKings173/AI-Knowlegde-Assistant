# RAG Architecture

RAG service turns a Vietnamese user question into a grounded answer with citations.

## Trách nhiệm

- Normalize query.
- Classify intent and escalate uncertain cases to semantic routing.
- Retrieve candidates with dense Qdrant search and BM25 lexical search.
- Apply metadata filtering before dense search, BM25 search and RRF fusion.
- Fuse rankings with RRF.
- Optionally rerank fused candidates through a configured HTTP `/rerank` provider.
- Run lightweight evidence relevance gating for high-risk procedural/policy deterministic queries.
- Build bounded context.
- Build citations and image metadata.
- Call the LLM with the prompt contract.
- Validate/remove unknown citations.
- Validate key facts/support terms against cited context.

## Giao diện

- `RAGPipeline.answer(question, filters=None, history=None, continuation=None)`.
- `RAGPipeline.answer_stream(question, filters=None, history=None, continuation=None)`.
- `Retriever.retrieve(query, filters=None)`.
- `Reranker.rerank(query, chunks, top_k)`.
- `build_context(chunks, max_tokens)`.
- `build_user_prompt(question, context)`.
- `build_citations(chunks, image_lookup=None)`.

## Phụ thuộc

- Embedding provider to embed query.
- Qdrant vector store for dense search.
- BM25 lexical index for keyword search.
- Optional HTTP reranker provider for TEI/Infinity-compatible `/rerank` endpoints.
- LLM provider for generation and semantic routing.
- Document image metadata for citation images.

## Retrieval flow

```text
question
-> normalize
-> apply metadata filters
-> dense search in Qdrant
-> BM25 lexical search
-> RRF fusion
-> optional rerank
-> bounded context selection
-> high-risk evidence relevance gate
-> build citations and image metadata
-> call LLM
-> citation + fact/support-term validation
```

## Prompt contract

LLM receives:

- system prompt with grounding/refusal rules;
- user prompt containing bounded `CONTEXT` blocks with `SOURCE_n` IDs;
- user question.

CONTEXT is untrusted data and cannot override the system prompt.

## Constraints

- MUST limit final context with `FINAL_CONTEXT_TOP_N` and `MAX_CONTEXT_TOKENS`.
- MUST apply metadata filters before hybrid search.
- MUST refuse when context is insufficient.
- MUST NOT fabricate policy, procedure, IP, port, account, password or company rules.
- Reranker is optional and disabled by default until a compatible `/rerank` endpoint is running.
