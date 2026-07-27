from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree

from docx import Document

from app.domain.exceptions import DocumentParseError
from app.domain.models import ImageAsset, ParsedElement
from app.ingestion.cleaner import clean_text
from app.utils.hashing import sha256_text

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


class DocxParseResult:
    def __init__(self, elements: list[ParsedElement], images: list[ImageAsset]) -> None:
        self.elements = elements
        self.images = images


def parse_docx(path: Path, image_dir: Path | None = None, document_id: str = "") -> DocxParseResult:
    try:
        document = Document(str(path))
    except Exception as exc:  # noqa: BLE001
        raise DocumentParseError(str(exc)) from exc

    style_by_text = _style_map(document)
    image_dir = image_dir or path.parent / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    try:
        return _parse_ordered_docx(path, image_dir, document_id, style_by_text)
    except Exception as exc:  # noqa: BLE001
        raise DocumentParseError(str(exc)) from exc


def _parse_ordered_docx(
    path: Path,
    image_dir: Path,
    document_id: str,
    style_by_text: dict[str, str],
) -> DocxParseResult:
    rels = _load_relationships(path)
    elements: list[ParsedElement] = []
    images: list[ImageAsset] = []
    image_counter = 0

    with zipfile.ZipFile(path) as docx:
        root = ElementTree.fromstring(docx.read("word/document.xml"))
        body = root.find(f"{{{W_NS}}}body")
        if body is None:
            return DocxParseResult([], [])
        for child in body:
            tag = _local_name(child.tag)
            if tag == "p":
                text = clean_text("".join(node.text or "" for node in child.iter(f"{{{W_NS}}}t")))
                image_ids: list[str] = []
                for rel_id in _image_relationship_ids(child):
                    image_counter += 1
                    asset = _extract_image(
                        docx,
                        rels,
                        rel_id,
                        image_dir,
                        document_id,
                        image_counter,
                        text,
                    )
                    if asset:
                        image_ids.append(asset.image_id)
                        images.append(asset)
                if text or image_ids:
                    elements.append(
                        ParsedElement(
                            text=text or "[IMAGE]",
                            style=style_by_text.get(text, ""),
                            is_bullet=_is_bullet_style(style_by_text.get(text, ""), text),
                            is_numbered=_is_numbered(text),
                            image_ids=image_ids,
                        )
                    )
            elif tag == "tbl":
                rows = []
                for row in child.iter(f"{{{W_NS}}}tr"):
                    cells = []
                    for cell in row.iter(f"{{{W_NS}}}tc"):
                        cell_text = clean_text(
                            " ".join(node.text or "" for node in cell.iter(f"{{{W_NS}}}t"))
                        )
                        if cell_text:
                            cells.append(cell_text)
                    if cells:
                        rows.append(" | ".join(cells))
                if rows:
                    elements.append(ParsedElement(text="\n".join(rows), style="Table"))
    return DocxParseResult(elements, images)


def _load_relationships(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as docx:
        xml = docx.read("word/_rels/document.xml.rels")
    root = ElementTree.fromstring(xml)
    rels: dict[str, str] = {}
    for rel in root.iter(f"{{{REL_NS}}}Relationship"):
        rel_id = rel.attrib.get("Id", "")
        target = rel.attrib.get("Target", "")
        if rel_id and target.startswith("media/"):
            rels[rel_id] = f"word/{target}"
    return rels


def _image_relationship_ids(element: ElementTree.Element) -> list[str]:
    rel_ids: list[str] = []
    for blip in element.iter(f"{{{A_NS}}}blip"):
        rel_id = blip.attrib.get(f"{{{R_NS}}}embed")
        if rel_id:
            rel_ids.append(rel_id)
    return rel_ids


def _extract_image(
    docx: zipfile.ZipFile,
    rels: dict[str, str],
    rel_id: str,
    image_dir: Path,
    document_id: str,
    image_counter: int,
    anchor_text: str,
) -> ImageAsset | None:
    target = rels.get(rel_id)
    if not target:
        return None
    content = docx.read(target)
    extension = Path(target).suffix.lower() or ".bin"
    image_id = f"img-{sha256_text(document_id + rel_id + str(image_counter))[:16]}"
    file_name = f"image-{image_counter:03d}{extension}"
    stored_path = image_dir / file_name
    stored_path.write_bytes(content)
    return ImageAsset(
        image_id=image_id,
        file_name=file_name,
        stored_path=str(stored_path),
        content_type=_content_type(extension),
        anchor_text=anchor_text,
    )


def _style_map(document: Document) -> dict[str, str]:
    styles: dict[str, str] = {}
    for paragraph in document.paragraphs:
        text = clean_text(paragraph.text)
        if text and paragraph.style:
            styles.setdefault(text, paragraph.style.name)
    return styles


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _is_bullet_style(style: str, text: str) -> bool:
    return "bullet" in style.lower() or text.startswith(("-", "•", "*"))


def _is_numbered(text: str) -> bool:
    return bool(text[:1].isdigit())


def _content_type(extension: str) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }.get(extension, "application/octet-stream")
