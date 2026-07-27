from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.deps import get_ingestion_pipeline, get_manifest_store


async def main() -> None:
    manifest = get_manifest_store().load()
    if not manifest.documents:
        print("No documents to rebuild.")
        return
    for record in manifest.documents.values():
        result = await get_ingestion_pipeline().ingest_path(Path(record.source_path), force=True)
        print(f"Rebuilt {result['file_name']}: {result['indexed_chunks']} chunks")


if __name__ == "__main__":
    asyncio.run(main())
