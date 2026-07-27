from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path


def sha256_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def stable_document_id(file_name: str) -> str:
    stem = Path(file_name).stem.lower()
    ascii_stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_stem)
    slug = slug.strip("-") or "document"
    return f"doc-{sha256_text(stem)[:12]}-{slug[:40]}"
