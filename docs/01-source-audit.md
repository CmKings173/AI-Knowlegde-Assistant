# BÁO CÁO KHẢO SÁT SOURCE

## 1. Tổng quan repository

- Repository hiện tại là `ai-knowledge-assistant`, ứng dụng Python `>=3.11` dùng FastAPI cho API, Streamlit cho UI, Qdrant làm vector store, và các provider LLM/embedding qua HTTP. Source: `pyproject.toml:6`, `pyproject.toml:8-16`, `docker-compose.yml:1-43`.
- Thư mục chính tìm thấy: `app/api`, `app/ingestion`, `app/rag`, `app/providers`, `app/documents`, `app/domain`, `app/utils`, `ui`, `scripts`, `docker`, `data`, `tests`, `docs`. Source: quét cấu trúc repository hiện tại bằng `rg --files`.
- Repository có các thư mục sinh tự động hoặc runtime cache như `.venv`, `.pytest_cache`, `.tmp`, `__pycache__`; các thư mục này đã bị bỏ qua khi khảo sát nội dung source.
- Trạng thái working tree trước khi tạo báo cáo đã có nhiều file modified/untracked. File mới trong lượt này: `docs/01-source-audit.md`.

## 2. Danh sách service

| Service | Entry point | Công nghệ | Vai trò | Source |
|---|---|---|---|---|
| API service | `app.main:app`; CLI script `api = "main:run_api"`; Docker CMD `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000` | FastAPI, Uvicorn, Pydantic Settings, httpx, Qdrant client | Cung cấp REST API health/chat/documents, wiring ingestion/RAG/provider | `app/main.py:17-24`, `main.py:4-10`, `pyproject.toml:19-21`, `docker/Dockerfile.api:13-14` |
| UI service | `ui/streamlit_app.py`; CLI script `ui = "ui:run_ui"`; Docker CMD `uv run streamlit run ui/streamlit_app.py --server.address 0.0.0.0` | Streamlit, requests | Giao diện chat và quản lý upload tài liệu, gọi API service | `ui.py:6-8`, `ui/streamlit_app.py:7`, `pyproject.toml:19-21`, `docker/Dockerfile.ui:11-12` |
| Qdrant service | Docker Compose service `qdrant` | Qdrant `qdrant/qdrant:v1.12.1` | Vector database cho chunk embedding | `docker-compose.yml:2-13`, `app/providers/vector_store/qdrant_store.py:15-18` |

Không tìm thấy worker service độc lập, producer/consumer queue, hoặc service backend khác trong source hiện tại.

## 3. Tech stack phát hiện được

| Nhóm | Công nghệ | Phiên bản | Vị trí sử dụng |
|---|---|---|---|
| Runtime | Python | `>=3.11` | `pyproject.toml:6`, `docker/Dockerfile.api:1`, `docker/Dockerfile.ui:1` |
| API | FastAPI | `>=0.115.0` | `pyproject.toml:8`, `app/main.py:17-24`, `app/api/routes_chat.py:9-21`, `app/api/routes_documents.py:14-79` |
| API server | Uvicorn | `>=0.30.0` | `pyproject.toml:9`, `main.py:4-10`, `docker/Dockerfile.api:14` |
| Config | pydantic-settings | `>=2.4.0` | `pyproject.toml:10`, `app/config.py:7-10` |
| Upload multipart | python-multipart | `>=0.0.9` | `pyproject.toml:11`, `app/api/routes_documents.py:5`, `app/api/routes_documents.py:23-33` |
| DOCX parsing | python-docx | `>=1.1.2` | `pyproject.toml:12`, `app/ingestion/docx_parser.py:7`, `app/ingestion/docx_parser.py:26-36` |
| Vector store client | qdrant-client | `>=1.11.0` | `pyproject.toml:13`, `app/providers/vector_store/qdrant_store.py:5-18` |
| HTTP client async | httpx | `>=0.27.0` | `pyproject.toml:14`, `app/providers/embeddings/api_provider.py:16-24`, `app/providers/llm/ollama_provider.py:13-18` |
| Lexical search | rank-bm25 | `>=0.2.2` | `pyproject.toml:15`, `app/rag/lexical.py:3-14` |
| UI | Streamlit | `>=1.37.0` | `pyproject.toml:16`, `ui/streamlit_app.py:5-15` |
| UI HTTP client | requests | Chưa xác định version từ `pyproject.toml`; được dùng trong source | `ui/streamlit_app.py:5`, `ui/streamlit_app.py:22-24`, `ui/streamlit_app.py:62-66`, `ui/streamlit_app.py:93-97` |
| Test | pytest, pytest-asyncio | `>=8.3.0`, `>=0.24.0` | `pyproject.toml:23-27`, `pyproject.toml:37-39` |
| Lint/format | ruff | `>=0.6.0` | `pyproject.toml:27`, `pyproject.toml:30-35`, `Makefile:27-36` |
| Container | Docker Compose | Chưa xác định version từ source | `docker-compose.yml:1-43`, `docker/Dockerfile.api:1-14`, `docker/Dockerfile.ui:1-12` |

