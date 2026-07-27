from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.deps import get_ingestion_pipeline


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", required=True, help="Document path to ingest")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-index even if file hash is unchanged",
    )
    args = parser.parse_args()

    for raw_path in args.input:
        path = Path(raw_path)
        if not path.exists():
            raise SystemExit(f"File not found: {path}")
        result = await get_ingestion_pipeline().add_document_path(path, force=args.force)
        print(f"Document: {result['file_name']}")
        print(f"Status: {result['status']}")
        print(f"Parent chunks: {result['parent_chunks']}")
        print(f"Child chunks: {result['child_chunks']}")
        print(f"Images: {result['image_count']}")
        print(f"Indexed chunks: {result['indexed_chunks']}")
        print(f"Duration: {result['duration_s']}s")


if __name__ == "__main__":
    asyncio.run(main())
