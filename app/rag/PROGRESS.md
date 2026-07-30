# RAG Progress

Last updated: 2026-07-30

## Current state

- Retrieval dùng dense Qdrant search + BM25 lexical search + RRF fusion.
- Metadata filtering được áp dụng trước dense search, BM25 search và RRF.
- Final context được giới hạn bằng `FINAL_CONTEXT_TOP_N` và `MAX_CONTEXT_TOKENS`.
- Prompt contract gồm system prompt + CONTEXT + user query.
- Citation validator loại bỏ unknown `SOURCE_n`.

## Verified

- Unit tests cover RRF, citation validation, refusal logic và metadata filtering.
- `MIN_RETRIEVAL_SCORE` đã giảm về `0.01` cho phù hợp scale RRF.

## Open work

- Reranker model mới là placeholder; chưa bật `bge-reranker-v2-m3` thật.
- BM25 filtered search hiện có thể rebuild filtered index mỗi request; cần tối ưu khi corpus lớn.
- Có thể thêm claim-level verification nếu cần chống hallucination mạnh hơn.
