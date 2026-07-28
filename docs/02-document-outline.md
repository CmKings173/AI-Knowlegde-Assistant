# OUTLINE TÀI LIỆU KỸ THUẬT

## 1. Thông tin tài liệu

- Nội dung cần trình bày: tên tài liệu, hệ thống `ai-knowledge-assistant`, phạm vi tài liệu, phiên bản tài liệu, ngày cập nhật, người phụ trách, trạng thái, audience, nguồn dữ liệu dùng để viết.
- Source cần tham chiếu: `docs/01-source-audit.md:1-13`, `pyproject.toml:1-6`.
- Sơ đồ hoặc bảng cần tạo: bảng metadata tài liệu.

## 2. Executive Summary

- Nội dung cần trình bày: hệ thống là AI Knowledge Assistant nội bộ; gồm API FastAPI, UI Streamlit, Qdrant vector database; hỗ trợ ingest tài liệu DOCX/MD/TXT, retrieval hybrid Qdrant + BM25, gọi LLM để trả lời có citation; các phần chưa xác định cần ghi “Cần xác nhận thêm”.
- Source cần tham chiếu: `docs/01-source-audit.md:3-18`, `docs/01-source-audit.md:39-45`, `docs/01-source-audit.md:95-151`.
- Sơ đồ hoặc bảng cần tạo: bảng tóm tắt service và capability chính.

## 3. Tổng quan hệ thống

- Nội dung cần trình bày: mục đích hệ thống, loại người dùng theo source hiện có là UI client/API client, dữ liệu vào là document upload và câu hỏi, dữ liệu ra là answer/citations/documents metadata; giới hạn xác nhận từ source.
- Source cần tham chiếu: `ui/streamlit_app.py:18-34`, `ui/streamlit_app.py:51-101`, `app/api/routes_chat.py:12-35`, `app/api/routes_documents.py:17-88`, `docs/01-source-audit.md:79-93`.
- Sơ đồ hoặc bảng cần tạo: context diagram cấp cao bằng Mermaid.

## 4. Kiến trúc tổng thể

- Nội dung cần trình bày: component table gồm UI, API, RAG pipeline, ingestion pipeline, provider layer, document storage, Qdrant, external AI APIs; boundary giữa internal service và external service; protocol HTTP nội bộ/ngoại bộ; volume data; dependency wiring qua `app/api/deps.py`.
- Source cần tham chiếu: `docker-compose.yml:1-43`, `app/api/deps.py:15-50`, `app/main.py:17-24`, `ui/streamlit_app.py:7-8`, `app/providers/vector_store/qdrant_store.py:15-18`, `app/providers/llm/*.py`, `app/providers/embeddings/api_provider.py`.
- Sơ đồ hoặc bảng cần tạo: component table; Mermaid architecture diagram; protocol table; internal/external boundary table.
- Mermaid cần tạo trong tài liệu hoàn chỉnh: `flowchart LR` với `UI --> API --> RAG/Ingestion --> Qdrant/FileStorage`, và `API --> Ollama/OpenAI/Gemini` là external boundary.

## 5. Cấu trúc source code

- Nội dung cần trình bày: vai trò từng thư mục `app/api`, `app/ingestion`, `app/rag`, `app/providers`, `app/documents`, `app/domain`, `app/utils`, `ui`, `scripts`, `docker`, `tests`, `data`; entry point top-level `main.py`, `ui.py`.
- Source cần tham chiếu: `docs/01-source-audit.md:3-13`, `main.py:4-13`, `ui.py:6-12`, `app/main.py:17-63`.
- Sơ đồ hoặc bảng cần tạo: source tree rút gọn; bảng module trách nhiệm.

## 6. Tech stack

- Nội dung cần trình bày theo nhóm:
  - Language/runtime: Python `>=3.11`, uv base image.
  - Backend: FastAPI, Uvicorn, Pydantic Settings, python-multipart, httpx.
  - Frontend: Streamlit, requests.
  - AI/ML: provider LLM/embedding, BM25, RAG modules.
  - Database: relational DB “Cần xác nhận thêm”.
  - Cache: `lru_cache` nội bộ; cache server “Cần xác nhận thêm”.
  - Queue: “Cần xác nhận thêm”.
  - Pub/Sub: “Cần xác nhận thêm”.
  - Vector database: Qdrant.
  - Infrastructure: Dockerfile, Docker Compose, Makefile.
  - Monitoring: logging stdout và health endpoint; monitoring backend “Cần xác nhận thêm”.
