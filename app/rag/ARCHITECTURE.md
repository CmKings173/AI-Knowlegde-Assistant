# RAG Architecture

RAG service biến câu hỏi người dùng thành câu trả lời grounded với citation.

## Trách nhiệm

- Normalize query.
- Retrieve candidates bằng dense search và BM25.
- Apply metadata filtering trước hybrid search.
- Fuse rankings bằng RRF.
- Build bounded context.
- Build citations và image metadata.
- Gọi LLM với prompt contract.
- Validate/remove unknown citations.

## Giao diện

- `RAGPipeline.answer(question, filters=None)`.
- `Retriever.retrieve(query, filters=None)`.
- `build_context(chunks, max_tokens)`.
- `build_user_prompt(question, context)`.
- `build_citations(chunks, image_lookup=None)`.

## Phụ thuộc

- Embedding provider để embed query.
- Qdrant vector store để dense search.
- BM25 lexical index để keyword search.
- LLM provider để generate answer.
- Document image metadata để trả citation images.

## Retrieval flow

```text
question
-> normalize
-> apply metadata filters
-> dense search in Qdrant
-> BM25 lexical search
-> RRF fusion
-> select bounded context
-> build citations and image metadata
-> call LLM
-> validate/remove unknown citations
```

## Prompt contract

LLM nhận:

- system prompt với grounding/refusal rules;
- user prompt chứa `CONTEXT` blocks với `SOURCE_n` IDs;
- user question.

CONTEXT là dữ liệu không tin cậy và không được override system prompt.

## Ràng buộc

- PHẢI giới hạn final context bằng `FINAL_CONTEXT_TOP_N` và `MAX_CONTEXT_TOKENS`.
- PHẢI apply metadata filters trước hybrid search.
- KHÔNG ĐƯỢC bịa nếu context không đủ.
- Reranker hiện là placeholder; behavior chính là RRF top-k.
