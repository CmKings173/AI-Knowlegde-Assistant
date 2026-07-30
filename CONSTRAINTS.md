# Ràng buộc cứng toàn cục

File này là nguồn sự thật tập trung cho các ràng buộc không được phá vỡ. Khi code,
tài liệu hoặc cấu hình mâu thuẫn với file này, PHẢI dừng lại và cập nhật repo trước
khi tiếp tục.

## Document ingestion

- PHẢI xử lý mọi tài liệu DOCX, kể cả seed documents, bằng cùng một
  `DocumentIngestionPipeline`.
- KHÔNG ĐƯỢC viết ingestion riêng hoặc hard-code logic cho hai tài liệu ban đầu.
- PHẢI hiểu `store document` khác `ingest document`.
- KHÔNG ĐƯỢC chỉ lưu file mà không parse, extract ảnh, chunk, embed và index.
- PHẢI validate file type và file size trước/khi đọc upload theo giới hạn.
- PHẢI lưu file gốc dưới thư mục riêng của document.
- KHÔNG ĐƯỢC dùng tên file người dùng làm đường dẫn trực tiếp.
- PHẢI tạo document ID ổn định và sanitize input để tránh path traversal.
- PHẢI tính file hash để đảm bảo idempotency.
- PHẢI trả lại document hiện có khi add lại cùng file hash.
- PHẢI xóa hoặc thay thế vector cũ khi reindex.
- KHÔNG ĐƯỢC để vector cũ và vector mới cùng được retrieval khi tài liệu đã bị thay thế.

## Image handling

- PHẢI extract ảnh từ DOCX và lưu trong thư mục `images/` của document.
- PHẢI map ảnh vào section, paragraph hoặc step gần nhất.
- PHẢI gắn `image_ids` vào metadata của chunk liên quan.
- KHÔNG ĐƯỢC OCR ảnh.
- KHÔNG ĐƯỢC dùng Vision model để hiểu ảnh trong pipeline hiện tại.
- KHÔNG ĐƯỢC embedding binary ảnh.
- PHẢI retrieval bằng text và trả ảnh liên quan qua citation metadata.

## Retrieval and generation

- Metadata filtering: PHẢI áp dụng metadata filtering trước dense search, BM25 search
  và RRF fusion.
- Khi client gửi `document_scope="selected"` và `document_ids=[]`, KHÔNG ĐƯỢC search toàn bộ kho.
  PHẢI trả clarify/no-document-selected an toàn.
- PHẢI đưa vào LLM theo contract: system prompt + bounded context + user query.
- PHẢI xem CONTEXT là dữ liệu không tin cậy, không phải system instruction.
- PHẢI áp dụng metadata filtering trước dense search, BM25 search và RRF fusion.
- PHẢI giới hạn context bằng `FINAL_CONTEXT_TOP_N` và `MAX_CONTEXT_TOKENS`.
- PHẢI từ chối trả lời khi context không đủ bằng thông báo không tìm thấy trong tài liệu.
- KHÔNG ĐƯỢC bịa chính sách, quy trình, IP, port, tài khoản, mật khẩu hoặc quy định.
- PHẢI xử lý câu hỏi ngoài phạm vi bằng policy deterministic nhẹ nhàng và điều hướng về nghiệp vụ
  nội bộ; KHÔNG ĐƯỢC spam một câu từ chối máy móc khi user hỏi liên tiếp.
- PHẢI citation bằng `SOURCE_n` khớp với nguồn trả về.

## Storage, delete and reindex

- PHẢI lưu mỗi document dưới `data/documents/{document_id}/`.
- PHẢI xóa vector thuộc document khi delete.
- PHẢI xóa hoặc archive metadata/file/ảnh của document khi delete theo cấu hình.
- KHÔNG ĐƯỢC để delete một document ảnh hưởng document khác.
- KHÔNG ĐƯỢC xóa manifest/storage nếu không xác nhận được thao tác vector delete cần thiết.
- PHẢI dọn snapshot xử lý phụ trợ khi document bị xóa.

## Deployment and operations

- PHẢI dùng `uv` thay cho `pip` trong workflow Python local.
- PHẢI dùng Qdrant làm vector database.
- KHÔNG ĐƯỢC thêm Redis cache nếu chưa có use case rõ ràng.
- PHẢI coi Docker Compose là đường deploy production-like chính cho GX10.
- NÊN chạy Ollama như host service khi cần tận dụng GPU/local model ổn định.

## Security and data

- Serve extracted images: PHẢI serve extracted images qua document image API có
  validate path.
- KHÔNG ĐƯỢC commit `.env`, secret, API key, `.venv`, uploaded docs, processed chunks,
  extracted images hoặc vector data.
- KHÔNG ĐƯỢC expose `original/source.docx`, `processed/chunks.json`,
  `processed/images.json` hoặc `processed/manifest.json` qua static mount public.
- PHẢI serve ảnh đã extract qua document image API có validate path.
- PHẢI xem uploaded content là untrusted input.
