from __future__ import annotations

from pathlib import Path

from app.domain.exceptions import DocumentParseError
from app.domain.models import ImageAsset, ParsedElement
from app.ingestion.docx_parser import parse_docx


class LoadedDocument:
    def __init__(
        self,
        elements: list[ParsedElement],
        images: list[ImageAsset] | None = None,
    ) -> None:
        self.elements = elements
        self.images = images or []


def load_document(
    path: Path,
    image_dir: Path | None = None,
    document_id: str = "",
) -> LoadedDocument:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        parsed = parse_docx(path, image_dir=image_dir, document_id=document_id)
        return LoadedDocument(parsed.elements, parsed.images)
    if suffix in {".md", ".txt"}:
        elements = [
            ParsedElement(text=line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return LoadedDocument(elements)
    raise DocumentParseError(f"Unsupported file type: {suffix}")