## 4. Database và storage

- Vector database: Qdrant. Compose dùng image `qdrant/qdrant:v1.12.1`, port `6333`, volume `qdrant_data:/qdrant/storage`, healthcheck `/healthz`. Source: `docker-compose.yml:2-13`.
- API dùng `AsyncQdrantClient(url=settings.qdrant_url, check_compatibility=False)`, collection mặc định `company_knowledge`. Source: `app/providers/vector_store/qdrant_store.py:15-18`, `app/config.py:25-26`.
- Qdrant operations tìm thấy: create collection, upsert chunks, dense search, delete by `document_id`, scroll/list chunks. Source: `app/providers/vector_store/qdrant_store.py:20-27`, `app/providers/vector_store/qdrant_store.py:37-49`, `app/providers/vector_store/qdrant_store.py:53-70`, `app/providers/vector_store/qdrant_store.py:73-87`, `app/providers/vector_store/qdrant_store.py:90-104`.
- File storage/runtime data: `data/documents`, `data/uploads`, `data/processed`; per-document `original`, `images`, `processed`; global `data/processed/chunks.json` và `documents_manifest.json`. Source: `app/config.py:18-21`, `app/documents/storage.py:18-35`, `app/documents/manifest.py:75-103`, `app/ingestion/pipeline.py:206-224`.
- Relational database: Chưa xác định được từ source code hiện tại.

## 5. Redis, cache, queue và Pub/Sub

- Redis: Chưa xác định được từ source code hiện tại.
- Cache: chỉ thấy cache trong process bằng `functools.lru_cache` cho settings/provider/dependency factory. Source: `app/config.py:73-75`, `app/api/deps.py:15-39`.
- Queue/job framework: Chưa xác định được từ source code hiện tại.
- Pub/Sub/Kafka/RabbitMQ/Celery: Chưa xác định được từ source code hiện tại.
- Producer/consumer riêng: Chưa xác định được từ source code hiện tại.

## 6. AI model và AI provider

