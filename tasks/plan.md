# Implementation Plan: AI Knowledge Assistant

## Overview

Build a modular-monolith internal RAG system. Documents are uploaded or ingested at runtime, parsed, chunked, embedded, indexed into Qdrant, then queried through FastAPI and Streamlit. Embeddings are provider-based, with OpenAI/Gemini API for MVP and hash embeddings for offline smoke tests. LLM generation defaults to local Ollama.

## Architecture Decisions

- Dynamic ingestion: source code does not embed company documents. Users upload DOCX/MD/TXT through UI/API or ingest with CLI.
- Per-document storage: each document is stored under `data/documents/{document_id}` with original file, extracted images, chunks, image metadata, and manifest.
- Local LLM: Ollama keeps answer generation on the user's machine. API LLM providers remain swappable.
- API embeddings for MVP: OpenAI/Gemini avoid local model setup cost. Provider abstraction allows BGE-M3 later.
- Qdrant is the retrieval store. Local JSON manifest tracks document hashes/status because PostgreSQL is intentionally out of scope.
- Retrieval is governed RAG: normalize query, dense search, BM25 local, RRF fusion, bounded context, citation validation, refusal threshold.

## Task List

### Phase 1: Foundation

- [x] Create uv-based Python project structure.
- [x] Add config, logging, exceptions, domain models.
- [x] Add provider interfaces and health endpoint.

### Phase 2: Ingestion

- [x] Add DOCX/MD/TXT loader.
- [x] Add rule-based classification and heading-aware parent-child chunking.
- [x] Add manifest storage and upload-safe file storage.
- [x] Add embedding/index pipeline.
- [x] Add per-document storage and status manifest.
- [x] Extract DOCX images and map image IDs to nearest paragraph/step chunks.

### Phase 3: Retrieval And Generation

- [x] Add query normalization, BM25, RRF, context builder.
- [x] Add Ollama/OpenAI/Gemini LLM providers.
- [x] Add chat/debug API endpoints and citation response contract.

### Phase 4: UI And Operations

- [x] Add Streamlit chat/upload UI.
- [x] Add CLI scripts for ingest, inspect, rebuild, evaluate.
- [x] Add Docker Compose, Dockerfiles, Makefile, README.

### Phase 5: Verification

- [x] Unit tests for core logic.
- [x] Ruff lint clean.
- [x] Parse/chunk smoke test with the two real DOCX files.
- [x] Dynamic ingestion smoke test with 56 extracted images and idempotency.
- [ ] Qdrant ingestion smoke test.
- [ ] Retrieval evaluation against Qdrant.
- [ ] End-to-end chat with Ollama.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Docker daemon unavailable | Cannot run Qdrant verification | Docker Desktop currently returns 500/timeouts; code remains Docker-ready; verify ingestion with fake vector store |
| Missing API keys | Cannot call real embeddings | Use `EMBEDDING_PROVIDER=hash` for offline tests |
| Ollama has no model | Chat generation fails | Pull `qwen2.5:3b-instruct` or set `LLM_PROVIDER=echo` for smoke |
| Vietnamese DOCX styles are inconsistent | Headings may be missed | Detect both Word Heading styles and Vietnamese patterns like `Phần`, `Điều` |

## Open Questions

- Which real embedding provider should be default in `.env`: OpenAI or Gemini?
- Which Ollama model should be pulled for your machine size?
