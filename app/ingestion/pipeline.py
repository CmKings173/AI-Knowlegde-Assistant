from __future__ import annotations

import json
import time
from pathlib import Path

from app.config import Settings
from app.documents.manifest import (
    STATUS_CHUNKING,
    STATUS_EMBEDDING,
    STATUS_FAILED,
    STATUS_INDEXING,
    STATUS_PARSING,
    STATUS_READY,
    STATUS_UPLOADED,
    DocumentRecord,
    ManifestStore,
    now_iso,
)
from app.documents.storage import document_dir, store_original_file, write_original_bytes
from app.domain.models import Chunk, DocumentInfo, ImageAsset
from app.ingestion.chunker import ChunkingConfig, chunk_document
from app.ingestion.loader import load_document
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.vector_store.base import VectorStore
from app.utils.hashing import sha256_bytes, sha256_file


class IngestionPipeline:
    def __init__(
        self,
        settings: Settings,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        manifest_store: ManifestStore,
    ) -> None:
        self.settings = settings
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.manifest_store = manifest_store

    async def add_document_path(self, path: Path, force: bool = False) -> dict[str, object]:
        self._validate_file(path.name, path.stat().st_size)
        file_hash = sha256_file(path)
        existing = self.manifest_store.load().find_by_hash(file_hash)
        if existing and not force:
            return _existing_response(existing)
        document_id, stored_path = store_original_file(
            path,
            self.settings.documents_dir,
            path.name,
        )
        return await self._ingest_stored_file(document_id, path.name, stored_path, file_hash, force)

    async def add_document_bytes(
        self,
        content: bytes,
        original_name: str,
        force: bool = False,
    ) -> dict[str, object]:
        self._validate_file(original_name, len(content))
        file_hash = sha256_bytes(content)
        existing = self.manifest_store.load().find_by_hash(file_hash)
        if existing and not force:
            return _existing_response(existing)
        document_id, stored_path = write_original_bytes(
            content,
            self.settings.documents_dir,
            original_name,
        )
        return await self._ingest_stored_file(
            document_id,
            original_name,
            stored_path,
            file_hash,
            force,
        )

    async def ingest_path(self, path: Path, force: bool = False) -> dict[str, object]:
        return await self.add_document_path(path, force=force)

    async def reindex_document(self, document_id: str) -> dict[str, object]:
        manifest = self.manifest_store.load()
        record = manifest.documents.get(document_id)
        if not record:
            raise FileNotFoundError(f"Document not found: {document_id}")
        return await self._ingest_stored_file(
            document_id,
            record.original_name,
            Path(record.source_path),
            record.file_hash,
            force=True,
        )

    async def _ingest_stored_file(
        self,
        document_id: str,
        original_name: str,
        stored_path: Path,
        file_hash: str,
        force: bool,
    ) -> dict[str, object]:
        started = time.perf_counter()
        created_at = _created_at(self.manifest_store, document_id)
        record = DocumentRecord(
            document_id=document_id,
            original_name=original_name,
            stored_name=stored_path.name,
            file_hash=file_hash,
            status=STATUS_UPLOADED,
            created_at=created_at,
            updated_at=now_iso(),
            vector_index_status="NOT_INDEXED",
            source_path=str(stored_path),
        )
        self.manifest_store.upsert(record)

        try:
            paths = _document_paths(self.settings.documents_dir, document_id)
            record.status = STATUS_PARSING
            record.updated_at = now_iso()
            self.manifest_store.upsert(record)
            loaded = load_document(stored_path, image_dir=paths["images"], document_id=document_id)

            record.status = STATUS_CHUNKING
            record.updated_at = now_iso()
            self.manifest_store.upsert(record)
            document = DocumentInfo(
                document_id=document_id,
                document_name=Path(original_name).stem,
                source_path=stored_path,
                file_hash=file_hash,
            )
            chunks = chunk_document(document, loaded.elements, self._chunking_config())
            images = _attach_image_sections(loaded.images, chunks)
            self._write_document_outputs(document_id, chunks, images)
            self._write_global_chunks_snapshot(chunks)

            record.status = STATUS_EMBEDDING
            record.chunk_count = len(chunks)
            record.parent_chunks = sum(1 for chunk in chunks if chunk.is_parent)
            record.child_chunks = record.chunk_count - record.parent_chunks
            record.image_count = len(images)
            record.updated_at = now_iso()
            self.manifest_store.upsert(record)

            record.status = STATUS_INDEXING
            record.updated_at = now_iso()
            self.manifest_store.upsert(record)
            await self.vector_store.delete_document(document_id)
            await self._embed_and_index(chunks)

            record.status = STATUS_READY
            record.vector_index_status = "INDEXED"
            record.updated_at = now_iso()
            self.manifest_store.upsert(record)
            return {
                "document_id": document_id,
                "file_name": original_name,
                "original_name": original_name,
                "status": STATUS_READY,
                "file_hash": file_hash,
                "parent_chunks": record.parent_chunks,
                "child_chunks": record.child_chunks,
                "image_count": record.image_count,
                "indexed_chunks": len(chunks),
                "skipped": False,
                "duration_s": round(time.perf_counter() - started, 2),
            }
        except Exception:
            record.status = STATUS_FAILED
            record.vector_index_status = "FAILED"
            record.updated_at = now_iso()
            self.manifest_store.upsert(record)
            raise

    async def _embed_and_index(self, chunks: list[Chunk]) -> None:
        batch_size = self.settings.embedding_batch_size
        for index in range(0, len(chunks), batch_size):
            batch = chunks[index : index + batch_size]
            vectors = await self.embedding_provider.embed_texts([chunk.content for chunk in batch])
            await self.vector_store.upsert_chunks(batch, vectors)

    def _chunking_config(self) -> ChunkingConfig:
        return ChunkingConfig(
            target_tokens=self.settings.chunk_target_tokens,
            max_tokens=self.settings.chunk_max_tokens,
            overlap_tokens=self.settings.chunk_overlap_tokens,
            parent_max_tokens=self.settings.parent_max_tokens,
        )

    def _validate_file(self, file_name: str, size: int) -> None:
        suffix = Path(file_name).suffix.lower()
        if suffix not in {".docx", ".md", ".txt"}:
            raise ValueError("Only .docx, .md, and .txt files are supported")
        if size > self.settings.max_upload_mb * 1024 * 1024:
            raise ValueError("Uploaded file is too large")

    def _write_document_outputs(
        self,
        document_id: str,
        chunks: list[Chunk],
        images: list[ImageAsset],
    ) -> None:
        paths = _document_paths(self.settings.documents_dir, document_id)
        (paths["processed"] / "chunks.json").write_text(
            json.dumps([chunk.payload() for chunk in chunks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (paths["processed"] / "images.json").write_text(
            json.dumps([image.__dict__ for image in images], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_global_chunks_snapshot(self, chunks: list[Chunk]) -> None:
        self.settings.processed_dir.mkdir(parents=True, exist_ok=True)
        path = self.settings.processed_dir / "chunks.json"
        existing: list[dict[str, object]] = []
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
        current_doc_ids = {chunk.document_id for chunk in chunks}
        kept = [item for item in existing if item.get("document_id") not in current_doc_ids]
        kept.extend(chunk.payload() for chunk in chunks)
        path.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")


def _existing_response(record: DocumentRecord) -> dict[str, object]:
    return {
        "document_id": record.document_id,
        "file_name": record.original_name,
        "original_name": record.original_name,
        "status": record.status,
        "file_hash": record.file_hash,
        "parent_chunks": record.parent_chunks,
        "child_chunks": record.child_chunks,
        "image_count": record.image_count,
        "indexed_chunks": 0,
        "skipped": True,
        "duration_s": 0,
    }


def remove_document_from_global_chunks_snapshot(processed_dir: Path, document_id: str) -> None:
    path = processed_dir / "chunks.json"
    if not path.exists():
        return
    existing = json.loads(path.read_text(encoding="utf-8"))
    kept = [item for item in existing if item.get("document_id") != document_id]
    path.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")


def _created_at(manifest_store: ManifestStore, document_id: str) -> str:
    record = manifest_store.load().documents.get(document_id)
    return record.created_at if record else now_iso()


def _document_paths(documents_dir: Path, document_id: str) -> dict[str, Path]:
    root = document_dir(documents_dir, document_id)
    return {
        "root": root,
        "original": root / "original",
        "images": root / "images",
        "processed": root / "processed",
    }


def _attach_image_sections(images: list[ImageAsset], chunks: list[Chunk]) -> list[ImageAsset]:
    section_by_image: dict[str, str] = {}
    for chunk in chunks:
        for image_id in chunk.image_ids:
            section_by_image.setdefault(image_id, chunk.section)
    return [
        ImageAsset(
            image_id=image.image_id,
            file_name=image.file_name,
            stored_path=image.stored_path,
            content_type=image.content_type,
            section=section_by_image.get(image.image_id, ""),
            anchor_text=image.anchor_text,
        )
        for image in images
    ]
