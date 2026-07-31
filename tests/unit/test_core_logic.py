from pathlib import Path

import pytest
from pydantic import ValidationError

from app.api.schemas import ChatResponse
from app.config import Settings
from app.domain.enums import KnowledgeType
from app.domain.models import Chunk, DocumentInfo, ParsedElement, RetrievalFilters, RetrievalResult
from app.ingestion.chunker import ChunkingConfig, chunk_document, detect_heading
from app.ingestion.classifier import classify_knowledge_type
from app.providers.embeddings import api_provider
from app.providers.embeddings.api_provider import OllamaEmbeddingProvider, create_embedding_provider
from app.rag.citation_builder import build_citations
from app.rag.execution.conversation_stream import LANGUAGE_FALLBACK_VI
from app.rag.fact_guard import extract_facts, validate_fact_consistency
from app.rag.hybrid_search import reciprocal_rank_fusion
from app.rag.intent_router import FollowUpSubtype, Intent, IntentRouter
from app.rag.lexical import LexicalIndex
from app.rag.pipeline import (
    CLARIFY_RESPONSE,
    CONVERSATIONAL_RESPONSE,
    GENERATION_FAILED_RESPONSE,
    NO_DOCUMENTS_SELECTED_RESPONSE,
    OUT_OF_SCOPE_EMOTION_RESPONSE,
    OUT_OF_SCOPE_LEISURE_RESPONSE,
    OUT_OF_SCOPE_RESPONSE,
    REFUSAL,
    REPEATED_OUT_OF_SCOPE_RESPONSE,
    RAGPipeline,
    parse_model_output,
    parse_query_rewrite_output,
    parse_router_output,
)
from app.rag.prompts import (
    CONVERSATIONAL_STREAM_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_conversation_stream_prompt,
    build_user_prompt,
)
from app.rag.response_validator import (
    contains_disallowed_cjk,
    filter_citation_ids,
    has_refusal_text,
    remove_unknown_citations,
    should_refuse,
)
from app.rag.section_expander import expand_section_chunks
from app.utils.hashing import sha256_text, stable_document_id
from app.utils.text import normalize_for_intent, normalize_query


def test_normalize_query_keeps_technical_tokens() -> None:
    query = "  mở   \\\\10.10.10.200   port 465 SMTP  "
    assert normalize_query(query) == "mở \\\\10.10.10.200 port 465 SMTP"


def test_normalize_for_intent_strips_vietnamese_marks() -> None:
    assert normalize_for_intent("  Xem  tiếp nhé  ") == "xem tiep nhe"
    assert normalize_for_intent("Bạn nói đúng không?") == "ban noi dung khong?"


def test_settings_replaces_blank_continuation_secret() -> None:
    assert Settings(continuation_secret="").continuation_secret


def test_classifier_detects_policy_and_troubleshooting() -> None:
    assert (
        classify_knowledge_type("Điều 1: Nhân viên phải tuân thủ nội quy")
        == KnowledgeType.POLICY
    )
    assert (
        classify_knowledge_type("Lỗi không truy cập được NAS và cách khắc phục")
        == KnowledgeType.TROUBLESHOOTING
    )


def test_heading_detection_supports_vietnamese_policy_patterns() -> None:
    assert detect_heading("Phần I: Nội quy công ty") == (1, "Phần I: Nội quy công ty")
    assert detect_heading("Điều 1: Thời gian làm việc") == (2, "Điều 1: Thời gian làm việc")


def test_chunker_keeps_heading_path_and_parent_child_links() -> None:
    document = DocumentInfo(
        document_id=stable_document_id("Noi Quy.docx"),
        document_name="Noi Quy",
        source_path=Path("data/uploads/Noi Quy.docx"),
        file_hash=sha256_text("file"),
    )
    elements = [
        ParsedElement("Phần I: Nội quy công ty"),
        ParsedElement("Điều 1: Thời gian làm việc"),
        ParsedElement("- Làm việc từ 8:00 đến 17:30."),
        ParsedElement("- Nghỉ trưa từ 12:00 đến 13:30."),
    ]
    chunks = chunk_document(document, elements, ChunkingConfig(max_tokens=20))
    assert any(chunk.is_parent for chunk in chunks)
    child = next(chunk for chunk in chunks if not chunk.is_parent)
    assert child.parent_id is not None
    assert child.heading_path == ["Phần I: Nội quy công ty", "Điều 1: Thời gian làm việc"]
    assert "8:00" in child.content


def test_rrf_merges_duplicate_candidates() -> None:
    fused = reciprocal_rank_fusion(
        [[("a", 0.9), ("b", 0.8)], [("b", 0.7), ("c", 0.6)]],
        top_k=3,
    )
    assert [item[0] for item in fused] == ["b", "a", "c"]


def test_lexical_index_uses_section_and_heading_path() -> None:
    internal = _section_chunk(
        "B\u1ea5m Windows + R, sau \u0111\u00f3 g\u00f5 \\\\10.10.10.200.",
        ["Qu\u1ea3n l\u00fd NAS", "Truy c\u1eadp v\u00e0o NAS t\u1eeb m\u1ea1ng n\u1ed9i b\u1ed9"],
        1,
    )
    mobile = _section_chunk(
        "T\u00ecm \u1ee9ng d\u1ee5ng WebAccess A v\u00e0 c\u00e0i \u0111\u1eb7t.",
        [
            "Qu\u1ea3n l\u00fd NAS",
            "Truy c\u1eadp v\u00e0o NAS b\u1eb1ng APP Mobile (V\u1edbi m\u1ea1ng ngo\u00e0i)",
        ],
        2,
    )
    index = LexicalIndex()
    index.build([internal, mobile])

    results = index.search("truy cap NAS bang app mobile mang ngoai", top_k=2)

    assert results
    assert results[0].chunk_id == mobile.chunk_id


def test_citation_validator_drops_unknown_source_ids() -> None:
    document = DocumentInfo(
        document_id="doc",
        document_name="Doc",
        source_path=Path("doc.docx"),
        file_hash="v1",
    )
    chunk = chunk_document(
        document,
        [ParsedElement("NAS", style="Heading 1"), ParsedElement("Nhấn Windows + R")],
        ChunkingConfig(),
    )[0]
    citations = build_citations([chunk])
    assert filter_citation_ids("Theo SOURCE_1 và SOURCE_999", citations) == {"SOURCE_1"}
    assert remove_unknown_citations("Theo SOURCE_1 và SOURCE_999", citations) == "Theo SOURCE_1 và "


def test_refusal_logic_uses_candidate_count_and_score() -> None:
    assert should_refuse(candidate_count=0, best_score=1.0, min_score=0.25)
    assert should_refuse(candidate_count=2, best_score=0.1, min_score=0.25)
    assert not should_refuse(candidate_count=2, best_score=0.5, min_score=0.25)


def test_fact_guard_normalizes_vietnamese_day_and_time_aliases() -> None:
    facts = extract_facts(
        "S\u00e1ng th\u1ee9 b\u1ea3y l\u00e0m vi\u1ec7c t\u1eeb 8h00 "
        "\u0111\u1ebfn 12:00. Chi\u1ec1u th\u1ee9 2 v\u00e0o l\u00fac 1h30 chi\u1ec1u."
    )

    assert facts.days == {"SAT", "MON"}
    assert facts.times == {"08:00", "12:00", "13:30"}


def test_fact_guard_normalizes_vietnamese_gio_phut_format() -> None:
    facts = extract_facts(
        "Th\u1eddi gian l\u00e0m vi\u1ec7c t\u1eeb 8 gi\u1edd 00 s\u00e1ng "
        "\u0111\u1ebfn 17 gi\u1edd 30 chi\u1ec1u. H\u1ecdp l\u00fac 5h30 chi\u1ec1u."
    )

    assert facts.times == {"08:00", "17:30"}


def test_fact_guard_rejects_day_not_supported_by_context() -> None:
    result = validate_fact_consistency(
        "S\u00e1ng ch\u1ee7 nh\u1eadt l\u00e0m vi\u1ec7c t\u1eeb 8:00 "
        "\u0111\u1ebfn 12:00. [SOURCE_1]",
        "S\u00e1ng th\u1ee9 7 l\u00e0m vi\u1ec7c t\u1eeb 8:00 "
        "\u0111\u1ebfn 12:00 \u0111\u1ed1i v\u1edbi ng\u01b0\u1eddi c\u00f3 l\u1ecbch.",
    )

    assert not result.passed
    assert result.reason == "unsupported_day:SUN"


