# Ingestion Architecture

The ingestion layer owns the unified document ingestion pipeline.

## Pipeline

```text
Upload/Add document
-> validate file
-> store original file
-> generate stable document ID
-> calculate file hash
-> parse DOCX blocks
-> extract text, headings, lists, tables, and images
-> build structure
-> map images to sections/steps
-> chunk text
-> generate metadata
-> generate embeddings
-> index into vector database
-> publish document manifest
```

## Constraints

- Seed documents and future uploads use the same pipeline.
- File names from users are metadata only; do not use them as direct paths.
- Re-adding the same hash must be idempotent.
- Images are extracted, mapped, and returned as metadata, not OCRed or embedded.
- Runtime outputs live under `data/documents/{document_id}/` and are ignored by git.
