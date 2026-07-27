from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATUS_UPLOADED = "UPLOADED"
STATUS_PARSING = "PARSING"
STATUS_CHUNKING = "CHUNKING"
STATUS_EMBEDDING = "EMBEDDING"
STATUS_INDEXING = "INDEXING"
STATUS_READY = "READY"
STATUS_FAILED = "FAILED"


@dataclass
class DocumentRecord:
    document_id: str
    original_name: str
    stored_name: str
    file_hash: str
    status: str
    created_at: str
    updated_at: str
    chunk_count: int = 0
    parent_chunks: int = 0
    child_chunks: int = 0
    image_count: int = 0
    vector_index_status: str = "NOT_INDEXED"
    source_path: str = ""

    @property
    def file_name(self) -> str:
        return self.original_name

    @property
    def uploaded_at(self) -> str:
        return self.created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "original_name": self.original_name,
            "file_name": self.original_name,
            "stored_name": self.stored_name,
            "file_hash": self.file_hash,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "uploaded_at": self.created_at,
            "chunk_count": self.chunk_count,
            "parent_chunks": self.parent_chunks,
            "child_chunks": self.child_chunks,
            "image_count": self.image_count,
            "vector_index_status": self.vector_index_status,
            "source_path": self.source_path,
        }


@dataclass
class Manifest:
    documents: dict[str, DocumentRecord] = field(default_factory=dict)

    def find_by_hash(self, file_hash: str) -> DocumentRecord | None:
        for record in self.documents.values():
            if record.file_hash == file_hash and record.status == STATUS_READY:
                return record
        return None


class ManifestStore:
    def __init__(self, processed_dir: Path, documents_dir: Path | None = None) -> None:
        self.path = processed_dir / "documents_manifest.json"
        self.documents_dir = documents_dir or Path("data/documents")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.documents_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> Manifest:
        if not self.path.exists():
            return Manifest()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return Manifest(
            documents={
                key: DocumentRecord(**_record_compat(value))
                for key, value in data.get("documents", {}).items()
            }
        )

    def save(self, manifest: Manifest) -> None:
        data = {"documents": {key: value.to_dict() for key, value in manifest.documents.items()}}
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def upsert(self, record: DocumentRecord) -> None:
        manifest = self.load()
        manifest.documents[record.document_id] = record
        self.save(manifest)
        self.save_document_manifest(record)

    def save_document_manifest(self, record: DocumentRecord) -> None:
        path = self.documents_dir / record.document_id / "processed" / "manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def remove(self, document_id: str) -> None:
        manifest = self.load()
        manifest.documents.pop(document_id, None)
        self.save(manifest)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _record_compat(value: dict[str, Any]) -> dict[str, Any]:
    created_at = value.get("created_at") or value.get("uploaded_at") or now_iso()
    updated_at = value.get("updated_at") or created_at
    original_name = value.get("original_name") or value.get("file_name") or "document.docx"
    return {
        "document_id": value["document_id"],
        "original_name": original_name,
        "stored_name": value.get("stored_name", "source.docx"),
        "file_hash": value["file_hash"],
        "status": value.get("status", STATUS_READY).upper(),
        "created_at": created_at,
        "updated_at": updated_at,
        "chunk_count": int(value.get("chunk_count", 0)),
        "parent_chunks": int(value.get("parent_chunks", 0)),
        "child_chunks": int(value.get("child_chunks", 0)),
        "image_count": int(value.get("image_count", 0)),
        "vector_index_status": value.get("vector_index_status", "INDEXED"),
        "source_path": value.get("source_path", ""),
    }