def test_fact_guard_rejects_mobile_claim_not_supported_by_context() -> None:
    result = validate_fact_consistency(
        (
            "\u0110\u1ec3 truy c\u1eadp NAS b\u1eb1ng \u1ee9ng d\u1ee5ng "
            "di \u0111\u1ed9ng, b\u1ea1n c\u00e0i app mobile. [SOURCE_1]"
        ),
        (
            "Khi k\u1ebft n\u1ed1i v\u1edbi m\u1ea1ng wifi t\u1ea1i c\u00f4ng ty, "
            "tr\u00ean laptop b\u1ea5m Windows + R, sau \u0111\u00f3 g\u00f5 "
            "\u0111\u01b0\u1eddng d\u1eabn \\\\10.10.10.200."
        ),
    )

    assert not result.passed
    assert result.reason == "unsupported_support_term:NAS_MOBILE"


def test_citation_builder_includes_full_content_blocks_and_image_anchors() -> None:
    chunk = _chunk(
        "B\u01b0\u1edbc 1: Nh\u1ea5n Windows + R."
        "\n\n"
        "B\u01b0\u1edbc 2: Nh\u1eadp \\\\10.10.10.200."
    )
    chunk.image_ids = ["img-1"]
    citations = build_citations(
        [chunk],
        {
            "img-1": {
                "image_id": "img-1",
                "file_name": "run.png",
                "url": "/api/v1/documents/doc-a/images/run.png",
                "anchor_text": "Nh\u1ea5n Windows + R",
            }
        },
    )

    citation = citations[0]

    assert citation.content == chunk.content
    assert citation.content_blocks[0].text == "B\u01b0\u1edbc 1: Nh\u1ea5n Windows + R."
    assert citation.content_blocks[0].images[0]["file_name"] == "run.png"
    assert citation.content_blocks[1].text == "B\u01b0\u1edbc 2: Nh\u1eadp \\\\10.10.10.200."
    assert citation.content_blocks[1].images == []


def test_citation_builder_does_not_attach_unmatched_images_to_wrong_text() -> None:
    chunk = _chunk(
        "B\u01b0\u1edbc 1: M\u1edf Control Panel."
        "\n\n"
        "B\u01b0\u1edbc 2: Ch\u1ecdn Credential Manager."
    )
    chunk.image_ids = ["img-1"]
    citations = build_citations(
        [chunk],
        {
            "img-1": {
                "image_id": "img-1",
                "file_name": "unknown-anchor.png",
                "url": "/api/v1/documents/doc-a/images/unknown-anchor.png",
                "anchor_text": "Kh\u00f4ng kh\u1edbp \u0111o\u1ea1n n\u00e0o",
            }
        },
    )

    citation = citations[0]

    assert citation.content_blocks[0].images == []
    assert citation.content_blocks[1].images == []
    assert citation.content_blocks[2].text == ""
    assert citation.content_blocks[2].images[0]["file_name"] == "unknown-anchor.png"


def test_user_facing_pipeline_copy_has_vietnamese_marks() -> None:
    assert REFUSAL == (
        "T\u00f4i ch\u01b0a t\u00ecm th\u1ea5y th\u00f4ng tin n\u00e0y "
        "trong t\u00e0i li\u1ec7u n\u1ed9i b\u1ed9 hi\u1ec7n c\u00f3."
    )
    assert (
        "Tr\u1ee3 l\u00fd Ki\u1ebfn th\u1ee9c N\u1ed9i b\u1ed9 Vi\u1ec7t Th\u00e1i D\u01b0\u01a1ng"
        in CONVERSATIONAL_RESPONSE
    )
    assert "N\u00f3i r\u00f5 th\u00eam gi\u00fap m\u00ecnh" in CLARIFY_RESPONSE
    assert (
        OUT_OF_SCOPE_RESPONSE
        == "C\u00e2u h\u1ecfi n\u00e0y n\u1eb1m ngo\u00e0i ph\u1ea1m vi "
        "kho ki\u1ebfn th\u1ee9c n\u1ed9i b\u1ed9 hi\u1ec7n c\u00f3. "
        "M\u00ecnh c\u00f3 th\u1ec3 h\u1ed7 tr\u1ee3 b\u1ea1n tra c\u1ee9u "
        "n\u1ed9i quy, ch\u00ednh s\u00e1ch, SOP, NAS, Outlook, email, "
        "Windows v\u00e0 troubleshooting trong t\u00e0i li\u1ec7u n\u1ed9i b\u1ed9."
    )


def test_chunker_default_section_title_is_valid_vietnamese() -> None:
    document = DocumentInfo(
        document_id=stable_document_id("FAQ.txt"),
        document_name="FAQ",
        source_path=Path("data/uploads/FAQ.txt"),
        file_hash=sha256_text("file"),
    )

    chunks = chunk_document(
        document,
        [ParsedElement("N\u1ed9i dung kh\u00f4ng c\u00f3 heading.")],
        ChunkingConfig(max_tokens=20),
    )

    assert chunks[0].section == "T\u00e0i li\u1ec7u"


def test_system_prompt_matches_current_context_format() -> None:
    assert "[SOURCE_X]" in SYSTEM_PROMPT
    assert "Tai lieu:" in SYSTEM_PROMPT
    assert "Muc:" in SYSTEM_PROMPT
    assert "Noi dung:" in SYSTEM_PROMPT
    assert "toi da 150 tu" in SYSTEM_PROMPT
    assert "JSON object hop le" in SYSTEM_PROMPT
    assert '"status"' in SYSTEM_PROMPT
    assert '"answer"' in SYSTEM_PROMPT
    assert '"sources"' in SYSTEM_PROMPT
    assert "answered" in SYSTEM_PROMPT
    assert "partial" in SYSTEM_PROMPT
    assert "insufficient_context" in SYSTEM_PROMPT
    assert "out_of_scope" in SYSTEM_PROMPT
    assert "conflict" in SYSTEM_PROMPT
    assert "Chrome" in SYSTEM_PROMPT
    assert "bookmark" in SYSTEM_PROMPT
    assert "tu choi nhe nhang" in SYSTEM_PROMPT
    assert "escape dung theo chuan JSON" in SYSTEM_PROMPT
    assert "sources giu thu tu xuat hien lan dau" in SYSTEM_PROMPT
    assert "khong phai nguon nghiep vu that" in SYSTEM_PROMPT
    assert "Vi du 1" in SYSTEM_PROMPT
    assert "Vi du 2" in SYSTEM_PROMPT
    assert "Vi du 3" in SYSTEM_PROMPT
    assert "Knowledge type:" not in SYSTEM_PROMPT

    user_prompt = build_user_prompt("NAS la gi?", "[SOURCE_1]\nTai lieu: Doc\nMuc: NAS")
    assert "CONTEXT:" in user_prompt
    assert "CAU HOI:" in user_prompt
    assert "JSON hop le" in user_prompt
    assert "NAS la gi?" in user_prompt

    stream_prompt = build_conversation_stream_prompt("hello", [])
    assert "JSON hop le" not in stream_prompt
    assert "Hay tra loi truc tiep bang tieng Viet co dau" in stream_prompt
    assert "khong nhac lai huong dan noi bo" in stream_prompt
    assert "khong dung tieng Trung" in CONVERSATIONAL_STREAM_SYSTEM_PROMPT
    assert "system prompt" in CONVERSATIONAL_STREAM_SYSTEM_PROMPT


def test_refusal_detection_uses_current_vietnamese_messages() -> None:
    assert has_refusal_text("Tôi chưa tìm thấy thông tin này trong tài liệu nội bộ hiện có.")
    assert has_refusal_text("Câu hỏi này nằm ngoài phạm vi kho kiến thức nội bộ hiện có.")


def test_response_validator_rejects_cjk_output() -> None:
    assert contains_disallowed_cjk("Xin chao, \u6211\u53ef\u4ee5 giup ban.")
    assert not contains_disallowed_cjk("Xin chao, toi co the ho tro ban.")


@pytest.mark.asyncio
async def test_ollama_embedding_provider_uses_batch_embed_endpoint(monkeypatch) -> None:
    class FakeResponse:
        status_code = 200

        def json(self):
            return {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}

    class FakeClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout
            self.calls: list[dict[str, object]] = []

        async def post(self, url: str, json: dict[str, object]):
            self.calls.append({"url": url, "json": json})
            return FakeResponse()

    fake_client = FakeClient(timeout=30)
    monkeypatch.setattr(api_provider.httpx, "AsyncClient", lambda timeout: fake_client)
    settings = Settings(
        embedding_provider="ollama",
        ollama_base_url="http://10.10.12.158:11434",
        ollama_embedding_model="bge-m3",
    )
    provider = create_embedding_provider(settings)

    vectors = await provider.embed_texts(["mot", "hai"])

    assert isinstance(provider, OllamaEmbeddingProvider)
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert fake_client.calls == [
        {
            "url": "http://10.10.12.158:11434/api/embed",
            "json": {"model": "bge-m3", "input": ["mot", "hai"]},
        }
    ]


