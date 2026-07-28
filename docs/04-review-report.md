# BÁO CÁO REVIEW TÀI LIỆU

## 1. Tổng quan

| Chỉ số | Kết quả |
|---|---:|
| Số section đã kiểm tra | 26 section trong `docs/03-technical-document.md` |
| Số kết luận đã xác minh | 78 kết luận/điểm mô tả chính |
| Số lỗi nghiêm trọng | 0 Critical |
| Số thông tin thiếu bằng chứng | 5 |
| Số phần bị thiếu | 3 |

Phạm vi đối chiếu: `docs/03-technical-document.md`, `docs/01-source-audit.md`, `docs/02-document-outline.md`, và source code hiện tại trong `app/`, `ui/`, `scripts/`, `docker/`, `pyproject.toml`, `.env.example`, `docker-compose.yml`, `Makefile`.

## 2. Thông tin có dấu hiệu bịa hoặc sai

| Mức độ | Nội dung trong tài liệu | Kết quả kiểm tra | Bằng chứng source | Cách sửa |
|---|---|---|---|---|
| High | “Docker Compose default network được dùng theo mặc định compose...” | Không đủ bằng chứng trong source vì `docker-compose.yml` không khai báo `networks`. Đây là kiến thức Docker chung, không phải dữ liệu từ source. | Source: `docker-compose.yml`; không có block `networks`. | Thay bằng “Network cụ thể: Chưa xác định được từ source code hiện tại.” |
| Medium | Architecture/RAG diagrams chỉ thể hiện OpenAI/Gemini/Ollama external providers | Thiếu provider local đã có source: `HashEmbeddingProvider` và `EchoLLMProvider`. Diagram không sai hoàn toàn, nhưng chưa khớp đủ provider layer hiện tại. | Source: `app/providers/embeddings/api_provider.py`; Class: `HashEmbeddingProvider`. Source: `app/providers/llm/factory.py`; Class: `EchoLLMProvider`. | Thêm node local provider hoặc ghi rõ local provider trong diagram. |
| Medium | ERD nối `DOCUMENT_RECORD ||--o{ IMAGE_ASSET` nhưng `ImageAsset` không có field `document_id` | Quan hệ image với document là suy luận từ storage path/`images.json`, không phải quan hệ trực tiếp trong dataclass. | Source: `app/domain/models.py`; Class: `ImageAsset`. Source: `app/documents/images.py`; Function: `load_image_lookup()`. | Đánh dấu là “Suy luận kỹ thuật từ storage layout”, không trình bày như schema DB xác định. |
| Low | Một số source reference dùng wildcard/tổng quát như `app/providers/*` | Không sai về hướng, nhưng chưa đạt mức dẫn chiếu tốt nhất cho tài liệu kỹ thuật. | Source cụ thể có trong `app/providers/llm/*.py`, `app/providers/embeddings/api_provider.py`, `app/providers/vector_store/qdrant_store.py`. | Bổ sung source cụ thể ở phần provider nếu chỉnh tiếp. |

## 3. Flow sai hoặc thiếu bước

| Mức độ | Flow | Kết quả kiểm tra | Bằng chứng source | Cách sửa |
|---|---|---|---|---|
| Medium | Upload/Ingest document | Thiếu bước mô tả classification metadata: `knowledge_type` và `domain` được suy ra trong chunking. | Source: `app/ingestion/chunker.py`; Function: `_build_chunk()`. Source: `app/ingestion/classifier.py`; Function: `classify_knowledge_type()`, `infer_domain()`. | Thêm bước sau chunking: `_build_chunk()` gọi classifier để gán metadata. |
| Low | Upload/Reindex/Delete | Flow có bước reload retriever nhưng error table chưa nêu reload có thể lỗi do Qdrant/list chunks. | Source: `app/rag/retriever.py`; Function: `reload()`. Source: `app/providers/vector_store/qdrant_store.py`; Function: `list_chunks()`. | Bổ sung error case reload/index refresh lỗi. |

## 4. Tech stack sai hoặc thiếu

| Mức độ | Nội dung | Kết quả kiểm tra | Bằng chứng source | Cách sửa |
|---|---|---|---|---|
| Medium | `requests` được liệt kê là UI HTTP client nhưng chỉ ghi “version unknown” | Cần nói rõ hơn: `requests` được import trong UI nhưng không thấy trong direct dependencies của `pyproject.toml`. | Source: `ui/streamlit_app.py`; import `requests`. Source: `pyproject.toml`; dependencies không liệt kê `requests`. | Cập nhật tech stack: “được dùng trong source, chưa thấy khai báo direct dependency”. |
| Low | `app/ingestion/classifier.py` chưa xuất hiện rõ trong tech/source flow | Metadata classification là thành phần đang dùng nhưng chưa được mô tả đủ. | Source: `app/ingestion/chunker.py`; Function: `_build_chunk()`. | Bổ sung trong RAG/Ingestion metadata. |

## 5. AI model và RAG sai hoặc thiếu

| Mức độ | Nội dung | Kết quả kiểm tra | Bằng chứng source | Cách sửa |
|---|---|---|---|---|
| Medium | RAG metadata chỉ nói payload có `knowledge_type/domain`, chưa nói cách sinh | Thiếu mô tả classifier. | Source: `app/ingestion/classifier.py`; Function: `classify_knowledge_type()`, `infer_domain()`. | Thêm subsection/bảng metadata classification. |
| Medium | Diagram thiếu local `HashEmbeddingProvider` và `EchoLLMProvider` | Provider tồn tại và có thể được chọn bằng settings. | Source: `app/providers/embeddings/api_provider.py`; Function: `create_embedding_provider()`. Source: `app/providers/llm/factory.py`; Function: `create_llm_provider()`. | Cập nhật architecture/RAG diagrams. |