- Source cần tham chiếu: `pyproject.toml:6-39`, `docker/Dockerfile.api:1-14`, `docker/Dockerfile.ui:1-12`, `Makefile:3-44`, `app/utils/logging.py:7-14`, `app/api/routes_health.py:11-24`.
- Sơ đồ hoặc bảng cần tạo: tech stack matrix.

## 7. AI và model

- Nội dung cần trình bày:
  - LLM: Ollama default `qwen2.5:3b-instruct`, OpenAI-compatible model từ `OPENAI_MODEL`, Gemini default `gemini-1.5-flash`, Echo provider.
  - Embedding: OpenAI `text-embedding-3-small`, Gemini `text-embedding-004`, Hash embedding.
  - RAG: normalize query, dense Qdrant search, BM25 lexical search, reciprocal rank fusion, context builder, citation builder, response validator.
  - Agent: không thấy agent runtime trong source chính; “Cần xác nhận thêm”.
  - STT/TTS/tool calling/retry: “Cần xác nhận thêm”.
  - Prompt: system prompt và user prompt.
  - Timeout: embedding httpx 30s, OpenAI/Gemini LLM 90s, Ollama theo `LLM_TIMEOUT_SECONDS`, UI request timeout 30/120/300s.
  - Fallback: refusal khi thiếu evidence, citation append/remove unknown citations, Echo provider nếu được cấu hình.
- Source cần tham chiếu: `app/config.py:28-44`, `.env.example:16-61`, `app/providers/llm/factory.py:9-25`, `app/providers/llm/ollama_provider.py:10-32`, `app/providers/llm/openai_provider.py:10-32`, `app/providers/llm/gemini_provider.py:10-33`, `app/providers/embeddings/api_provider.py:13-82`, `app/rag/prompts.py:1-39`, `app/rag/pipeline.py:40-89`, `app/rag/retriever.py:29-52`.
- Sơ đồ hoặc bảng cần tạo: AI provider matrix; RAG pipeline diagram; timeout/fallback table.

## 8. Các flow chính

### 8.1 Chat/RAG answer

- Nội dung cần trình bày: mục đích trả lời câu hỏi dựa trên tài liệu; trigger `POST /api/v1/chat`; input `ChatRequest`; các bước normalize, retrieve, fuse, refusal check, context/citation, LLM call, citation validation; output `ChatResponse`; error cases provider/vector/retrieval lỗi qua exception handler.
- Source references: `app/api/routes_chat.py:12-17`, `app/api/schemas.py:36-66`, `app/rag/pipeline.py:40-109`, `app/rag/retriever.py:29-52`, `app/rag/response_validator.py:23-39`.
- Sơ đồ cần tạo: Mermaid sequence diagram.

### 8.2 Debug retrieve

- Nội dung cần trình bày: mục đích debug retrieval; trigger `POST /api/v1/debug/retrieve`; input `ChatRequest`; check `DEBUG_ENDPOINTS_ENABLED`; output candidate payload; error case 404 khi disabled.
- Source references: `app/api/routes_chat.py:20-35`, `app/config.py:59`.
- Sơ đồ cần tạo: sequence diagram ngắn.

### 8.3 Upload và ingest document

- Nội dung cần trình bày: mục đích thêm tài liệu; trigger UI hoặc `POST /api/v1/documents`; input multipart file; validate size/type/hash; parse/chunk/write files/embed/delete old vectors/upsert/reload; output ingest result; error cases 413, 422, FAILED manifest, provider/vector lỗi.
- Source references: `ui/streamlit_app.py:90-101`, `app/api/routes_documents.py:23-36`, `app/api/routes_documents.py:79-88`, `app/ingestion/pipeline.py:42-76`, `app/ingestion/pipeline.py:95-182`, `app/ingestion/loader.py:20-31`, `app/ingestion/docx_parser.py:26-38`.
- Sơ đồ cần tạo: sequence diagram; state transition diagram cho document status.

