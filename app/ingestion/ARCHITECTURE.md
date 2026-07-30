# Ingestion Architecture

Ingestion service sở hữu unified document ingestion pipeline.

## Trách nhiệm

- Validate file.
- Store original file.
- Generate stable document ID và file hash.
- Parse DOCX/MD/TXT thành document elements.
- Extract DOCX images và map ảnh vào section/step gần nhất.
- Chunk text và tạo metadata.
- Generate embeddings.
- Index chunks vào vector database.
- Publish document manifest.

## Giao diện

- `IngestionPipeline.add_document_path(path, force=False)`.
- `IngestionPipeline.add_document_bytes(content, original_name, force=False)`.
- `IngestionPipeline.ingest_path(path, force=False)`.
- `IngestionPipeline.reindex_document(document_id)`.
- `remove_document_from_global_chunks_snapshot(processed_dir, document_id)`.

## Phụ thuộc

- `app.documents.storage` để chuẩn hóa document directory.
- `app.documents.manifest` để quản lý manifest.
- `app.ingestion.loader` và `app.ingestion.docx_parser` để parse.
- `app.ingestion.chunker` để chunk.
- Embedding provider để tạo vectors.
- Vector store provider để index/delete vectors.

## Pipeline

```text
Upload/Add document
-> validate file
-> store original file
-> generate stable document ID
-> calculate file hash
-> parse document blocks
-> extract text, heading, list, table and images
-> build document structure
-> map images to sections or steps
-> chunk text
-> generate metadata
-> generate embeddings
-> index into vector database
-> publish document
```

## Ràng buộc

- PHẢI dùng cùng pipeline cho seed documents và future uploads.
- KHÔNG ĐƯỢC dùng tên file user làm path trực tiếp.
- PHẢI idempotent khi add lại cùng file hash.
- KHÔNG ĐƯỢC OCR/Vision/embed binary ảnh trong pipeline hiện tại.
