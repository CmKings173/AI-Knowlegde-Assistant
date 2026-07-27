from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    chunks_path = settings.processed_dir / "chunks.json"
    if not chunks_path.exists():
        raise SystemExit("No chunks found. Run ingestion first.")
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    preview_path = settings.processed_dir / "chunks_preview.md"
    lines = ["# Chunks Preview", ""]
    for chunk in chunks:
        lines.append(f"## {chunk['document_name']} / {chunk['section']}")
        lines.append("")
        lines.append(f"- chunk_id: `{chunk['chunk_id']}`")
        lines.append(f"- parent_id: `{chunk.get('parent_id')}`")
        lines.append(f"- type: `{chunk['knowledge_type']}`")
        lines.append(f"- domain: `{chunk['domain']}`")
        lines.append(f"- image_ids: `{chunk.get('image_ids', [])}`")
        lines.append("")
        lines.append("```text")
        lines.append(chunk["content"][:1200])
        lines.append("```")
        lines.append("")
    preview_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {chunks_path}")
    print(f"Wrote {preview_path}")


if __name__ == "__main__":
    main()