### 8.4 Reindex document

- Nội dung cần trình bày: mục đích rebuild index cho document có sẵn; trigger `POST /api/v1/documents/{document_id}/reindex`; input `document_id`; check manifest; force ingest; output result; error case 404.
- Source references: `app/api/routes_documents.py:43-50`, `app/ingestion/pipeline.py:82-93`.
- Sơ đồ cần tạo: sequence diagram.

### 8.5 Delete document

- Nội dung cần trình bày: mục đích xóa document khỏi vector store, manifest, snapshot và filesystem; trigger `DELETE /api/v1/documents/{document_id}`; input `document_id`; output status; error cases 404, path guard.
- Source references: `app/api/routes_documents.py:53-64`, `app/providers/vector_store/qdrant_store.py:73-87`, `app/documents/manifest.py:109-112`, `app/ingestion/pipeline.py:243-249`, `app/documents/storage.py:67-73`.
- Sơ đồ cần tạo: sequence diagram.

### 8.6 UI chat

- Nội dung cần trình bày: mục đích UX chat; trigger `st.chat_input`; input question và optional document filter; API calls; render answer/citation/image; session state.
- Source references: `ui/streamlit_app.py:18-85`, `app/api/routes_documents.py:67-76`.
- Sơ đồ cần tạo: UI interaction sequence.

### 8.7 CLI ingestion/evaluation operations

- Nội dung cần trình bày: mục đích các script vận hành; trigger CLI; input flags/files; output console và file report/preview; error cases file not found/no chunks/no golden dataset.
- Source references: `scripts/ingest_documents.py:13-37`, `scripts/add_document.py:13-33`, `scripts/rebuild_index.py:12-22`, `scripts/evaluate_retrieval.py:15-72`, `scripts/inspect_chunks.py:12-38`.
- Sơ đồ cần tạo: bảng command-flow mapping.

## 9. API

- Nội dung cần trình bày: REST API list đầy đủ, method/path, request model, response model, status/error cases, debug endpoint flag, image serving guard.
- Source cần tham chiếu: `app/api/routes_health.py:11-24`, `app/api/routes_chat.py:12-35`, `app/api/routes_documents.py:17-88`, `app/api/schemas.py:9-87`, `app/main.py:38-59`.
- Sơ đồ hoặc bảng cần tạo: API endpoint table; request/response schema table.

## 10. WebSocket

- Nội dung cần trình bày: ghi rõ WebSocket không được tìm thấy trong source; mọi realtime/event streaming đều “Cần xác nhận thêm”.
- Source cần tham chiếu: `docs/01-source-audit.md:79-93`, kết quả đối chiếu route trong `app/api`.
- Sơ đồ hoặc bảng cần tạo: bảng trạng thái “không có WebSocket xác nhận từ source”.

## 11. Database

- Nội dung cần trình bày: relational database/ORM/migration chưa xác định; storage thực tế là Qdrant và filesystem manifest/snapshot; phân biệt database thường và vector database.
- Source cần tham chiếu: `docs/01-source-audit.md:39-45`, `app/documents/manifest.py:75-112`, `app/ingestion/pipeline.py:206-224`.
- Sơ đồ hoặc bảng cần tạo: storage artifact table; “Cần xác nhận thêm” cho relational DB.

## 12. Redis, queue và Pub/Sub

- Nội dung cần trình bày: không thấy Redis, queue, Pub/Sub, worker service; chỉ có `lru_cache` trong process cho settings/dependencies.
- Source cần tham chiếu: `docs/01-source-audit.md:47-53`, `app/config.py:73-75`, `app/api/deps.py:15-39`.
- Sơ đồ hoặc bảng cần tạo: capability presence/absence table.

## 13. Authentication và security

- Nội dung cần trình bày: authentication/authorization chưa thấy trong routes; security hiện xác nhận được gồm upload size/type validation, image path traversal guard, document storage delete guard, prompt guard trong system prompt, API key config cho providers; các cơ chế auth/rate limit/CORS “Cần xác nhận thêm”.
- Source cần tham chiếu: `app/api/routes_documents.py:79-88`, `app/api/routes_documents.py:67-76`, `app/documents/storage.py:67-73`, `app/rag/prompts.py:1-39`, `app/providers/embeddings/api_provider.py:18-24`, `app/providers/llm/openai_provider.py:15-22`.
- Sơ đồ hoặc bảng cần tạo: security controls table; gaps table.