| Model/provider | Chức năng | File sử dụng | Cấu hình |
|---|---|---|---|
| Ollama, model mặc định `qwen2.5:3b-instruct` | LLM chat/generation qua `/api/chat` | `app/providers/llm/ollama_provider.py:10-32`, `app/providers/llm/factory.py:15-18` | `app/config.py:36-39`, `.env.example:38-41` |
| OpenAI-compatible LLM, model từ `OPENAI_MODEL` | LLM chat/generation qua `/chat/completions` | `app/providers/llm/openai_provider.py:10-32`, `app/providers/llm/factory.py:19-20` | `app/config.py:30`, `app/config.py:40`, `.env.example:18`, `.env.example:42` |
| Gemini LLM, model mặc định `gemini-1.5-flash` | LLM chat/generation qua Google Generative Language `generateContent` | `app/providers/llm/gemini_provider.py:10-33`, `app/providers/llm/factory.py:21-22` | `app/config.py:32`, `app/config.py:41`, `.env.example:43` |
| Echo LLM | Local/test fallback provider trả chuỗi cố định khi `LLM_PROVIDER=echo` | `app/providers/llm/factory.py:9-14`, `app/providers/llm/factory.py:23-24` | Chưa thấy trong `.env.example`; provider được chọn bằng `settings.llm_provider` tại `app/providers/llm/factory.py:15-25` |
| OpenAI embedding, model mặc định `text-embedding-3-small` | Embedding qua `/embeddings` | `app/providers/embeddings/api_provider.py:13-29`, `app/providers/embeddings/api_provider.py:74-77` | `app/config.py:28-31`, `.env.example:16-20` |
| Gemini embedding, model mặc định `text-embedding-004` | Embedding qua Google Generative Language `embedContent` | `app/providers/embeddings/api_provider.py:32-50`, `app/providers/embeddings/api_provider.py:78-79` | `app/config.py:32-33`, `.env.example:21-22` |
| Hash embedding | Deterministic local embedding cho tests/offline smoke checks | `app/providers/embeddings/api_provider.py:54-71`, `app/providers/embeddings/api_provider.py:80-81` | Chọn bằng `EMBEDDING_PROVIDER=hash`; không thấy trong `.env.example` |
| Reranker model `BAAI/bge-reranker-v2-m3` | Cấu hình tồn tại nhưng retriever hiện trả `reranker_used=False`; `Reranker` chỉ sort theo score nếu được dùng trực tiếp | `app/config.py:43-44`, `app/rag/retriever.py:52`, `app/rag/reranker.py:6-9` | `.env.example:46-61` |

- STT: Chưa xác định được từ source code hiện tại.
- TTS: Chưa xác định được từ source code hiện tại.

## 7. External services

- Ollama: HTTP POST tới `{OLLAMA_BASE_URL}/api/chat`. Source: `app/providers/llm/ollama_provider.py:13-18`, `app/config.py:37-38`.
- OpenAI-compatible API: HTTP POST tới `{OPENAI_BASE_URL}/embeddings` và `{OPENAI_BASE_URL}/chat/completions`. Source: `app/providers/embeddings/api_provider.py:21-24`, `app/providers/llm/openai_provider.py:18-28`, `app/config.py:29-31`, `app/config.py:40`.
- Google Gemini API: HTTP POST tới `https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent` và `...:generateContent`. Source: `app/providers/embeddings/api_provider.py:43-49`, `app/providers/llm/gemini_provider.py:18-25`.
- Qdrant: HTTP/gRPC client qua `AsyncQdrantClient` đến `QDRANT_URL`. Source: `app/providers/vector_store/qdrant_store.py:15-18`, `docker-compose.yml:23`.
- UI gọi API service qua `API_BASE_URL` mặc định `http://localhost:8000`; compose đặt `http://api:8000`. Source: `ui/streamlit_app.py:7`, `docker-compose.yml:39`.

## 8. Danh sách API và WebSocket event

| Method/Event | Path | Mục đích | Source |
|---|---|---|---|
| GET | `/health` | Health check, kiểm tra Qdrant và trả provider info | `app/api/routes_health.py:11-24` |
| POST | `/api/v1/chat` | Trả lời câu hỏi qua RAG pipeline | `app/api/routes_chat.py:12-17` |
| POST | `/api/v1/debug/retrieve` | Debug retrieval candidates nếu `DEBUG_ENDPOINTS_ENABLED=true` | `app/api/routes_chat.py:20-35`, `app/config.py:59` |
| GET | `/api/v1/documents` | List document manifest | `app/api/routes_documents.py:17-20` |
| POST | `/api/v1/documents` | Upload và ingest tài liệu | `app/api/routes_documents.py:23-36` |
| POST | `/api/v1/documents/upload` | Compatibility alias gọi lại upload chính | `app/api/routes_documents.py:38-40` |
| POST | `/api/v1/documents/{document_id}/reindex` | Reindex document đã có trong manifest | `app/api/routes_documents.py:43-50` |
| DELETE | `/api/v1/documents/{document_id}` | Xóa vector, manifest, snapshot và storage của document | `app/api/routes_documents.py:53-64` |
| GET | `/api/v1/documents/{document_id}/images/{file_name}` | Serve image đã extract từ document | `app/api/routes_documents.py:67-76` |