Không phát hiện model AI bị ghi sai. Các model mặc định trong tài liệu khớp source: `qwen2.5:3b-instruct`, `text-embedding-3-small`, `text-embedding-004`, `gemini-1.5-flash`, `BAAI/bge-reranker-v2-m3`.

## 6. API, WebSocket, queue và Redis sai hoặc thiếu

| Mức độ | Nội dung | Kết quả kiểm tra | Bằng chứng source | Cách sửa |
|---|---|---|---|---|
| None | API endpoints | Đã xác minh các endpoints trong tài liệu đều tồn tại. | Source: `app/api/routes_health.py`, `app/api/routes_chat.py`, `app/api/routes_documents.py`. | Không cần sửa. |
| None | WebSocket | Tài liệu ghi chưa xác định; khớp source. | Không thấy WebSocket route trong `app/api`. | Không cần sửa. |
| None | Redis/queue/PubSub | Tài liệu ghi chưa xác định; khớp source. | Không thấy dependency/config/source usage. | Không cần sửa. |

## 7. Deployment sai hoặc thiếu

| Mức độ | Nội dung | Kết quả kiểm tra | Bằng chứng source | Cách sửa |
|---|---|---|---|---|
| High | Network Docker Compose | Không đủ bằng chứng như mục 2. | Source: `docker-compose.yml`; không có `networks`. | Sửa thành chưa xác định. |
| None | Ports | Ports `6333`, `8000`, `8501` khớp source. | Source: `docker-compose.yml`, Dockerfiles. | Không cần sửa. |
| None | Volume | Qdrant volume và API `./data:/app/data` khớp source. | Source: `docker-compose.yml`. | Không cần sửa. |
| None | GPU/systemd/nginx/CI/CD | Tài liệu ghi chưa xác định; khớp source. | Không thấy file tương ứng trong repo. | Không cần sửa. |

## 8. Security và secret

| Mức độ | Nội dung | Kết quả kiểm tra | Bằng chứng source | Cách sửa |
|---|---|---|---|---|
| None | Secret thật | Không phát hiện secret thật trong `docs/03-technical-document.md`; chỉ có tên biến env và key trống trong example. | Source: `docs/03-technical-document.md`. | Không cần sửa. |
| None | Auth/security gaps | Tài liệu ghi auth/CORS/rate limit chưa xác định; khớp source. | Không thấy auth middleware/dependency trong routes. | Không cần sửa. |

## 9. Diagram cần sửa

| Mức độ | Diagram | Vấn đề | Cách sửa |
|---|---|---|---|
| Medium | Architecture diagram | Thiếu local Hash/Echo providers trong provider layer. | Thêm node `Local Providers: HashEmbeddingProvider/EchoLLMProvider`. |
| Medium | RAG flowchart | Embedding provider path chỉ thể hiện OpenAI/Gemini, thiếu Hash local. | Thêm nhánh local hash embedding hoặc đổi nhãn thành selected embedding provider. |
| Low | ERD | Quan hệ document-image là suy luận từ storage, không phải DB relation. | Đánh dấu rõ “Suy luận kỹ thuật từ storage layout”. |

## 10. Nội dung bị lặp hoặc quá mơ hồ

| Mức độ | Nội dung | Kết quả kiểm tra | Cách sửa |
|---|---|---|---|
| Low | Các cụm “provider errors qua global handler” | Đúng nhưng hơi tổng quát. | Có thể giữ vì flow error table đã nêu nguyên nhân cụ thể hơn. |
| Low | Source reference tổng quát/wildcard | Có thể gây mơ hồ khi reviewer cần truy vết. | Bổ sung exact source ở provider/metadata sections. |

## 11. Các phần chưa đủ bằng chứng

- Network cụ thể của Docker Compose.
- Runtime `.env` thực tế và provider/model production.
- Authentication/authorization/CORS/rate limit.
- systemd/nginx/CI/CD/GPU/production TLS/domain/autoscaling.
- Metrics/tracing/log aggregation.
- Retry/circuit breaker.
- Quan hệ ERD dạng database thực sự.

Các mục trên phải tiếp tục ghi: “Chưa xác định được từ source code hiện tại.”

## 12. Danh sách chỉnh sửa bắt buộc

### Critical

Không có.

### High

- Sửa câu mô tả Docker Compose default network vì không đủ bằng chứng trong source.

### Medium

- Cập nhật architecture/RAG diagrams để thể hiện local `HashEmbeddingProvider` và `EchoLLMProvider`.
- Bổ sung mô tả metadata classification `knowledge_type/domain` trong ingestion/RAG.
- Ghi rõ `requests` được import trong UI nhưng chưa thấy khai báo direct dependency trong `pyproject.toml`.
- Đánh dấu ERD quan hệ document-image là suy luận kỹ thuật từ storage layout.

### Low

- Bổ sung error case retriever reload có thể lỗi sau upload/reindex/delete.
- Giảm source reference dạng wildcard ở phần provider nếu chỉnh tiếp.

## 13. Kiểm tra cuối sau chỉnh sửa

| Kiểm tra | Trạng thái |
|---|---|
| Không còn API không tồn tại | Đã xác minh |
| Không còn model không được khai báo trong source | Đã xác minh |
| Không còn port bị suy đoán | Đã xác minh |
| Không còn flow không có source reference | Đã xác minh |
| Không có secret thật | Đã xác minh |
| Diagram khớp với code | Đã sửa trong `docs/03-technical-document.md` theo các điểm ở mục 9 |
| Kiến trúc hiện tại và đề xuất được tách riêng | Đã xác minh |
| Tài liệu có thể dùng để onboarding developer mới | Đạt sau khi sửa các mục High/Medium trong `docs/03-technical-document.md` |