## 14. Configuration và environment variables

- Nội dung cần trình bày: `Settings` đọc `.env`; từng nhóm env app/data/Qdrant/embedding/LLM/retrieval/chunking/debug; default values; `.env.example`; biến compose override; runtime provider thực tế “Cần xác nhận thêm”.
- Source cần tham chiếu: `app/config.py:10-75`, `.env.example:1-69`, `docker-compose.yml:20-31`, `docker-compose.yml:37-43`.
- Sơ đồ hoặc bảng cần tạo: environment variable table theo nhóm.

## 15. Docker, systemd và deployment

- Nội dung cần trình bày: Docker Compose services, image build context, ports, volumes, dependencies, healthcheck, Dockerfile API/UI, Makefile docker commands; systemd/nginx/CI/CD chưa thấy và cần ghi “Cần xác nhận thêm”.
- Source cần tham chiếu: `docker-compose.yml:1-43`, `docker/Dockerfile.api:1-14`, `docker/Dockerfile.ui:1-12`, `Makefile:38-44`, `docs/01-source-audit.md:153-162`.
- Sơ đồ hoặc bảng cần tạo: deployment topology diagram; service port/volume table.

## 16. Startup flow

- Nội dung cần trình bày: API startup qua `create_app()`, logging config, router include, middleware/exception handlers; CLI `run_api`; UI startup qua Streamlit CLI; Docker CMD startup; compose dependency API waits for Qdrant healthy, UI depends on API.
- Source cần tham chiếu: `app/main.py:17-63`, `main.py:4-13`, `ui.py:6-12`, `docker/Dockerfile.api:14`, `docker/Dockerfile.ui:12`, `docker-compose.yml:28-43`.
- Sơ đồ hoặc bảng cần tạo: startup sequence diagram; entry point table.

## 17. Logging và monitoring

- Nội dung cần trình bày: logging stdout format/level, request ID middleware/header, exception logging, health endpoint Qdrant status/provider info; metrics/tracing/log aggregation “Cần xác nhận thêm”.
- Source cần tham chiếu: `app/utils/logging.py:7-14`, `app/main.py:30-59`, `app/api/routes_health.py:11-24`.
- Sơ đồ hoặc bảng cần tạo: observability capability table.

## 18. Error handling và resilience

- Nội dung cần trình bày: exception hierarchy, global handlers, upload validations, ingestion FAILED transition, provider errors/status code checks, health fallback, RAG refusal and citation fallback; retry policy/circuit breaker/rate limit “Cần xác nhận thêm”.
- Source cần tham chiếu: `app/domain/exceptions.py:1-39`, `app/main.py:38-59`, `app/api/routes_documents.py:23-36`, `app/api/routes_documents.py:79-88`, `app/ingestion/pipeline.py:170-175`, `app/providers/llm/*.py`, `app/providers/embeddings/api_provider.py:18-50`, `app/rag/pipeline.py:51-81`.
- Sơ đồ hoặc bảng cần tạo: error handling matrix; document status failure diagram.

## 19. Performance và scalability

- Nội dung cần trình bày: batch embedding size, retrieval top-k settings, BM25 in-memory lexical index, Qdrant scroll limit, context token cap, file upload size cap, UI/API/provider timeouts; horizontal scaling/session/cache/large corpus behavior “Cần xác nhận thêm”.
- Source cần tham chiếu: `app/config.py:22-23`, `app/config.py:34-58`, `app/ingestion/pipeline.py:177-182`, `app/rag/retriever.py:24-52`, `app/providers/vector_store/qdrant_store.py:90-104`, `ui/streamlit_app.py:22-24`, `ui/streamlit_app.py:62-66`, `ui/streamlit_app.py:93-97`.
- Sơ đồ hoặc bảng cần tạo: tuning parameter table; scalability constraints table.

## 20. Rủi ro kỹ thuật