WebSocket event: Chưa xác định được từ source code hiện tại.

## 9. Các flow chính

### Flow 1: Chat/RAG answer

- Điểm bắt đầu: `POST /api/v1/chat`.
- Thành phần tham gia: `routes_chat`, `RAGPipeline`, `QueryNormalizer`, `Retriever`, embedding provider, Qdrant vector store, BM25 lexical index, context/citation builders, LLM provider.
- Chuỗi xử lý: validate độ dài câu hỏi; normalize query; retrieve bằng embedding dense search Qdrant và BM25 lexical; fuse bằng reciprocal rank fusion; nếu không đủ evidence thì trả refusal; build context và citations; gọi LLM; lọc/ép citation; trả response kèm retrieval meta và timing.
- Điểm kết thúc: JSON `ChatResponse`.
- File liên quan: `app/api/routes_chat.py:12-17`, `app/rag/pipeline.py:40-89`, `app/rag/retriever.py:29-52`, `app/rag/hybrid_search.py:4-13`, `app/rag/response_validator.py:38-39`, `app/providers/llm/factory.py:15-25`.

### Flow 2: Debug retrieve

- Điểm bắt đầu: `POST /api/v1/debug/retrieve`.
- Thành phần tham gia: `routes_chat`, `RAGPipeline.normalizer`, `Retriever`.
- Chuỗi xử lý: kiểm tra `debug_endpoints_enabled`; normalize question; gọi retriever; trả candidate count và payload của candidates.
- Điểm kết thúc: JSON debug candidates.
- File liên quan: `app/api/routes_chat.py:20-35`, `app/config.py:59`, `app/rag/retriever.py:29-52`.

### Flow 3: Upload và ingest document qua API/UI

- Điểm bắt đầu: UI tab Documents gọi `POST /api/v1/documents`, hoặc client gọi API trực tiếp.
- Thành phần tham gia: Streamlit UI, `routes_documents`, `IngestionPipeline`, storage/manifest, document loader/parser/chunker, embedding provider, Qdrant vector store, retriever reload.
- Chuỗi xử lý: đọc upload giới hạn kích thước; validate extension/size; hash file và skip nếu hash READY đã tồn tại; lưu original file; ghi manifest `UPLOADED`; parse DOCX/MD/TXT; chunk; ghi `chunks.json` và `images.json`; batch embedding; delete vector cũ của document; upsert chunks; ghi `READY/INDEXED`; reload lexical index.
- Điểm kết thúc: JSON kết quả ingest; UI hiển thị success.
- File liên quan: `ui/streamlit_app.py:90-101`, `app/api/routes_documents.py:23-36`, `app/api/routes_documents.py:79-88`, `app/ingestion/pipeline.py:42-76`, `app/ingestion/pipeline.py:95-182`, `app/ingestion/loader.py:20-31`, `app/ingestion/chunker.py:81-115`.

### Flow 4: Reindex document

- Điểm bắt đầu: `POST /api/v1/documents/{document_id}/reindex`.
- Thành phần tham gia: `routes_documents`, manifest store, `IngestionPipeline`, embedding provider, Qdrant vector store, retriever reload.
- Chuỗi xử lý: load manifest; trả 404 nếu document không tồn tại; gọi reindex với `force=True`; pipeline ingest lại từ `record.source_path`; reload retriever.
- Điểm kết thúc: JSON kết quả reindex.
- File liên quan: `app/api/routes_documents.py:43-50`, `app/ingestion/pipeline.py:82-93`, `app/ingestion/pipeline.py:95-182`.

