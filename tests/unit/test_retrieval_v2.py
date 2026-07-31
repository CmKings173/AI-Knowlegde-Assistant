from __future__ import annotations

from app.config import Settings
from app.domain.enums import KnowledgeType
from app.domain.models import Chunk, RetrievalSignals
from app.rag.lexical import LexicalIndex
from app.rag.pipeline import _chunk_evidence
from app.rag.retriever import Retriever


def _chunk(chunk_id: str, content: str, score: float = 0.0) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        parent_id=None,
        document_id="doc-1",
        document_name="Tài liệu",
        document_version="1",
        knowledge_type=KnowledgeType.POLICY,
        domain="HR_POLICY",
        section="Nội quy",
        heading_path=["Nội quy"],
        chunk_index=0,
        content=content,
        source_path="source.docx",
        content_hash=f"hash-{chunk_id}",
        score=score,
    )


class FakeEmbeddingProvider:
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]


class FakeVectorStore:
    def __init__(self, dense: list[Chunk]) -> None:
        self.dense = dense

    async def list_chunks(self) -> list[Chunk]:
        return []

    async def search(self, query_vector, top_k, filters=None) -> list[Chunk]:
        return self.dense[:top_k]


class FakeLexicalIndex:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks

    def build(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks

    def search(self, query, top_k, filters=None) -> list[Chunk]:
        return self.chunks[:top_k]


async def test_retriever_preserves_dense_bm25_and_rrf_provenance() -> None:
    dense = [
        _chunk("shared", "quy định giờ làm", score=0.91),
        _chunk("dense-only", "thời gian", score=0.75),
    ]
    lexical = [
        _chunk("lexical-only", "giờ làm việc", score=8.0),
        _chunk("shared", "quy định giờ làm", score=6.5),
    ]
    retriever = Retriever(
        Settings(dense_top_k=5, lexical_top_k=5, fusion_top_k=5),
        FakeEmbeddingProvider(),
        FakeVectorStore(dense),
    )
    retriever.lexical_index = FakeLexicalIndex(lexical)
    retriever._loaded = True

    result = await retriever.retrieve("đi làm lúc mấy giờ")
    by_id = {chunk.chunk_id: chunk for chunk in result.chunks}

    assert by_id["shared"].retrieval == RetrievalSignals(
        dense_score=0.91,
        dense_rank=1,
        bm25_score=6.5,
        bm25_rank=2,
        rrf_score=by_id["shared"].score,
        matched_queries=("original",),
    )
    assert by_id["dense-only"].retrieval.dense_score == 0.75
    assert by_id["dense-only"].retrieval.bm25_score is None
    assert by_id["lexical-only"].retrieval.dense_score is None
    assert by_id["lexical-only"].retrieval.bm25_score == 8.0


def test_retrieval_signals_are_transient_and_not_written_to_payload() -> None:
    chunk = _chunk("one", "nội dung")
    chunk.retrieval = RetrievalSignals(
        dense_score=0.9,
        dense_rank=1,
        bm25_score=3.0,
        bm25_rank=2,
        rrf_score=0.03,
        matched_queries=("original",),
    )

    assert "retrieval" not in chunk.payload()


def test_retrieval_evidence_log_contains_raw_provenance() -> None:
    chunk = _chunk("one", "nội dung", score=0.03)
    chunk.retrieval = RetrievalSignals(
        dense_score=0.91,
        dense_rank=1,
        bm25_score=3.5,
        bm25_rank=2,
        rrf_score=0.03,
        matched_queries=("original", "quy trình nghỉ việc"),
    )

    evidence = _chunk_evidence(chunk)

    assert evidence["dense_score"] == 0.91
    assert evidence["bm25_rank"] == 2
    assert evidence["rrf_score"] == 0.03
    assert evidence["matched_queries"] == ["original", "quy trình nghỉ việc"]


def test_lexical_search_does_not_mutate_indexed_chunks() -> None:
    original = _chunk("one", "thời gian làm việc")
    index = LexicalIndex()
    index.build([original])

    results = index.search("thời gian làm việc", top_k=1)

    assert results[0].score > 0
    assert original.score == 0.0