def test_intent_router_detects_conversational_messages() -> None:
    router = IntentRouter()

    assert router.classify("hello").intent == Intent.CONVERSATIONAL_LLM
    assert router.classify("xin chao").intent == Intent.CONVERSATIONAL_LLM
    assert router.classify("ban la ai").intent == Intent.CONVERSATIONAL_LLM
    assert router.classify("toi thich an pho").intent == Intent.OUT_OF_SCOPE
    assert router.classify("xin chao", has_history=True).intent == Intent.FOLLOW_UP


def test_intent_router_detects_follow_up_challenge_with_history() -> None:
    router = IntentRouter()

    decision = router.classify("ban co chac kien thuc ban dang noi la dung", has_history=True)

    assert decision.intent == Intent.FOLLOW_UP
    assert decision.subtype == "source_challenge"
    assert router.classify("the con buoc 2 thi sao", has_history=True).intent == Intent.FOLLOW_UP
    assert router.classify("the con buoc 2 thi sao", has_history=True).subtype == (
        "knowledge_follow_up"
    )
    assert router.classify("tiep di", has_history=True).intent == Intent.FOLLOW_UP
    assert router.classify("tiep di", has_history=True).subtype == "continuation"
    assert router.classify("ok", has_history=True).intent == Intent.FOLLOW_UP
    assert router.classify("ok", has_history=True).subtype == "casual_follow_up"
    assert router.classify("nguon o dau hay ban tu suy", has_history=True).intent == (
        Intent.FOLLOW_UP
    )
    assert router.classify("sao ma ngan vay", has_history=True).intent == Intent.FOLLOW_UP


def test_intent_router_detects_internal_knowledge_queries() -> None:
    router = IntentRouter()

    assert router.classify("Outlook khong gui duoc mail").intent == Intent.KNOWLEDGE_QUERY
    assert router.classify("cach mo NAS").intent == Intent.KNOWLEDGE_QUERY
    assert router.classify("Backup bookmark Chrome nhu the nao?").intent == Intent.KNOWLEDGE_QUERY
    assert router.classify("toi can biet ve van hoa cong ty").intent == Intent.KNOWLEDGE_QUERY
    assert router.classify("m\u1ea5y h l\u00e0m v\u00e0 m\u1ea5y h v\u1ec1").intent == (
        Intent.KNOWLEDGE_QUERY
    )


def test_intent_router_detects_broad_section_queries() -> None:
    router = IntentRouter()

    assert router.classify("noi quy cong ty gom nhung gi").intent == Intent.BROAD_SECTION_QUERY
    assert router.classify("liet ke toan bo cac dieu trong noi quy").intent == (
        Intent.BROAD_SECTION_QUERY
    )
    assert router.classify("noi quy ve thoi gian lam viec").intent == Intent.KNOWLEDGE_QUERY


def test_intent_router_detects_out_of_scope_messages() -> None:
    router = IntentRouter()

    assert router.classify("thoi tiet hom nay the nao").intent == Intent.OUT_OF_SCOPE
    assert router.classify(
        "toi muon di da nang 2 ngay 1 dem, ban hay len plan cho toi"
    ).intent == Intent.OUT_OF_SCOPE
    assert router.classify("lam sao de cong viec tro nen thu vi hon").intent == (
        Intent.OUT_OF_SCOPE
    )
    assert router.classify("co toi quan li tai chinh kem qua").intent == Intent.OUT_OF_SCOPE
    assert router.classify("toi no 100tr va dang tim cach tra").intent == Intent.OUT_OF_SCOPE
    assert router.classify("hom nay toi buon").intent == Intent.OUT_OF_SCOPE
    assert router.classify("minh stress qua").intent == Intent.OUT_OF_SCOPE
    assert router.classify("hay toi nen tu tu").intent == Intent.OUT_OF_SCOPE
    assert router.classify("huong dan toi di").intent == Intent.CLARIFY
    cat_decision = router.classify(
        "k\u1ec3 t\u00ean c\u00e1c gi\u1ed1ng m\u00e8o \u1edf Vi\u1ec7t Nam"
    )

    assert cat_decision.intent == Intent.OUT_OF_SCOPE


def test_intent_router_detects_mobile_detail_follow_up_with_history() -> None:
    router = IntentRouter()

    mobile = router.classify("d\u00f9ng app mobile \u0111i", has_history=True)
    detail = router.classify(
        "c\u00f3 h\u00e3y h\u01b0\u1edbng d\u1eabn chi ti\u1ebft cho t\u00f4i",
        has_history=True,
    )

    assert mobile.intent == Intent.FOLLOW_UP
    assert mobile.subtype == FollowUpSubtype.KNOWLEDGE_FOLLOW_UP
    assert detail.intent == Intent.FOLLOW_UP
    assert detail.subtype == FollowUpSubtype.KNOWLEDGE_FOLLOW_UP


def test_expand_section_chunks_uses_anchor_root_and_document_order() -> None:
    chunks = [
        _section_chunk("intro", ["Phan I: Noi quy"], 0),
        _section_chunk("dieu 1", ["Phan I: Noi quy", "Dieu 1"], 1),
        _section_chunk("dieu 2", ["Phan I: Noi quy", "Dieu 2"], 2),
        _section_chunk("other", ["Phan II: Van hoa"], 3),
        _section_chunk("other doc", ["Phan I: Noi quy"], 0, document_id="doc-b"),
    ]

    selection = expand_section_chunks([chunks[1]], chunks)

    assert selection is not None
    assert selection.document_id == "doc-a"
    assert selection.section_root == "Phan I: Noi quy"
    assert [chunk.content for chunk in selection.chunks] == ["intro", "dieu 1", "dieu 2"]


def test_parse_model_output_accepts_json_and_sources() -> None:
    parsed = parse_model_output(
        (
            '{"status": "answered", "answer": "Mở File Explorer. [SOURCE_1]", '
            '"sources": ["SOURCE_1"]}'
        ),
        {"SOURCE_1"},
    )

    assert parsed.is_valid
    assert parsed.status == "answered"
    assert parsed.answer == "Mở File Explorer. [SOURCE_1]"
    assert parsed.sources == ["SOURCE_1"]


def test_parse_model_output_rejects_status_outside_allowed_set() -> None:
    parsed = parse_model_output(
        '{"status": "conversational", "answer": "Chao ban.", "sources": []}',
        {"SOURCE_1"},
        allowed_statuses={"answered", "partial", "insufficient_context"},
    )

    assert not parsed.is_valid
    assert parsed.error == "invalid_status"


def test_parse_router_output_accepts_structured_decision() -> None:
    parsed = parse_router_output(
        '{"intent": "follow_up", "subtype": "knowledge_follow_up", '
        '"confidence": 0.82, "reason": "depends on previous answer"}'
    )

    assert parsed is not None
    assert parsed.intent == Intent.FOLLOW_UP
    assert parsed.subtype == "knowledge_follow_up"
    assert parsed.llm_router_used


def test_parse_router_output_rejects_invalid_json() -> None:
    assert parse_router_output("not json") is None
    assert parse_router_output('{"intent": "unknown"}') is None


def test_parse_query_rewrite_output_returns_bounded_query() -> None:
    assert parse_query_rewrite_output('{"query": "noi quy cong ty thu 7"}') == (
        "noi quy cong ty thu 7"
    )
    assert parse_query_rewrite_output("not json") == ""


def test_parse_model_output_rejects_text_when_not_json() -> None:
    parsed = parse_model_output("Mở File Explorer. SOURCE_1", {"SOURCE_1"})

    assert not parsed.is_valid
    assert parsed.error == "invalid_json"


def test_parse_model_output_rejects_source_mismatch() -> None:
    parsed = parse_model_output(
        (
            '{"status": "answered", "answer": "Mở File Explorer. [SOURCE_1]", '
            '"sources": ["SOURCE_2"]}'
        ),
        {"SOURCE_1", "SOURCE_2"},
    )

    assert not parsed.is_valid
    assert parsed.error == "source_mismatch"