### Flow 5: Delete document

- Điểm bắt đầu: `DELETE /api/v1/documents/{document_id}`.
- Thành phần tham gia: `routes_documents`, Qdrant vector store, manifest store, global chunks snapshot, filesystem storage, retriever reload.
- Chuỗi xử lý: load manifest; trả 404 nếu không có document; delete vectors theo `document_id`; remove manifest; remove document khỏi global `chunks.json`; xóa thư mục document sau khi guard path; reload retriever.
- Điểm kết thúc: JSON `{status: deleted, document_id}`.
- File liên quan: `app/api/routes_documents.py:53-64`, `app/providers/vector_store/qdrant_store.py:73-87`, `app/documents/manifest.py:109-112`, `app/ingestion/pipeline.py:243-249`, `app/documents/storage.py:67-73`.

### Flow 6: UI chat

- Điểm bắt đầu: `st.chat_input` trong Streamlit.
- Thành phần tham gia: Streamlit UI, API `/api/v1/documents`, API `/api/v1/chat`, image endpoint.
- Chuỗi xử lý: load danh sách document để tạo filter; user nhập question; nếu chọn document thì gửi `filters.document_ids` và `include_parent_chunks=false`; POST chat; render answer, citations, image URLs.
- Điểm kết thúc: UI session state lưu assistant message và citations.
- File liên quan: `ui/streamlit_app.py:18-34`, `ui/streamlit_app.py:51-85`, `app/api/routes_chat.py:12-17`, `app/api/routes_documents.py:67-76`.

### Flow 7: CLI ingestion/evaluation operations

- Điểm bắt đầu: `scripts/ingest_documents.py`, `scripts/add_document.py`, `scripts/rebuild_index.py`, `scripts/evaluate_retrieval.py`, `scripts/inspect_chunks.py`.
- Thành phần tham gia: scripts, dependency factories, ingestion pipeline, manifest store, retriever, filesystem output.
- Chuỗi xử lý: scripts ingest/add/rebuild gọi ingestion pipeline; evaluate gọi retriever trên `data/evaluation/golden_questions.json` và ghi `retrieval_report.json`; inspect đọc `processed/chunks.json` và ghi preview markdown.
- Điểm kết thúc: console output và/hoặc file trong `data/evaluation`/`data/processed`.
- File liên quan: `scripts/ingest_documents.py:13-37`, `scripts/add_document.py:13-33`, `scripts/rebuild_index.py:12-22`, `scripts/evaluate_retrieval.py:15-72`, `scripts/inspect_chunks.py:12-38`.

## 10. Deployment và infrastructure

- Docker Compose có 3 service: `qdrant`, `api`, `ui`. Source: `docker-compose.yml:1-43`.
- API image dùng `ghcr.io/astral-sh/uv:python3.11-bookworm`, copy `pyproject.toml`, `README.md`, `app`, `scripts`, `data/evaluation`, expose `8000`, chạy Uvicorn. Source: `docker/Dockerfile.api:1-14`.
- UI image dùng cùng base image, copy `ui`, expose `8501`, chạy Streamlit. Source: `docker/Dockerfile.ui:1-12`.
- Compose mount `./data:/app/data` cho API và đặt `QDRANT_URL=http://qdrant:6333`, `OLLAMA_BASE_URL=http://host.docker.internal:11434`. Source: `docker-compose.yml:20-31`.
- Makefile có lệnh install/run/test/lint/harness/check/format/docker up/down/logs. Source: `Makefile:3-44`.
- CI/CD workflows: Chưa xác định được từ source code hiện tại.
- Nginx config: Chưa xác định được từ source code hiện tại.
- systemd service: Chưa xác định được từ source code hiện tại.

## 11. Error handling, retry và fallback

