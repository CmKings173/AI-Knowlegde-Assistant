from pathlib import Path

from app.api.schemas import ChatRequest
from app.domain.enums import KnowledgeType
from app.domain.models import Chunk, RetrievalFilters, chunk_matches_filters
from app.providers.vector_store.qdrant_store import build_qdrant_filter
from app.rag.lexical import LexicalIndex


def make_chunk(
    chunk_id: str,
    content: str,
    *,
    document_id: str = "doc-a",
    knowledge_type: KnowledgeType = KnowledgeType.TECHNICAL_GUIDE,
    domain: str = "it",
    language: str = "vi",
    is_parent: bool = False,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        parent_id=None,
        document_id=document_id,
        document_name=document_id,
        document_version="v1",
        knowledge_type=knowledge_type,
        domain=domain,
        section="Email",
        heading_path=["Email"],
        chunk_index=0,
        content=content,
        source_path=str(Path("source.docx")),
        content_hash=chunk_id,
        language=language,
        is_parent=is_parent,
    )


def test_lexical_search_applies_metadata_filters_before_ranking() -> None:
    index = LexicalIndex()
    index.build(
        [
            make_chunk(
                "00000000-0000-0000-0000-000000000001",
                "smtp email config",
                document_id="doc-a",
            ),
            make_chunk(
                "00000000-0000-0000-0000-000000000002",
                "nas folder access",
                document_id="doc-b",
            ),
            make_chunk(
                "00000000-0000-0000-0000-000000000005",
                "vpn guide setup",
                document_id="doc-c",
            ),
            make_chunk(
                "00000000-0000-0000-0000-000000000003",
                "smtp email policy",
                domain="hr",
            ),
            make_chunk(
                "00000000-0000-0000-0000-000000000004",
                "smtp email parent",
                is_parent=True,
            ),
        ]
    )

    results = index.search(
        "smtp",
        top_k=10,
        filters=RetrievalFilters(
            domains=["it"],
            language="vi",
            include_parent_chunks=False,
        ),
    )

    assert [chunk.document_id for chunk in results] == ["doc-a"]
    assert all(not chunk.is_parent for chunk in results)


def test_selected_document_scope_with_empty_ids_matches_no_chunks() -> None:
    chunk = make_chunk("00000000-0000-0000-0000-000000000006", "smtp email config")
    filters = RetrievalFilters(document_scope="selected", document_ids=[])
    index = LexicalIndex()
    index.build([chunk])

    assert not chunk_matches_filters(chunk, filters)
    assert index.search("smtp", top_k=10, filters=filters) == []


def test_qdrant_filter_contains_supported_metadata_conditions() -> None:
    query_filter = build_qdrant_filter(
        RetrievalFilters(
            document_ids=["doc-a", "doc-b"],
            knowledge_types=[KnowledgeType.SOP],
            domains=["it"],
            language="vi",
            include_parent_chunks=False,
        )
    )

    assert query_filter is not None
    condition_keys = [condition.key for condition in query_filter.must]
    assert condition_keys == [
        "document_id",
        "knowledge_type",
        "domain",
        "language",
        "is_parent",
    ]


def test_chat_request_filters_convert_to_retrieval_filters() -> None:
    request = ChatRequest(
        question="Cach cau hinh email?",
        filters={
            "document_scope": "selected",
            "document_ids": ["doc-a"],
            "knowledge_types": ["TECHNICAL_GUIDE"],
            "domains": ["it"],
            "language": "vi",
            "include_parent_chunks": False,
        },
    )

    filters = request.retrieval_filters()

    assert filters is not None
    assert filters.document_scope == "selected"
    assert filters.document_ids == ["doc-a"]
    assert filters.knowledge_types == [KnowledgeType.TECHNICAL_GUIDE]
    assert filters.domains == ["it"]
    assert filters.language == "vi"
    assert filters.include_parent_chunks is False