def test_parse_model_output_rejects_duplicate_or_unavailable_sources() -> None:
    duplicate = parse_model_output(
        (
            '{"status": "answered", "answer": "Theo [SOURCE_1]. [SOURCE_1]", '
            '"sources": ["SOURCE_1", "SOURCE_1"]}'
        ),
        {"SOURCE_1"},
    )
    unavailable = parse_model_output(
        (
            '{"status": "answered", "answer": "Theo [SOURCE_999].", '
            '"sources": ["SOURCE_999"]}'
        ),
        {"SOURCE_1"},
    )

    assert not duplicate.is_valid
    assert duplicate.error == "duplicate_sources"
    assert not unavailable.is_valid
    assert unavailable.error == "unknown_source"


def test_parse_model_output_preserves_escaped_windows_path() -> None:
    parsed = parse_model_output(
        (
            r'{"status": "answered", '
            r'"answer": "Mở C:\\Users\\Admin\\AppData. [SOURCE_1]", '
            r'"sources": ["SOURCE_1"]}'
        ),
        {"SOURCE_1"},
    )

    assert parsed.is_valid
    assert parsed.answer == r"Mở C:\Users\Admin\AppData. [SOURCE_1]"


def test_chat_response_requires_status() -> None:
    response = ChatResponse(
        status="answered",
        answer="Mở File Explorer. [SOURCE_1]",
        citations=[
            {
                "citation_id": "SOURCE_1",
                "document_name": "Doc",
                "section": "NAS",
                "chunk_id": "chunk-a",
                "excerpt": "Mở File Explorer.",
                "images": [],
            }
        ],
        retrieval={"candidate_count": 1, "context_count": 1, "reranker_used": False},
        timing_ms={"total": 1},
    )

    assert response.status == "answered"

    conversational_response = ChatResponse(
        status="conversational",
        answer="Chao ban.",
        citations=[],
        retrieval={"candidate_count": 0, "context_count": 0, "reranker_used": False},
        timing_ms={"total": 1},
    )

    assert conversational_response.status == "conversational"

    clarify_response = ChatResponse(
        status="clarify",
        answer="Ban dang hoi ve NAS hay Outlook?",
        citations=[],
        retrieval={"candidate_count": 0, "context_count": 0, "reranker_used": False},
        timing_ms={"total": 1},
        trace={
            "intent": "clarify",
            "confidence": 0.5,
            "reason": "missing_entity",
            "branch": "clarify",
        },
    )

    assert clarify_response.status == "clarify"
    assert clarify_response.trace is not None
    assert clarify_response.trace.branch == "clarify"

    continuation_response = ChatResponse(
        status="partial",
        answer="Dieu 1. [SOURCE_1]",
        citations=[
            {
                "citation_id": "SOURCE_1",
                "document_name": "Doc",
                "section": "Noi quy",
                "chunk_id": "chunk-a",
                "excerpt": "Dieu 1.",
                "images": [],
            }
        ],
        retrieval={"candidate_count": 3, "context_count": 1, "reranker_used": False},
        timing_ms={"total": 1},
        continuation={
            "has_more": True,
            "mode": "broad_section",
            "document_id": "doc-a",
            "section_root": "Phan I: Noi quy",
            "next_offset": 1,
            "source_question": "noi quy cong ty gom nhung gi",
            "token": "x" * 64,
        },
    )

    assert continuation_response.continuation is not None
    assert continuation_response.continuation.next_offset == 1

    try:
        ChatResponse(
            answer="Mở File Explorer. [SOURCE_1]",
            citations=[],
            retrieval={"candidate_count": 1, "context_count": 1, "reranker_used": False},
            timing_ms={"total": 1},
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("ChatResponse must require status")


@pytest.mark.asyncio
async def test_pipeline_uses_llm_without_retrieval_for_greeting(tmp_path: Path) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("retriever should not be called")

    class FakeLLM:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.calls.append((system_prompt, user_prompt))
            return (
                '{"status": "conversational", '
                '"answer": "Chao ban, minh co the ho tro tra cuu thong tin noi bo.", '
                '"sources": []}'
            )

    llm = FakeLLM()
    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), llm)

    result = await pipeline.answer("hello")

    assert result["status"] == "conversational"
    assert result["answer"] == "Chao ban, minh co the ho tro tra cuu thong tin noi bo."
    assert result["citations"] == []
    assert result["retrieval"] == {
        "candidate_count": 0,
        "context_count": 0,
        "reranker_used": False,
    }
    assert llm.calls


@pytest.mark.asyncio
async def test_pipeline_refuses_personal_emotional_query_without_llm(tmp_path: Path) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("retriever should not be called")

    class FailLLM:
        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            raise AssertionError("llm should not be called")

    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), FailLLM())

    result = await pipeline.answer("hom nay toi buon")

    assert result["status"] == "out_of_scope"
    assert result["answer"] == OUT_OF_SCOPE_EMOTION_RESPONSE
    assert result["citations"] == []
    assert result["retrieval"] == {
        "candidate_count": 0,
        "context_count": 0,
        "reranker_used": False,
    }


@pytest.mark.asyncio
async def test_pipeline_uses_distinct_out_of_scope_responses_by_subtype(
    tmp_path: Path,
) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("retriever should not be called")

    class FailLLM:
        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            raise AssertionError("llm should not be called")

    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), FailLLM())

    leisure = await pipeline.answer("toi muon di choi")
    repeated = await pipeline.answer(
        "toi chan qua",
        history=[
            {"role": "assistant", "content": OUT_OF_SCOPE_EMOTION_RESPONSE},
            {"role": "assistant", "content": OUT_OF_SCOPE_LEISURE_RESPONSE},
        ],
    )

    assert leisure["status"] == "out_of_scope"
    assert leisure["answer"] == OUT_OF_SCOPE_LEISURE_RESPONSE
    assert repeated["status"] == "out_of_scope"
    assert repeated["answer"] == REPEATED_OUT_OF_SCOPE_RESPONSE


@pytest.mark.asyncio
async def test_pipeline_clarifies_when_no_documents_are_selected(tmp_path: Path) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("retriever should not be called")

    class FailLLM:
        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            raise AssertionError("llm should not be called")

    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), FailLLM())

    result = await pipeline.answer(
        "Outlook khong gui duoc mail",
        filters=RetrievalFilters(document_scope="selected", document_ids=[]),
    )

    assert result["status"] == "clarify"
    assert result["answer"] == NO_DOCUMENTS_SELECTED_RESPONSE
    assert result["retrieval"] == {
        "candidate_count": 0,
        "context_count": 0,
        "reranker_used": False,
    }


@pytest.mark.asyncio
async def test_pipeline_uses_llm_for_identity_question(tmp_path: Path) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("retriever should not be called")

    class FakeLLM:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.calls.append((system_prompt, user_prompt))
            return (
                '{"status": "conversational", '
                '"answer": "Minh la tro ly tra cuu thong tin noi bo.", '
                '"sources": []}'
            )

    llm = FakeLLM()
    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), llm)

    result = await pipeline.answer("ban la ai")

    assert result["status"] == "conversational"
    assert result["answer"] == "Minh la tro ly tra cuu thong tin noi bo."
    assert result["retrieval"]["candidate_count"] == 0
    assert llm.calls


@pytest.mark.asyncio
async def test_pipeline_streams_conversational_tokens(tmp_path: Path) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("streamed follow-up reply should not retrieve")

    class FakeLLM:
        async def stream_generate(self, system_prompt: str, user_prompt: str):
            del system_prompt
            assert "co chac khong" in user_prompt
            yield "M\u00ecnh "
            yield "s\u1ebd ki\u1ec3m tra l\u1ea1i theo ngu\u1ed3n."

    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), FakeLLM())

    events = [
        event
        async for event in pipeline.answer_stream(
            "co chac khong",
            history=[
                {"role": "assistant", "content": "N\u1ed9i dung tr\u01b0\u1edbc. [SOURCE_1]"}
            ],
        )
    ]

    assert [event["event"] for event in events] == [
        "progress",
        "progress",
        "delta",
        "final",
    ]
    assert events[2]["data"] == {
        "text": "M\u00ecnh s\u1ebd ki\u1ec3m tra l\u1ea1i theo ngu\u1ed3n."
    }
    assert events[-1]["data"]["status"] == "conversational"
    assert events[-1]["data"]["answer"] == (
        "M\u00ecnh s\u1ebd ki\u1ec3m tra l\u1ea1i theo ngu\u1ed3n."
    )
    assert events[-1]["data"]["trace"]["branch"] == "conversation_stream"