- FastAPI gắn middleware `x-request-id` và exception handlers cho `ApplicationError` và `Exception`, log bằng `logging.exception`, trả JSON lỗi 500. Source: `app/main.py:30-59`.
- Logging cấu hình qua `logging.basicConfig`, level từ settings, output stdout. Source: `app/utils/logging.py:7-14`, `app/config.py:16`.
- Upload validate kích thước bằng `file.size` và đọc từng chunk 1 MiB; lỗi kích thước trả 413. Source: `app/api/routes_documents.py:79-88`.
- Upload document bắt `ValueError` từ ingestion và trả 422. Source: `app/api/routes_documents.py:23-34`.
- Ingestion bắt mọi exception trong `_ingest_stored_file`, ghi status `FAILED` và `vector_index_status=FAILED`, rồi raise lại. Source: `app/ingestion/pipeline.py:170-175`.
- DOCX parser wrap lỗi parse thành `DocumentParseError`. Source: `app/ingestion/docx_parser.py:26-38`.
- Ollama provider bắt `httpx.HTTPError`; OpenAI/Gemini/embedding providers kiểm tra status code `>=400` và raise lỗi provider tương ứng. Source: `app/providers/llm/ollama_provider.py:16-32`, `app/providers/llm/openai_provider.py:15-32`, `app/providers/llm/gemini_provider.py:15-33`, `app/providers/embeddings/api_provider.py:18-29`, `app/providers/embeddings/api_provider.py:37-50`.
- Health endpoint fallback Qdrant status sang `unavailable` nếu `get_collections()` lỗi. Source: `app/api/routes_health.py:15-20`.
- RAG fallback/refusal khi không có candidate hoặc best score dưới `min_retrieval_score`. Source: `app/rag/pipeline.py:51-61`, `app/rag/response_validator.py:38-39`, `app/config.py:55`.
- Citation fallback: nếu có citations nhưng answer không dùng citation và không phải refusal, append `Nguồn`; đồng thời remove unknown citations. Source: `app/rag/pipeline.py:74-81`, `app/rag/response_validator.py:23-30`.
- Retry policy: Chưa xác định được từ source code hiện tại.

## 12. Những thông tin chưa xác định

- Relational database, schema migration và ORM: Chưa xác định được từ source code hiện tại.
- Redis/cache server: Chưa xác định được từ source code hiện tại.
- Queue, Pub/Sub, Kafka, RabbitMQ, Celery, background worker: Chưa xác định được từ source code hiện tại.
- STT/TTS provider/model/API: Chưa xác định được từ source code hiện tại.
- WebSocket events: Chưa xác định được từ source code hiện tại.
- CI/CD pipeline: Chưa xác định được từ source code hiện tại.
- Nginx/reverse proxy config: Chưa xác định được từ source code hiện tại.
- systemd/service manager config: Chưa xác định được từ source code hiện tại.
- Secret management ngoài `.env`/`.env.example`: Chưa xác định được từ source code hiện tại.
- Production domain, TLS, autoscaling, observability backend, log aggregation: Chưa xác định được từ source code hiện tại.
- Provider đang được dùng ở runtime thực tế ngoài giá trị default và `.env.example`: Chưa xác định được từ source code hiện tại.

## 13. Các file quan trọng cần đọc ở lượt tiếp theo

- `README.md` - đối chiếu hướng dẫn vận hành và giới hạn sản phẩm với source.
- `AGENTS.md`, `CONSTRAINTS.md`, `PROGRESS.md`, `tasks/plan.md`, `tasks/todo.md` - bối cảnh yêu cầu, ràng buộc và tiến độ có thể ảnh hưởng cách hiểu hệ thống.
- `app/api/ARCHITECTURE.md`, `app/ingestion/ARCHITECTURE.md`, `app/rag/ARCHITECTURE.md`, `app/providers/ARCHITECTURE.md` - tài liệu kiến trúc cục bộ cần đối chiếu với implementation.
- `tests/unit/test_*.py` - xác nhận các behavior có test đang bảo vệ.
- `uv.lock` - xác định version lock thực tế của dependency thay vì chỉ constraint trong `pyproject.toml`.
- `data/evaluation/golden_questions.json` - hiểu bộ câu hỏi đánh giá retrieval.
