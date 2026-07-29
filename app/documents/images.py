from __future__ import annotations

import json
from pathlib import Path


def load_image_lookup(documents_dir: Path, document_ids: set[str]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for document_id in document_ids:
        images_path = documents_dir / document_id / "processed" / "images.json"
        if not images_path.exists():
            continue
        images = json.loads(images_path.read_text(encoding="utf-8"))
        for image in images:
            image_id = image["image_id"]
            lookup[image_id] = {
                "image_id": image_id,
                "file_name": image["file_name"],
                "section": image.get("section", ""),
                "anchor_text": image.get("anchor_text", ""),
                "url": f"/api/v1/documents/{document_id}/images/{image['file_name']}",
            }
    return lookup
