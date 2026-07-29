from __future__ import annotations

from app.documents.manifest import STATUS_READY, Manifest
from app.domain.models import Chunk


def reconcile_manifest_with_chunks(manifest: Manifest, chunks: list[Chunk]) -> dict[str, object]:
    chunk_document_ids = {chunk.document_id for chunk in chunks}
    manifest_document_ids = set(manifest.documents)
    ready_document_ids = {
        document_id
        for document_id, record in manifest.documents.items()
        if record.status == STATUS_READY and record.vector_index_status == "INDEXED"
    }

    ready_without_vectors = sorted(ready_document_ids - chunk_document_ids)
    vectors_without_manifest = sorted(chunk_document_ids - manifest_document_ids)
    failed_with_vectors = sorted(
        document_id
        for document_id, record in manifest.documents.items()
        if record.status != STATUS_READY and document_id in chunk_document_ids
    )

    return {
        "status": "ok"
        if not ready_without_vectors and not vectors_without_manifest and not failed_with_vectors
        else "mismatch",
        "manifest_documents": len(manifest_document_ids),
        "vector_documents": len(chunk_document_ids),
        "ready_without_vectors": ready_without_vectors,
        "vectors_without_manifest": vectors_without_manifest,
        "failed_with_vectors": failed_with_vectors,
    }