@pytest.mark.asyncio
async def test_pipeline_stream_buffers_and_blocks_cjk_tokens(tmp_path: Path) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("streamed follow-up reply should not retrieve")

    class FakeLLM:
        async def stream_generate(self, system_prompt: str, user_prompt: str):
            del system_prompt, user_prompt
            yield "R\u1ea5t ti\u1ebfc, "
            yield "\u6211\u53ef\u4ee5 giup ban."

    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), FakeLLM())

    events = [
        event
        async for event in pipeline.answer_stream(
            "co chac khong",
            history=[{"role": "assistant", "content": "Noi dung truoc. [SOURCE_1]"}],
        )
    ]

    delta_text = "".join(
        event["data"]["text"] for event in events if event["event"] == "delta"
    )
    assert "\u6211" not in delta_text
    assert events[-1]["data"]["answer"] == LANGUAGE_FALLBACK_VI
    assert events[-1]["data"]["trace"]["language_retry_used"]
    assert events[-1]["data"]["trace"]["language_fallback_used"]


@pytest.mark.asyncio
async def test_pipeline_guarded_stream_rejects_raw_english_tokens(
    tmp_path: Path,
) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("conversational reply should not retrieve")

    class FakeLLM:
        def __init__(self) -> None:
            self.stream_calls = 0
            self.generate_calls = 0

        async def stream_generate(self, system_prompt: str, user_prompt: str):
            self.stream_calls += 1
            yield "bad raw token"

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.generate_calls += 1
            return (
                '{"status": "conversational", '
                '"answer": "C\u00e2u h\u1ecfi n\u00e0y n\u1eb1m ngo\u00e0i ph\u1ea1m vi '
                'kho ki\u1ebfn th\u1ee9c n\u1ed9i b\u1ed9 hi\u1ec7n c\u00f3.", '
                '"sources": []}'
            )

    llm = FakeLLM()
    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), llm)

    events = [event async for event in pipeline.answer_stream("hello")]

    assert [event["event"] for event in events] == [
        "progress",
        "progress",
        "delta",
        "final",
    ]
    assert events[-1]["data"]["status"] == "conversational"
    assert "bad raw token" not in events[-1]["data"]["answer"]
    assert events[-1]["data"]["answer"] == LANGUAGE_FALLBACK_VI
    assert events[-1]["data"]["trace"]["branch"] == "conversation_stream"
    assert llm.stream_calls == 2
    assert llm.generate_calls == 0


@pytest.mark.asyncio
async def test_pipeline_streams_rag_as_validated_final_only(tmp_path: Path) -> None:
    class FakeRetriever:
        async def retrieve(self, query, filters=None):
            return RetrievalResult(
                chunks=[_chunk("Mo File Explorer.")],
                candidate_count=1,
                reranker_used=False,
            )

    class FakeLLM:
        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            return (
                '{"status": "answered", '
                '"answer": "Mo File Explorer. [SOURCE_1]", '
                '"sources": ["SOURCE_1"]}'
            )

    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, final_context_top_n=1),
        FakeRetriever(),
        FakeLLM(),
    )

    events = [event async for event in pipeline.answer_stream("cach mo NAS")]

    assert [event["event"] for event in events] == ["progress", "progress", "final"]
    assert events[-1]["data"]["status"] == "answered"
    assert events[-1]["data"]["answer"] == "Mo File Explorer. [SOURCE_1]"


@pytest.mark.asyncio
async def test_pipeline_stream_does_not_emit_retrieval_progress_for_out_of_scope(
    tmp_path: Path,
) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("out-of-scope stream should not retrieve")

    class FailLLM:
        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            raise AssertionError("out-of-scope stream should not call llm")

    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), FailLLM())

    events = [event async for event in pipeline.answer_stream("thoi tiet hom nay the nao")]

    assert [event["event"] for event in events] == ["progress", "final"]
    assert events[0]["data"]["stage"] == "routing"
    assert events[-1]["data"]["status"] == "out_of_scope"


@pytest.mark.asyncio
async def test_pipeline_bypasses_retrieval_for_out_of_scope_message(tmp_path: Path) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("retriever should not be called")

    class FailLLM:
        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            raise AssertionError("llm should not be called")

    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), FailLLM())

    result = await pipeline.answer("thoi tiet hom nay the nao")

    assert result["status"] == "out_of_scope"
    assert result["citations"] == []
    assert result["retrieval"] == {
        "candidate_count": 0,
        "context_count": 0,
        "reranker_used": False,
    }


@pytest.mark.asyncio
async def test_pipeline_retrieves_before_clarifying_vague_ambiguous_question(
    tmp_path: Path,
) -> None:
    class FakeRetriever:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def retrieve(self, query, filters=None):
            self.queries.append(query)
            return RetrievalResult(chunks=[], candidate_count=0, reranker_used=False)

    class FakeLLM:
        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            return (
                '{"intent": "clarify", "subtype": "none", '
                '"confidence": 0.78, "reason": "missing target system"}'
            )

    retriever = FakeRetriever()
    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), retriever, FakeLLM())

    result = await pipeline.answer("sao toi khong vao duoc")

    assert result["status"] == "clarify"
    assert retriever.queries == ["sao toi khong vao duoc"]
    assert result["retrieval"]["candidate_count"] == 0
    assert result["trace"]["intent"] == "ambiguous"
    assert result["trace"]["branch"] == "retrieval_first_clarify"
    assert result["trace"]["llm_router_used"] is False


@pytest.mark.asyncio
async def test_pipeline_uses_llm_history_for_follow_up_challenge(tmp_path: Path) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("retriever should not be called")

    class FakeLLM:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.calls.append((system_prompt, user_prompt))
            return (
                '{"status": "conversational", '
                '"answer": "Minh chi chac trong pham vi nguon da tra cuu.", '
                '"sources": []}'
            )

    llm = FakeLLM()
    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), llm)

    result = await pipeline.answer(
        "ban co chac kien thuc ban dang noi la dung",
        history=[
            {"role": "user", "content": "cach truy cap NAS"},
            {"role": "assistant", "content": "Mo File Explorer. [SOURCE_1]"},
        ],
    )

    assert result["status"] == "conversational"
    assert result["citations"] == []
    assert result["retrieval"]["candidate_count"] == 0
    assert "Mo File Explorer" in llm.calls[0][1]
    assert "ban co chac" in llm.calls[0][1]


@pytest.mark.asyncio
async def test_pipeline_uses_llm_history_for_source_challenge(tmp_path: Path) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("retriever should not be called for a source challenge")

    class FakeLLM:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.calls.append((system_prompt, user_prompt))
            return (
                '{"status": "conversational", '
                '"answer": "Ban noi dung, cau truoc chua co citation nen '
                'khong nen coi la ket luan tu tai lieu.", '
                '"sources": []}'
            )

    llm = FakeLLM()
    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), llm)

    result = await pipeline.answer(
        "sao ma ngan vay, nguon o dau hay ban tu suy",
        history=[
            {"role": "user", "content": "toi can biet ve van hoa cong ty"},
            {
                "role": "assistant",
                "content": "Van hoa cong ty de cao su ton trong va hop tac.",
            },
        ],
    )

    assert result["status"] == "conversational"
    assert result["citations"] == []
    assert result["retrieval"]["candidate_count"] == 0
    assert "Van hoa cong ty" in llm.calls[0][1]
    assert "nguon o dau" in llm.calls[0][1]


@pytest.mark.asyncio
async def test_pipeline_rewrites_knowledge_follow_up_before_retrieval(tmp_path: Path) -> None:
    class FakeRetriever:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def retrieve(self, query, filters=None):
            self.queries.append(query)
            return RetrievalResult(
                chunks=[_chunk("Thu Bay cong ty lam viec buoi sang.")],
                candidate_count=1,
                reranker_used=False,
            )

    class FakeLLM:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []
            self.outputs = [
                '{"query": "noi quy cong ty thoi gian lam viec thu Bay"}',
                (
                    '{"status": "answered", '
                    '"answer": "Thu Bay cong ty lam viec buoi sang. [SOURCE_1]", '
                    '"sources": ["SOURCE_1"]}'
                ),
            ]

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.calls.append((system_prompt, user_prompt))
            return self.outputs.pop(0)

    retriever = FakeRetriever()
    llm = FakeLLM()
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, final_context_top_n=1),
        retriever,
        llm,
    )

    result = await pipeline.answer(
        "the con thu 7 thi sao",
        history=[
            {"role": "user", "content": "noi quy cong ty ve thoi gian lam viec"},
            {"role": "assistant", "content": "Cong ty lam viec tu thu 2 den thu 6."},
        ],
    )

    assert result["status"] == "answered"
    assert retriever.queries == ["noi quy cong ty thoi gian lam viec thu Bay"]
    assert result["trace"]["rewrite_used"] is True
    assert "USER: noi quy cong ty ve thoi gian lam viec" in llm.calls[1][1]