- Nội dung cần trình bày: chỉ liệt kê rủi ro có căn cứ từ source/audit, ví dụ thiếu retry policy, thiếu auth xác nhận, runtime provider thực tế chưa xác định, CI/CD/monitoring chưa xác định, cache server/queue không có, local filesystem state trong `data`, lexical index in-process cần reload.
- Source cần tham chiếu: `docs/01-source-audit.md:164-190`, `app/api/deps.py:15-39`, `app/rag/retriever.py:24-35`, `app/ingestion/pipeline.py:206-224`.
- Sơ đồ hoặc bảng cần tạo: risk register table gồm risk, evidence, impact, trạng thái “Cần xác nhận thêm” nếu thiếu dữ liệu.

## 21. Đề xuất cải tiến

- Nội dung cần trình bày: chưa viết proposal kiến trúc mới; outline chỉ yêu cầu mục này ở tài liệu hoàn chỉnh phải tách bạch giữa “đề xuất” và “hiện trạng”, chỉ đề xuất dựa trên gaps đã xác nhận.
- Source cần tham chiếu: `docs/01-source-audit.md:178-190`, `docs/01-source-audit.md:164-176`.
- Sơ đồ hoặc bảng cần tạo: improvement backlog table, mỗi dòng có evidence source và trạng thái “Cần xác nhận thêm” nếu chưa đủ dữ liệu.

## 22. Hướng dẫn developer mới

- Nội dung cần trình bày: cách cài đặt bằng Makefile/uv, chạy API/UI, chạy test/lint/check, docker up/down/logs, các script ingest/evaluate/inspect; yêu cầu đọc thêm README/AGENTS/CONSTRAINTS/ARCHITECTURE docs ở lượt viết đầy đủ.
- Source cần tham chiếu: `Makefile:3-44`, `pyproject.toml:19-39`, `main.py:4-13`, `ui.py:6-12`, `scripts/*.py`, `docs/01-source-audit.md:192-200`.
- Sơ đồ hoặc bảng cần tạo: developer command table; onboarding reading order.

## 23. Troubleshooting

- Nội dung cần trình bày: lỗi Qdrant unavailable, thiếu API key/model provider, upload quá lớn/sai định dạng, document not found, no chunks/no golden dataset, backend không phản hồi trong UI; không thêm lỗi chưa có source.
- Source cần tham chiếu: `app/api/routes_health.py:15-24`, `app/providers/embeddings/api_provider.py:18-50`, `app/providers/llm/openai_provider.py:15-32`, `app/providers/llm/gemini_provider.py:15-33`, `app/providers/llm/ollama_provider.py:16-32`, `app/api/routes_documents.py:43-64`, `scripts/evaluate_retrieval.py:20-22`, `scripts/inspect_chunks.py:14-17`, `ui/streamlit_app.py:20-34`, `ui/streamlit_app.py:86-101`.
- Sơ đồ hoặc bảng cần tạo: troubleshooting table gồm symptom, likely source-backed cause, check, source.

## 24. Glossary

- Nội dung cần trình bày: định nghĩa ngắn cho RAG, chunk, parent/child chunk, citation, embedding, vector store, Qdrant, BM25, reciprocal rank fusion, provider, manifest, reindex, refusal.
- Source cần tham chiếu: `app/domain/models.py`, `app/rag/retriever.py:29-52`, `app/rag/hybrid_search.py:4-13`, `app/documents/manifest.py:19-112`, `app/ingestion/chunker.py:81-115`.
- Sơ đồ hoặc bảng cần tạo: glossary table.

## 25. Phụ lục

- Nội dung cần trình bày: danh sách file quan trọng, endpoint list đầy đủ, env list đầy đủ, commands, dependency constraints, Docker service definitions, unknowns cần xác nhận thêm.
- Source cần tham chiếu: `docs/01-source-audit.md:192-200`, `pyproject.toml:6-39`, `.env.example:1-69`, `Makefile:3-44`, `docker-compose.yml:1-43`.
- Sơ đồ hoặc bảng cần tạo: appendix tables cho env/dependency/commands/unknowns.

## Bảng kiểm soát outline

