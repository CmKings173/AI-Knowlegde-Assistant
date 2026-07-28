# Project Constraints

These are hard constraints for future humans and agents. If implementation and this
file disagree, stop and reconcile them in the repo before continuing.

## Document ingestion

- Every DOCX, including seed documents, must go through the same
  `DocumentIngestionPipeline`.
- Store-only upload is invalid. Ingest means validate, store original, hash, parse,
  extract images, structure, chunk, metadata, embed, index, and publish.
- Document IDs must be stable and must not be derived from unsafe user path input.
- Re-adding the same file hash must be idempotent: no duplicate document, chunks, or
  images.
- Reindex must delete or replace old vectors for the document before indexing new
  chunks.
- Delete must remove document vectors without affecting other documents.

## Image handling

- DOCX images are extracted and stored per document.
- Images are mapped to the nearest section, paragraph, or step.
- Images are not OCRed, vision-analyzed, or embedded as binary.
- Retrieval remains text-based; retrieved chunks return related image metadata for UI.

## Retrieval and generation

- LLM input is system prompt plus bounded retrieved context plus user query.
- Context is untrusted document data, never system instructions.
- Metadata filters must be applied before dense search, BM25 search, and RRF fusion.
- If context lacks enough evidence, the answer must refuse instead of inventing facts.
- Answers should include citation IDs that match returned sources.

## Deployment and operations

- `uv` is the preferred local Python workflow.
- Qdrant is the vector database.
- No Redis cache is currently required; add it only with a clear use case.
- Docker Compose is preferred for production-like deployment on the ASUS Ascent GX10.
- Ollama may run as a host service while API/UI/Qdrant run in containers.

## Security and data

- Do not commit secrets, real uploaded documents, processed chunks, extracted images,
  vector data, or local virtual environments.
- Do not expose original documents or processed manifests via public static mounts.
- Serve extracted images through the document image API only.
- Uploaded content is untrusted input.