@pytest.mark.asyncio
async def test_pipeline_routes_company_culture_to_retrieval(tmp_path: Path) -> None:
    class FakeRetriever:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def retrieve(self, query, filters=None):
            self.queries.append(query)
            return RetrievalResult(
                chunks=[_chunk("Van hoa cong ty khuyen khich su ton trong lan nhau.")],
                candidate_count=1,
                reranker_used=False,
            )

    class FakeLLM:
        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            return (
                '{"status": "answered", '
                '"answer": "Van hoa cong ty khuyen khich su ton trong lan nhau. [SOURCE_1]", '
                '"sources": ["SOURCE_1"]}'
            )

    retriever = FakeRetriever()
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, final_context_top_n=1),
        retriever,
        FakeLLM(),
    )

    result = await pipeline.answer("toi can biet ve van hoa cong ty")

    assert result["status"] == "answered"
    assert retriever.queries == ["toi can biet ve van hoa cong ty"]
    assert result["retrieval"]["candidate_count"] == 1
    assert result["retrieval"]["context_count"] == 1
    assert [citation["citation_id"] for citation in result["citations"]] == ["SOURCE_1"]


@pytest.mark.asyncio
async def test_pipeline_blocks_clear_out_of_scope_question_before_llm(tmp_path: Path) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("out-of-scope question must not run retrieval")

    class FailLLM:
        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            raise AssertionError("out-of-scope question must not call llm")

    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), FailLLM())

    result = await pipeline.answer(
        "k\u1ec3 t\u00ean c\u00e1c gi\u1ed1ng m\u00e8o \u1edf Vi\u1ec7t Nam"
    )

    assert result["status"] == "out_of_scope"
    assert result["citations"] == []


@pytest.mark.asyncio
async def test_pipeline_blocks_travel_planning_before_llm(tmp_path: Path) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("travel planning must not run retrieval")

    class FailLLM:
        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            raise AssertionError("travel planning must not call llm")

    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), FailLLM())

    result = await pipeline.answer(
        "t\u00f4i mu\u1ed1n \u0111i \u0111\u00e0 n\u1eb5ng 2 ng\u00e0y 1 \u0111\u00eam, "
        "b\u1ea1n h\u00e3y l\u00ean plan cho t\u00f4i"
    )

    assert result["status"] == "out_of_scope"
    assert result["citations"] == []
    assert "tra c\u1ee9u" in result["answer"]


@pytest.mark.asyncio
async def test_pipeline_blocks_personal_finance_and_self_harm_before_retrieval(
    tmp_path: Path,
) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("personal finance/self-harm question must not run retrieval")

    class FailLLM:
        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            raise AssertionError("personal finance/self-harm question must not call llm")

    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), FailLLM())

    result = await pipeline.answer("toi no 100tr va dang tim cach tra, hay toi nen tu tu")

    assert result["status"] == "out_of_scope"
    assert result["retrieval"]["candidate_count"] == 0
    assert result["retrieval"]["context_count"] == 0
    assert result["citations"] == []
    assert "tra c\u1ee9u" in result["answer"]


@pytest.mark.asyncio
async def test_pipeline_routes_bookmark_question_to_retrieval(tmp_path: Path) -> None:
    class FakeRetriever:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def retrieve(self, query, filters=None):
            self.queries.append(query)
            return RetrievalResult(
                chunks=[_chunk("Chrome c\u00f3 ph\u1ea7n bookmark trong t\u00e0i li\u1ec7u.")],
                candidate_count=1,
                reranker_used=False,
            )

    class FakeLLM:
        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            return (
                '{"status": "answered", '
                '"answer": "Chrome c\u00f3 ph\u1ea7n bookmark trong t\u00e0i li\u1ec7u. '
                '[SOURCE_1]", "sources": ["SOURCE_1"]}'
            )

    retriever = FakeRetriever()
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, final_context_top_n=1),
        retriever,
        FakeLLM(),
    )

    result = await pipeline.answer("Backup bookmark Chrome nh\u01b0 th\u1ebf n\u00e0o?")

    assert result["status"] == "answered"
    assert retriever.queries == ["Backup bookmark Chrome nh\u01b0 th\u1ebf n\u00e0o?"]


@pytest.mark.asyncio
async def test_pipeline_rewrites_mobile_follow_up_before_retrieval(tmp_path: Path) -> None:
    class FakeRetriever:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def retrieve(self, query, filters=None):
            self.queries.append(query)
            return RetrievalResult(
                chunks=[
                    _chunk(
                        "Tr\u00ean AppStore ho\u1eb7c CH Play, t\u00ecm \u1ee9ng "
                        "d\u1ee5ng WebAccess A v\u00e0 c\u00e0i \u0111\u1eb7t."
                    )
                ],
                candidate_count=1,
                reranker_used=False,
            )

    class FakeLLM:
        def __init__(self) -> None:
            self.outputs = [
                '{"query": "truy cap NAS bang app mobile mang ngoai"}',
                (
                    '{"status": "answered", "answer": "Tr\u00ean AppStore '
                    'ho\u1eb7c CH Play, t\u00ecm \u1ee9ng d\u1ee5ng WebAccess A '
                    'v\u00e0 c\u00e0i \u0111\u1eb7t. [SOURCE_1]", '
                    '"sources": ["SOURCE_1"]}'
                ),
            ]

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            return self.outputs.pop(0)

    retriever = FakeRetriever()
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, final_context_top_n=1),
        retriever,
        FakeLLM(),
    )

    result = await pipeline.answer(
        "d\u00f9ng app mobile \u0111i",
        history=[
            {"role": "user", "content": "h\u01b0\u1edbng d\u1eabn NAS"},
            {"role": "assistant", "content": "C\u00f3 hai c\u00e1ch truy c\u1eadp NAS."},
        ],
    )

    assert result["status"] == "answered"
    assert retriever.queries == ["truy cap NAS bang app mobile mang ngoai"]
    assert result["trace"]["rewrite_used"] is True


@pytest.mark.asyncio
async def test_pipeline_routes_continue_without_token_to_llm_history(tmp_path: Path) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("retriever should not be called for conversational follow-up")

    class FakeLLM:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.calls.append((system_prompt, user_prompt))
            return (
                '{"status": "conversational", '
                '"answer": "Neu ban muon xem tiep phan danh sach truoc do, '
                'minh can token tiep noi hop le.", '
                '"sources": []}'
            )

    llm = FakeLLM()
    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), llm)

    result = await pipeline.answer(
        "tiep di",
        history=[
            {"role": "user", "content": "noi quy cong ty gom nhung gi"},
            {
                "role": "assistant",
                "content": "Dieu 1. [SOURCE_1]\n\nBan co muon xem tiep khong?",
            },
        ],
    )

    assert result["status"] == "conversational"
    assert result["retrieval"]["candidate_count"] == 0
    assert llm.calls
    assert "noi quy cong ty gom nhung gi" in llm.calls[0][1]
    assert "tiep di" in llm.calls[0][1]
    assert "Tr" not in result["answer"]


@pytest.mark.asyncio
async def test_pipeline_returns_continuation_for_long_broad_section(tmp_path: Path) -> None:
    chunks = [
        _section_chunk("Dieu 1 noi dung ngan. " * 8, ["Phan I: Noi quy", "Dieu 1"], 1),
        _section_chunk("Dieu 2 noi dung ngan. " * 8, ["Phan I: Noi quy", "Dieu 2"], 2),
        _section_chunk("Dieu 3 noi dung ngan. " * 8, ["Phan I: Noi quy", "Dieu 3"], 3),
    ]

    class FakeRetriever:
        async def retrieve(self, query, filters=None):
            return RetrievalResult(chunks=[chunks[0]], candidate_count=1, reranker_used=False)

        async def all_chunks(self):
            return chunks

    class FakeLLM:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.calls.append(user_prompt)
            return (
                '{"status": "partial", '
                '"answer": "Dieu 1 noi dung ngan. [SOURCE_1]\\n\\nBan co muon xem tiep khong?", '
                '"sources": ["SOURCE_1"]}'
            )

    llm = FakeLLM()
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, broad_max_context_tokens=45),
        FakeRetriever(),
        llm,
    )

    result = await pipeline.answer("noi quy cong ty gom nhung gi")

    assert result["status"] == "partial"
    assert result["retrieval"]["context_count"] == 1
    assert result["continuation"] == {
        "has_more": True,
        "mode": "broad_section",
        "document_id": "doc-a",
        "section_root": "Phan I: Noi quy",
        "next_offset": 1,
        "source_question": "noi quy cong ty gom nhung gi",
        "token": result["continuation"]["token"],
    }
    assert "Dieu 1" in llm.calls[0]
    assert "Dieu 2" not in llm.calls[0]
    assert "Ban co muon xem tiep" in result["answer"]


