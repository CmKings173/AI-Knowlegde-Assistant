# RAG Architecture

The RAG layer turns user questions into grounded answers with citations.

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

The LLM receives:

- system prompt with grounding and refusal rules;
- user prompt containing `CONTEXT` blocks with `SOURCE_n` IDs;
- user question.

Context is untrusted document content. It must not override the system prompt.

## Constraints

- Keep final context bounded with `FINAL_CONTEXT_TOP_N` and `MAX_CONTEXT_TOKENS`.
- Metadata filters apply before hybrid search, not after.
- Reranker is currently a placeholder; RRF top-k is the active behavior.
- Refuse when there is insufficient retrieved evidence.