| Phần tài liệu | Source chính | Sơ đồ cần tạo | Trạng thái thông tin |
|---|---|---|---|
| 1. Thông tin tài liệu | `docs/01-source-audit.md`, `pyproject.toml` | Metadata table | Đủ từ source cho outline |
| 2. Executive Summary | `docs/01-source-audit.md` | Capability summary table | Đủ từ source cho outline |
| 3. Tổng quan hệ thống | `ui/streamlit_app.py`, `app/api/routes_*.py` | Context diagram | Đủ từ source cho outline |
| 4. Kiến trúc tổng thể | `docker-compose.yml`, `app/api/deps.py`, `app/providers/*` | Mermaid architecture, component/protocol/boundary tables | Đủ từ source cho outline |
| 5. Cấu trúc source code | `rg --files`, entry points | Source tree, module table | Đủ từ source cho outline |
| 6. Tech stack | `pyproject.toml`, Dockerfiles, Makefile | Tech stack matrix | Thiếu version lock nếu chưa đọc sâu `uv.lock`; Cần xác nhận thêm |
| 7. AI và model | `app/config.py`, `.env.example`, `app/providers/*`, `app/rag/*` | AI provider matrix, RAG diagram, timeout/fallback table | Agent/STT/TTS/tool calling/retry cần xác nhận thêm |
| 8. Các flow chính | `docs/01-source-audit.md`, routes, pipelines, scripts | Sequence diagrams, state diagram, command-flow table | Đủ từ source cho 7 flow đã xác nhận |
| 9. API | `app/api/routes_*.py`, `app/api/schemas.py` | Endpoint table, schema table | Đủ từ source cho REST; auth details cần xác nhận thêm |
| 10. WebSocket | `app/api` route scan, `docs/01-source-audit.md` | Absence/status table | Không thấy WebSocket; Cần xác nhận thêm nếu có runtime ngoài source |
| 11. Database | `app/documents/*`, `app/ingestion/pipeline.py`, Qdrant store | Storage artifact table | Relational DB/ORM/migration cần xác nhận thêm |
| 12. Redis, queue và Pub/Sub | `app/config.py`, `app/api/deps.py`, audit | Presence/absence table | Redis/queue/PubSub cần xác nhận thêm |
| 13. Authentication và security | routes, storage guard, prompts, provider config | Security controls/gaps tables | Auth/CORS/rate limit cần xác nhận thêm |
| 14. Configuration và environment variables | `app/config.py`, `.env.example`, compose | Env variable table | Runtime `.env` thực tế cần xác nhận thêm |
| 15. Docker, systemd và deployment | Dockerfiles, compose, Makefile | Deployment topology, port/volume table | systemd/nginx/CI cần xác nhận thêm |
| 16. Startup flow | `app/main.py`, `main.py`, `ui.py`, Dockerfiles, compose | Startup sequence, entry point table | Đủ từ source cho API/UI/Docker |
| 17. Logging và monitoring | `app/utils/logging.py`, `app/main.py`, health route | Observability table | Metrics/tracing/log aggregation cần xác nhận thêm |
| 18. Error handling và resilience | exceptions, handlers, provider errors, RAG validator | Error matrix, failure state diagram | Retry/circuit breaker/rate limit cần xác nhận thêm |
| 19. Performance và scalability | `app/config.py`, ingestion/retriever/vector store/UI timeouts | Tuning parameter, scalability constraints tables | Horizontal scaling behavior cần xác nhận thêm |
| 20. Rủi ro kỹ thuật | audit unknowns, dependency wiring, retriever reload | Risk register | Đủ căn cứ từ gaps; mức độ ưu tiên cần xác nhận thêm |
| 21. Đề xuất cải tiến | audit gaps/error handling | Improvement backlog table | Chỉ outline; đề xuất cụ thể cần phân tích thêm |
| 22. Hướng dẫn developer mới | Makefile, pyproject, scripts, entry points | Command table, reading order | Đủ từ source cho commands |
| 23. Troubleshooting | routes, provider errors, scripts, UI errors | Troubleshooting table | Đủ cho lỗi có source; vận hành production cần xác nhận thêm |
| 24. Glossary | domain models, RAG modules, manifest | Glossary table | Đủ từ source cho thuật ngữ hiện có |
| 25. Phụ lục | audit, pyproject, env, Makefile, compose | Appendix tables | Đủ từ source cho outline |
