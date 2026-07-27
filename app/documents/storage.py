from __future__ import annotations

import re
import shutil
from pathlib import Path

from app.utils.hashing import stable_document_id

STORED_SOURCE_NAME = "source.docx"


def safe_file_name(file_name: str) -> str:
    name = Path(file_name).name
    name = re.sub(r"[^\w.\- ()\[\]À-ỹ]", "_", name, flags=re.UNICODE)
    return name.strip(" .") or "uploaded-document.docx"


def document_dir(documents_dir: Path, document_id: str) -> Path:
    return documents_dir / document_id


def prepare_document_dirs(documents_dir: Path, document_id: str) -> dict[str, Path]:
    root = document_dir(documents_dir, document_id)
    paths = {
        "root": root,
        "original": root / "original",
        "images": root / "images",
        "processed": root / "processed",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def document_id_for_name(file_name: str) -> str:
    return stable_document_id(safe_file_name(file_name))


def store_original_file(
    source_path: Path,
    documents_dir: Path,
    original_name: str,
) -> tuple[str, Path]:
    document_id = document_id_for_name(original_name)
    paths = prepare_document_dirs(documents_dir, document_id)
    suffix = Path(original_name).suffix.lower() or source_path.suffix.lower()
    stored_name = f"source{suffix}" if suffix else STORED_SOURCE_NAME
    target = paths["original"] / stored_name
    shutil.copyfile(source_path, target)
    return document_id, target


def write_original_bytes(
    content: bytes,
    documents_dir: Path,
    original_name: str,
) -> tuple[str, Path]:
    document_id = document_id_for_name(original_name)
    paths = prepare_document_dirs(documents_dir, document_id)
    suffix = Path(original_name).suffix.lower() or ".docx"
    stored_name = f"source{suffix}"
    target = paths["original"] / stored_name
    target.write_bytes(content)
    return document_id, target


def remove_document_storage(documents_dir: Path, document_id: str) -> None:
    root = document_dir(documents_dir, document_id).resolve()
    base = documents_dir.resolve()
    if base not in root.parents and root != base:
        raise ValueError("Refusing to delete outside documents directory")
    if root.exists():
        shutil.rmtree(root)
