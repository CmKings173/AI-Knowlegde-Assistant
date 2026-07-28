import json
from pathlib import Path

import pytest

from app.config import Settings
from app.documents.images import load_image_lookup
from app.ingestion.pipeline import remove_document_from_global_chunks_snapshot
from app.providers.vector_store.qdrant_store import QdrantVectorStore


def test_default_retrieval_threshold_matches_rrf_score_scale() -> None:
    assert Settings().min_retrieval_score == 0.01


def test_image_lookup_returns_api_image_url(tmp_path: Path) -> None:
    document_dir = tmp_path / "doc-a" / "processed"
    document_dir.mkdir(parents=True)
    (document_dir / "images.json").write_text(
        json.dumps(
            [
                {
                    "image_id": "img-1",
                    "file_name": "image-001.png",
                    "section": "Email",
                }
            ]
        ),
        encoding="utf-8",
    )

    lookup = load_image_lookup(tmp_path, {"doc-a"})

    assert lookup["img-1"]["url"] == "/api/v1/documents/doc-a/images/image-001.png"


def test_remove_document_from_global_chunks_snapshot(tmp_path: Path) -> None:
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    chunks_path = processed_dir / "chunks.json"
    chunks_path.write_text(
        json.dumps(
            [
                {"document_id": "doc-a", "chunk_id": "a"},
                {"document_id": "doc-b", "chunk_id": "b"},
            ]
        ),
        encoding="utf-8",
    )

    remove_document_from_global_chunks_snapshot(processed_dir, "doc-a")

    assert json.loads(chunks_path.read_text(encoding="utf-8")) == [
        {"document_id": "doc-b", "chunk_id": "b"}
    ]


@pytest.mark.asyncio
async def test_qdrant_delete_propagates_connection_errors(monkeypatch) -> None:
    store = QdrantVectorStore(Settings(qdrant_collection="test_collection"))

    async def fail_get_collections():
        raise RuntimeError("qdrant unavailable")

    monkeypatch.setattr(store.client, "get_collections", fail_get_collections)

    with pytest.raises(RuntimeError, match="qdrant unavailable"):
        await store.delete_document("doc-a")
