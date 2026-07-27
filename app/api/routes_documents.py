from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.deps import get_ingestion_pipeline, get_manifest_store, get_retriever, get_vector_store
from app.api.schemas import DocumentsResponse
from app.config import get_settings
from app.documents.storage import remove_document_storage

router = APIRouter(prefix="/api/v1/documents")


@router.get("", response_model=DocumentsResponse)
async def list_documents() -> dict[str, object]:
    manifest = get_manifest_store().load()
    return {"documents": [record.to_dict() for record in manifest.documents.values()]}


@router.post("")
async def add_document(file: Annotated[UploadFile, File(...)]) -> dict[str, object]:
    settings = get_settings()
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Uploaded file is too large")
    try:
        result = await get_ingestion_pipeline().add_document_bytes(
            content,
            file.filename or "document.docx",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await get_retriever().reload()
    return result


@router.post("/upload")
async def upload_document_compat(file: Annotated[UploadFile, File(...)]) -> dict[str, object]:
    return await add_document(file)


@router.post("/{document_id}/reindex")
async def reindex_document(document_id: str) -> dict[str, object]:
    manifest = get_manifest_store().load()
    if document_id not in manifest.documents:
        raise HTTPException(status_code=404, detail="Document not found")
    result = await get_ingestion_pipeline().reindex_document(document_id)
    await get_retriever().reload()
    return result


@router.delete("/{document_id}")
async def delete_document(document_id: str) -> dict[str, str]:
    manifest_store = get_manifest_store()
    manifest = manifest_store.load()
    if document_id not in manifest.documents:
        raise HTTPException(status_code=404, detail="Document not found")
    await get_vector_store().delete_document(document_id)
    manifest_store.remove(document_id)
    remove_document_storage(get_settings().documents_dir, document_id)
    await get_retriever().reload()
    return {"status": "deleted", "document_id": document_id}
