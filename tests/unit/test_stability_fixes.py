import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.documents.images import load_image_lookup
from app.documents.manifest import STATUS_FAILED, STATUS_READY, DocumentRecord, Manifest
from app.documents.reconciliation import reconcile_manifest_with_chunks
from app.domain.enums import KnowledgeType
from app.domain.models import Chunk
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


def test_reconciliation_detects_manifest_and_vector_mismatches() -> None:
    manifest = Manifest(
        documents={
            "doc-ready-missing": DocumentRecord(
                document_id="doc-ready-missing",
                original_name="ready.docx",
                stored_name="source.docx",
                file_hash="hash-ready",
                status=STATUS_READY,
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
                vector_index_status="INDEXED",
            ),
            "doc-failed": DocumentRecord(
                document_id="doc-failed",
                original_name="failed.docx",
                stored_name="source.docx",
                file_hash="hash-failed",
                status=STATUS_FAILED,
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
                vector_index_status="FAILED",
            ),
        }
    )
    chunks = [
        Chunk(
            chunk_id="00000000-0000-0000-0000-000000000001",
            parent_id=None,
            document_id="doc-failed",
            document_name="Failed",
            document_version="v1",
            knowledge_type=KnowledgeType.TECHNICAL_GUIDE,
            domain="it",
            section="NAS",
            heading_path=["NAS"],
            chunk_index=0,
            content="Open NAS",
            source_path="doc.md",
            content_hash="hash-a",
        ),
        Chunk(
            chunk_id="00000000-0000-0000-0000-000000000002",
            parent_id=None,
            document_id="doc-vector-only",
            document_name="Vector",
            document_version="v1",
            knowledge_type=KnowledgeType.TECHNICAL_GUIDE,
            domain="it",
            section="NAS",
            heading_path=["NAS"],
            chunk_index=0,
            content="Open NAS",
            source_path="doc.md",
            content_hash="hash-b",
        ),
    ]

    report = reconcile_manifest_with_chunks(manifest, chunks)

    assert report["status"] == "mismatch"
    assert report["ready_without_vectors"] == ["doc-ready-missing"]
    assert report["vectors_without_manifest"] == ["doc-vector-only"]
    assert report["failed_with_vectors"] == ["doc-failed"]


@pytest.mark.asyncio
async def test_qdrant_delete_propagates_connection_errors(monkeypatch) -> None:
    store = QdrantVectorStore(Settings(qdrant_collection="test_collection"))

    async def fail_get_collections():
        raise RuntimeError("qdrant unavailable")

    monkeypatch.setattr(store.client, "get_collections", fail_get_collections)

    with pytest.raises(RuntimeError, match="qdrant unavailable"):
        await store.delete_document("doc-a")


@pytest.mark.asyncio
async def test_qdrant_search_uses_query_points_client_api() -> None:
    store = QdrantVectorStore(Settings(qdrant_collection="test_collection"))
    chunk = Chunk(
        chunk_id="00000000-0000-0000-0000-000000000001",
        parent_id=None,
        document_id="doc-a",
        document_name="Doc",
        document_version="v1",
        knowledge_type=KnowledgeType.TECHNICAL_GUIDE,
        domain="it",
        section="NAS",
        heading_path=["NAS"],
        chunk_index=0,
        content="Open NAS",
        source_path="doc.md",
        content_hash="hash-a",
    )

    class FakeClient:
        def __init__(self) -> None:
            self.query_points_calls: list[dict[str, object]] = []

        async def get_collections(self):
            return SimpleNamespace(collections=[SimpleNamespace(name="test_collection")])

        async def query_points(self, **kwargs):
            self.query_points_calls.append(kwargs)
            point = SimpleNamespace(payload=chunk.payload(), score=0.7)
            return SimpleNamespace(points=[point])

    fake_client = FakeClient()
    store.client = fake_client

    results = await store.search([0.1, 0.2], top_k=3)

    assert [result.chunk_id for result in results] == [chunk.chunk_id]
    assert results[0].score == 0.7
    assert fake_client.query_points_calls == [
        {
            "collection_name": "test_collection",
            "query": [0.1, 0.2],
            "limit": 3,
            "query_filter": None,
            "with_payload": True,
        }
    ]


@pytest.mark.asyncio
async def test_qdrant_list_document_chunks_uses_payload_filter() -> None:
    store = QdrantVectorStore(Settings(qdrant_collection="test_collection"))
    chunk = Chunk(
        chunk_id="00000000-0000-0000-0000-000000000001",
        parent_id=None,
        document_id="doc-a",
        document_name="Doc",
        document_version="v1",
        knowledge_type=KnowledgeType.TECHNICAL_GUIDE,
        domain="it",
        section="NAS",
        heading_path=["NAS"],
        chunk_index=0,
        content="Open NAS",
        source_path="doc.md",
        content_hash="hash-a",
    )

    class FakeClient:
        def __init__(self) -> None:
            self.scroll_calls: list[dict[str, object]] = []

        async def get_collections(self):
            return SimpleNamespace(collections=[SimpleNamespace(name="test_collection")])

        async def scroll(self, **kwargs):
            self.scroll_calls.append(kwargs)
            record = SimpleNamespace(payload=chunk.payload())
            return [record], None

    fake_client = FakeClient()
    store.client = fake_client

    results = await store.list_document_chunks("doc-a")

    assert [result.document_id for result in results] == ["doc-a"]
    assert fake_client.scroll_calls[0]["collection_name"] == "test_collection"
    assert fake_client.scroll_calls[0]["scroll_filter"] is not None