@pytest.mark.asyncio
async def test_pipeline_uses_continuation_offset_for_next_broad_section_part(
    tmp_path: Path,
) -> None:
    chunks = [
        _section_chunk("Dieu 1 noi dung ngan. " * 8, ["Phan I: Noi quy", "Dieu 1"], 1),
        _section_chunk("Dieu 2 noi dung ngan. " * 8, ["Phan I: Noi quy", "Dieu 2"], 2),
    ]

    class FakeRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("anchor retrieval should not be called for continuation")

        async def all_chunks(self):
            return chunks

    class FakeLLM:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.calls.append(user_prompt)
            return (
                '{"status": "answered", '
                '"answer": "Dieu 2 noi dung ngan. [SOURCE_1]", '
                '"sources": ["SOURCE_1"]}'
            )

    llm = FakeLLM()
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, broad_max_context_tokens=200),
        FakeRetriever(),
        llm,
    )

    result = await pipeline.answer(
        "tiep",
        continuation={
            "mode": "broad_section",
            "document_id": "doc-a",
            "section_root": "Phan I: Noi quy",
            "next_offset": 1,
            "source_question": "noi quy cong ty gom nhung gi",
            "token": pipeline.sign_continuation(
                {
                    "mode": "broad_section",
                    "document_id": "doc-a",
                    "section_root": "Phan I: Noi quy",
                    "next_offset": 1,
                    "source_question": "noi quy cong ty gom nhung gi",
                },
            ),
        },
    )

    assert result["status"] == "answered"
    assert "Dieu 2" in llm.calls[0]
    assert "Dieu 1" not in llm.calls[0]
    assert "continuation" not in result


@pytest.mark.asyncio
async def test_pipeline_accepts_accented_continue_request(tmp_path: Path) -> None:
    chunks = [
        _section_chunk("Dieu 1 noi dung ngan. " * 8, ["Phan I: Noi quy", "Dieu 1"], 1),
        _section_chunk("Dieu 2 noi dung ngan. " * 8, ["Phan I: Noi quy", "Dieu 2"], 2),
    ]

    class FakeRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("anchor retrieval should not be called for continuation")

        async def all_chunks(self):
            return chunks

    class FakeLLM:
        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            return (
                '{"status": "answered", '
                '"answer": "Dieu 2 noi dung ngan. [SOURCE_1]", '
                '"sources": ["SOURCE_1"]}'
            )

    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FakeRetriever(), FakeLLM())
    continuation = {
        "mode": "broad_section",
        "document_id": "doc-a",
        "section_root": "Phan I: Noi quy",
        "next_offset": 1,
        "source_question": "noi quy cong ty gom nhung gi",
    }
    continuation["token"] = pipeline.sign_continuation(continuation)

    result = await pipeline.answer("xem tiếp", continuation=continuation)

    assert result["status"] == "answered"


@pytest.mark.asyncio
async def test_pipeline_rejects_tampered_continuation_token(tmp_path: Path) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("tampered continuation must not trigger retrieval")

        async def all_chunks(self):
            raise AssertionError("tampered continuation must not expand chunks")

    class FailLLM:
        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            raise AssertionError("tampered continuation must not call llm")

    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), FailLLM())

    result = await pipeline.answer(
        "tiep",
        continuation={
            "mode": "broad_section",
            "document_id": "doc-a",
            "section_root": "Phan I: Noi quy",
            "next_offset": 10,
            "source_question": "noi quy cong ty gom nhung gi",
            "token": "invalid-token",
        },
    )

    assert result["status"] == "insufficient_context"
    assert result["citations"] == []


@pytest.mark.asyncio
async def test_pipeline_applies_filters_during_broad_section_expansion(tmp_path: Path) -> None:
    chunks = [
        _section_chunk(
            "Dieu 1 HR. " * 4,
            ["Phan I: Noi quy", "Dieu 1"],
            1,
            domain="hr",
        ),
        _section_chunk(
            "Dieu 2 IT. " * 4,
            ["Phan I: Noi quy", "Dieu 2"],
            2,
            domain="it",
        ),
    ]

    class FakeRetriever:
        async def retrieve(self, query, filters=None):
            return RetrievalResult(chunks=[chunks[0]], candidate_count=1, reranker_used=False)

        async def all_chunks(self):
            return chunks

    class FakeLLM:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.calls.append(user_prompt)
            return (
                '{"status": "answered", "answer": "Dieu 1 HR. [SOURCE_1]", '
                '"sources": ["SOURCE_1"]}'
            )

    llm = FakeLLM()
    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FakeRetriever(), llm)

    result = await pipeline.answer(
        "noi quy cong ty gom nhung gi",
        filters=RetrievalFilters(domains=["hr"]),
    )

    assert result["status"] == "answered"
    assert "Dieu 1 HR" in llm.calls[0]
    assert "Dieu 2 IT" not in llm.calls[0]


@pytest.mark.asyncio
async def test_pipeline_broad_retry_preserves_broad_instructions(tmp_path: Path) -> None:
    chunks = [
        _section_chunk("Dieu 1 noi dung ngan. " * 8, ["Phan I: Noi quy", "Dieu 1"], 1),
        _section_chunk("Dieu 2 noi dung ngan. " * 8, ["Phan I: Noi quy", "Dieu 2"], 2),
    ]

    class FakeRetriever:
        async def retrieve(self, query, filters=None):
            return RetrievalResult(chunks=[chunks[0]], candidate_count=1, reranker_used=False)

        async def all_chunks(self):
            return chunks

    class FakeLLM:
        def __init__(self) -> None:
            self.outputs = [
                "not json",
                (
                    '{"status": "partial", '
                    '"answer": "Dieu 1 noi dung ngan. [SOURCE_1]\\n\\n'
                    'Ban co muon xem tiep khong?", '
                    '"sources": ["SOURCE_1"]}'
                ),
            ]
            self.calls: list[str] = []

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.calls.append(user_prompt)
            return self.outputs.pop(0)

    llm = FakeLLM()
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, broad_max_context_tokens=45),
        FakeRetriever(),
        llm,
    )

    result = await pipeline.answer("noi quy cong ty gom nhung gi")

    assert result["status"] == "partial"
    assert len(llm.calls) == 2
    assert "Day la cau hoi dang liet ke/tong hop nhieu muc." in llm.calls[1]
    assert "Ban co muon xem tiep khong" in llm.calls[1]


@pytest.mark.asyncio
async def test_pipeline_does_not_call_llm_when_continuation_offset_is_exhausted(
    tmp_path: Path,
) -> None:
    chunks = [_section_chunk("Dieu 1 noi dung ngan.", ["Phan I: Noi quy", "Dieu 1"], 1)]

    class FakeRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("anchor retrieval should not be called for continuation")

        async def all_chunks(self):
            return chunks

    class FailLLM:
        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            raise AssertionError("llm should not be called when no chunks remain")

    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FakeRetriever(), FailLLM())
    continuation = {
        "mode": "broad_section",
        "document_id": "doc-a",
        "section_root": "Phan I: Noi quy",
        "next_offset": 10,
        "source_question": "noi quy cong ty gom nhung gi",
    }
    continuation["token"] = pipeline.sign_continuation(continuation)

    result = await pipeline.answer("tiep", continuation=continuation)

    assert result["status"] == "conversational"
    assert result["citations"] == []
    assert "continuation" not in result


@pytest.mark.asyncio
async def test_pipeline_retries_invalid_json_once(tmp_path: Path) -> None:
    class FakeRetriever:
        async def retrieve(self, query, filters=None):
            return RetrievalResult(
                chunks=[_chunk("Mở File Explorer.")],
                candidate_count=1,
                reranker_used=False,
            )

    class FakeLLM:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.outputs = [
                (
                    '{"status": "answered", "answer": "Mở File Explorer. [SOURCE_1]", '
                    '"sources": ["SOURCE_2"]}'
                ),
                (
                    '{"status": "answered", "answer": "Mở File Explorer. [SOURCE_1]", '
                    '"sources": ["SOURCE_1"]}'
                ),
            ]

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.calls.append(user_prompt)
            return self.outputs.pop(0)

    llm = FakeLLM()
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, final_context_top_n=1),
        FakeRetriever(),
        llm,
    )

    result = await pipeline.answer("Cách mở NAS?")

    assert len(llm.calls) == 2
    assert "khong hop le" in llm.calls[1]
    assert result["status"] == "answered"
    assert result["answer"] == "Mở File Explorer. [SOURCE_1]"
    assert [citation["citation_id"] for citation in result["citations"]] == ["SOURCE_1"]


@pytest.mark.asyncio
async def test_pipeline_returns_safe_fallback_after_retry_failure(tmp_path: Path) -> None:
    class FakeRetriever:
        async def retrieve(self, query, filters=None):
            return RetrievalResult(
                chunks=[_chunk("Mở File Explorer.")],
                candidate_count=1,
                reranker_used=False,
            )

    class FakeLLM:
        def __init__(self) -> None:
            self.calls = 0

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.calls += 1
            return "not json"

    llm = FakeLLM()
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, final_context_top_n=1),
        FakeRetriever(),
        llm,
    )

    result = await pipeline.answer("Cách mở NAS?")

    assert llm.calls == 2
    assert result["status"] == "generation_failed"
    assert result["answer"] == GENERATION_FAILED_RESPONSE
    assert result["citations"] == []


@pytest.mark.asyncio
async def test_pipeline_does_not_retry_noncritical_day_claim(
    tmp_path: Path,
) -> None:
    source_text = (
        "Th\u1eddi gian l\u00e0m vi\u1ec7c t\u1eeb 8h00 s\u00e1ng "
        "\u0111\u1ebfn 17h30 chi\u1ec1u t\u1eeb th\u1ee9 2 \u0111\u1ebfn th\u1ee9 6. "
        "S\u00e1ng th\u1ee9 7 l\u00e0m vi\u1ec7c t\u1eeb 8:00 \u0111\u1ebfn 12:00."
    )

    class FakeRetriever:
        async def retrieve(self, query, filters=None):
            return RetrievalResult(
                chunks=[_chunk(source_text)],
                candidate_count=1,
                reranker_used=False,
            )

    class FakeLLM:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.outputs = [
                (
                    '{"status": "answered", "answer": "S\u00e1ng ch\u1ee7 nh\u1eadt '
                    'l\u00e0m vi\u1ec7c t\u1eeb 8:00 \u0111\u1ebfn 12:00. [SOURCE_1]", '
                    '"sources": ["SOURCE_1"]}'
                ),
                (
                    '{"status": "answered", "answer": "S\u00e1ng th\u1ee9 7 '
                    'l\u00e0m vi\u1ec7c t\u1eeb 8:00 \u0111\u1ebfn 12:00. [SOURCE_1]", '
                    '"sources": ["SOURCE_1"]}'
                ),
            ]

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.calls.append(user_prompt)
            return self.outputs.pop(0)

    llm = FakeLLM()
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, final_context_top_n=1),
        FakeRetriever(),
        llm,
    )

    result = await pipeline.answer("m\u1ea5y h l\u00e0m v\u00e0 m\u1ea5y h v\u1ec1")

    assert result["status"] == "answered"
    assert "ch\u1ee7 nh\u1eadt" in result["answer"].lower()
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_pipeline_rejects_literal_not_supported_by_its_citation(
    tmp_path: Path,
) -> None:
    class FakeRetriever:
        async def retrieve(self, query, filters=None):
            return RetrievalResult(
                chunks=[
                    _section_chunk(
                        "M\u1ee5c \u0111\u00edch c\u1ee7a N\u1ed9i quy l\u00e0 gi\u00fap "
                        "nh\u00e2n vi\u00ean t\u1eadp trung v\u00e0o c\u00f4ng vi\u1ec7c.",
                        ["N\u1ed9i quy", "M\u1ee5c \u0111\u00edch"],
                        0,
                    ),
                    _section_chunk(
                        "Th\u1eddi gian l\u00e0m vi\u1ec7c t\u1eeb 8h00 s\u00e1ng "
                        "\u0111\u1ebfn 17h30 chi\u1ec1u t\u1eeb th\u1ee9 2 "
                        "\u0111\u1ebfn th\u1ee9 6.",
                        ["N\u1ed9i quy", "Th\u1eddi gian l\u00e0m vi\u1ec7c"],
                        1,
                    ),
                ],
                candidate_count=2,
                reranker_used=False,
            )

    class FakeLLM:
        def __init__(self) -> None:
            self.calls = 0

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.calls += 1
            return (
                '{"status": "answered", "answer": "Th\u1eddi gian l\u00e0m '
                'vi\u1ec7c t\u1eeb 8:00 \u0111\u1ebfn 17:30. [SOURCE_1]", '
                '"sources": ["SOURCE_1"]}'
            )

    llm = FakeLLM()
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, final_context_top_n=2),
        FakeRetriever(),
        llm,
    )

    result = await pipeline.answer("th\u1eddi gian l\u00e0m vi\u1ec7c")

    assert result["status"] == "generation_failed"
    assert result["answer"] == GENERATION_FAILED_RESPONSE
    assert result["trace"]["literal_validation_error"] == (
        "unsupported_literal:time:08:00,time:17:30"
    )
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_pipeline_does_not_retry_for_removed_heuristic_fact_guard(
    tmp_path: Path,
) -> None:
    source_text = "S\u00e1ng th\u1ee9 7 l\u00e0m vi\u1ec7c t\u1eeb 8:00 \u0111\u1ebfn 12:00."

    class FakeRetriever:
        async def retrieve(self, query, filters=None):
            return RetrievalResult(
                chunks=[_chunk(source_text)],
                candidate_count=1,
                reranker_used=False,
            )

    class FakeLLM:
        def __init__(self) -> None:
            self.calls = 0

        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.calls += 1
            return (
                '{"status": "answered", "answer": "S\u00e1ng ch\u1ee7 nh\u1eadt '
                'l\u00e0m vi\u1ec7c t\u1eeb 8:00 \u0111\u1ebfn 12:00. [SOURCE_1]", '
                '"sources": ["SOURCE_1"]}'
            )

    llm = FakeLLM()
    pipeline = RAGPipeline(
        Settings(documents_dir=tmp_path, final_context_top_n=1),
        FakeRetriever(),
        llm,
    )

    result = await pipeline.answer("m\u1ea5y h l\u00e0m v\u00e0 m\u1ea5y h v\u1ec1")

    assert llm.calls == 1
    assert result["status"] == "answered"
    assert result["trace"]["literal_validation_error"] is None


@pytest.mark.asyncio
async def test_pipeline_asks_deeper_clarify_for_category_only_after_clarify(
    tmp_path: Path,
) -> None:
    class FailRetriever:
        async def retrieve(self, query, filters=None):
            raise AssertionError("category-only clarify reply must not run retrieval")

    class FailLLM:
        async def generate(self, system_prompt: str, user_prompt: str) -> str:
            raise AssertionError("category-only clarify reply must not call llm")

    pipeline = RAGPipeline(Settings(documents_dir=tmp_path), FailRetriever(), FailLLM())

    result = await pipeline.answer(
        "quy tr\u00ecnh n\u1ed9i b\u1ed9 nh\u00e9",
        history=[
            {"role": "user", "content": "t\u00f4i c\u00f3 v\u1ea5n \u0111\u1ec1"},
            {"role": "assistant", "content": CLARIFY_RESPONSE},
        ],
    )

    assert result["status"] == "clarify"
    assert result["retrieval"]["candidate_count"] == 0
    assert result["trace"]["branch"] == "clarify_deeper"


def _chunk(content: str) -> Chunk:
    return Chunk(
        chunk_id="chunk-a",
        parent_id=None,
        document_id="doc-a",
        document_name="Doc",
        document_version="v1",
        knowledge_type=KnowledgeType.TECHNICAL_GUIDE,
        domain="it",
        section="NAS",
        heading_path=["NAS"],
        chunk_index=0,
        content=content,
        source_path="doc.md",
        content_hash="hash-a",
        score=0.8,
    )


def _section_chunk(
    content: str,
    heading_path: list[str],
    chunk_index: int,
    document_id: str = "doc-a",
    domain: str = "hr",
) -> Chunk:
    return Chunk(
        chunk_id=f"{document_id}-{chunk_index}",
        parent_id=f"{document_id}-parent",
        document_id=document_id,
        document_name="Noi Quy",
        document_version="v1",
        knowledge_type=KnowledgeType.POLICY,
        domain=domain,
        section=" > ".join(heading_path),
        heading_path=heading_path,
        chunk_index=chunk_index,
        content=content,
        source_path="noi-quy.md",
        content_hash=f"hash-{document_id}-{chunk_index}",
        score=0.8,
    )
