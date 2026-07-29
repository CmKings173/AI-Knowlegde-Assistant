from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from app.utils.text import normalize_for_intent


class Intent(StrEnum):
    CONVERSATIONAL = "conversational"
    CONVERSATIONAL_LLM = "conversational_llm"
    FOLLOW_UP = "follow_up"
    BROAD_SECTION_QUERY = "broad_section_query"
    KNOWLEDGE_QUERY = "knowledge_query"
    OUT_OF_SCOPE = "out_of_scope"
    CLARIFY = "clarify"
    AMBIGUOUS = "ambiguous"


class FollowUpSubtype(StrEnum):
    SOURCE_CHALLENGE = "source_challenge"
    CONTINUATION = "continuation"
    KNOWLEDGE_FOLLOW_UP = "knowledge_follow_up"
    CASUAL_FOLLOW_UP = "casual_follow_up"
    NONE = "none"


@dataclass(frozen=True)
class IntentDecision:
    intent: Intent
    confidence: float
    reason: str
    subtype: FollowUpSubtype = FollowUpSubtype.NONE
    llm_router_used: bool = False


class IntentRouter:
    def classify(self, question: str, has_history: bool = False) -> IntentDecision:
        normalized = normalize_for_intent(question)
        if not normalized:
            return IntentDecision(Intent.CONVERSATIONAL, 0.8, "empty_message")

        knowledge_score = _score_terms(normalized, KNOWLEDGE_TERMS)
        broad_score = _score_terms(normalized, BROAD_SECTION_TERMS)
        follow_up_score = _score_terms(normalized, FOLLOW_UP_TERMS)
        conversational_score = _score_terms(normalized, CONVERSATIONAL_TERMS)
        out_of_scope_score = _score_terms(normalized, OUT_OF_SCOPE_TERMS)

        if out_of_scope_score > 0 and knowledge_score == 0:
            return IntentDecision(
                Intent.OUT_OF_SCOPE,
                min(0.9, 0.65 + out_of_scope_score * 0.1),
                "out_of_scope_term",
            )

        if broad_score > 0 and knowledge_score > 0:
            return IntentDecision(
                Intent.BROAD_SECTION_QUERY,
                min(0.95, 0.7 + broad_score * 0.1),
                "broad_section_term",
            )

        if follow_up_score > 0 and has_history:
            subtype = _follow_up_subtype(normalized)
            return IntentDecision(
                Intent.FOLLOW_UP,
                min(0.95, 0.7 + follow_up_score * 0.1),
                "follow_up_term_with_history",
                subtype,
            )

        if knowledge_score > 0:
            return IntentDecision(
                Intent.KNOWLEDGE_QUERY,
                min(0.95, 0.65 + knowledge_score * 0.1),
                "knowledge_term",
            )

        if follow_up_score > 0:
            return IntentDecision(
                Intent.CONVERSATIONAL_LLM,
                min(0.85, 0.6 + follow_up_score * 0.1),
                "follow_up_term_without_history",
            )

        if has_history and _looks_contextual_follow_up(normalized):
            return IntentDecision(
                Intent.FOLLOW_UP,
                0.7,
                "contextual_follow_up_with_history",
                FollowUpSubtype.KNOWLEDGE_FOLLOW_UP,
            )

        if conversational_score > 0 and out_of_scope_score == 0:
            if has_history:
                return IntentDecision(
                    Intent.FOLLOW_UP,
                    min(0.85, 0.6 + conversational_score * 0.1),
                    "conversational_term_with_history",
                    FollowUpSubtype.CASUAL_FOLLOW_UP,
                )
            return IntentDecision(
                Intent.CONVERSATIONAL_LLM,
                min(0.85, 0.6 + conversational_score * 0.1),
                "conversational_term_needs_llm",
            )

        if out_of_scope_score > 0:
            return IntentDecision(
                Intent.OUT_OF_SCOPE,
                min(0.9, 0.65 + out_of_scope_score * 0.1),
                "out_of_scope_term",
            )

        if _looks_like_question(normalized):
            return IntentDecision(Intent.AMBIGUOUS, 0.5, "question_without_domain_term")

        if has_history:
            return IntentDecision(
                Intent.FOLLOW_UP,
                0.6,
                "short_message_with_history",
                FollowUpSubtype.CASUAL_FOLLOW_UP,
            )

        return IntentDecision(Intent.CONVERSATIONAL_LLM, 0.55, "short_non_question_message")


CONVERSATIONAL_TERMS = (
    "xin chao",
    "chao",
    "hello",
    "hi",
    "cam on",
    "thanks",
    "thank you",
    "ban la ai",
    "ban lam duoc gi",
    "tro ly",
    "help",
)

FOLLOW_UP_TERMS = (
    "co chac",
    "chac khong",
    "dung khong",
    "co dung",
    "sai khong",
    "tai sao ban",
    "ban vua",
    "ban dang noi",
    "kien thuc ban",
    "cau tra loi truoc",
    "nguon nao",
    "nguon o dau",
    "nguon dau",
    "lay nguon o dau",
    "lay o dau",
    "ban tu suy",
    "tu suy",
    "sao ma ngan",
    "sao ngan",
    "ngan vay",
    "trich dan",
    "citation",
    "source",
    "tiep",
    "xem tiep",
    "tiep di",
    "noi tiep",
    "tiep nhe",
    "xem tiep nhe",
    "noi tiep di",
    "y do",
    "cai do",
    "phan do",
    "noi vay",
    "app mobile",
    "mobile",
    "dien thoai",
    "ung dung",
    "mang ngoai",
    "chi tiet",
    "chi tiet hon",
    "huong dan chi tiet",
)

SOURCE_CHALLENGE_TERMS = (
    "co chac",
    "chac khong",
    "dung khong",
    "co dung",
    "sai khong",
    "nguon nao",
    "nguon o dau",
    "nguon dau",
    "lay nguon o dau",
    "lay o dau",
    "ban tu suy",
    "tu suy",
    "trich dan",
    "citation",
    "source",
)

CONTINUATION_TERMS = (
    "tiep",
    "xem tiep",
    "tiep di",
    "noi tiep",
    "tiep nhe",
    "xem tiep nhe",
    "noi tiep di",
    "continue",
    "next",
)

KNOWLEDGE_FOLLOW_UP_TERMS = (
    "the con",
    "vay con",
    "thi sao",
    "ro hon",
    "giai thich them",
    "chi tiet hon",
    "chi tiet",
    "huong dan chi tiet",
    "app mobile",
    "mobile",
    "dien thoai",
    "ung dung",
    "mang ngoai",
    "phan do",
    "muc do",
    "dieu do",
)

BROAD_SECTION_TERMS = (
    "liet ke",
    "toan bo",
    "day du",
    "tat ca",
    "gom nhung gi",
    "co nhung dieu nao",
    "cac dieu",
    "danh sach",
    "noi quy cong ty",
    "phan i",
)

KNOWLEDGE_TERMS = (
    "noi quy",
    "van hoa",
    "van hoa cong ty",
    "noi quy va van hoa",
    "quy dinh",
    "chinh sach",
    "quy trinh",
    "sop",
    "faq",
    "nas",
    "outlook",
    "email",
    "mail",
    "windows",
    "chrome",
    "bookmark",
    "bookmarks",
    "browser",
    "trinh duyet",
    "dau trang",
    "sao luu bookmark",
    "backup bookmark",
    "troubleshooting",
    "loi",
    "huong dan",
    "cach",
    "may h",
    "may gio",
    "gio lam",
    "gio lam viec",
    "thoi gian lam viec",
    "vao lam",
    "gio ve",
    "di ve",
    "lam viec",
    "may tinh",
    "o mang",
    "server",
    "vpn",
    "tai lieu",
)

OUT_OF_SCOPE_TERMS = (
    "thoi tiet",
    "bong da",
    "chung khoan",
    "nau an",
    "du lich",
    "di da nang",
    "da nang",
    "di choi",
    "ky nghi",
    "lich trinh",
    "len plan",
    "khach san",
    "tour",
    "ve may bay",
    "dich truyen",
    "viet code",
    "lap trinh",
    "marketing",
    "facebook",
    "tiktok",
    "crypto",
    "bitcoin",
    "meo",
    "giong meo",
    "con cho",
    "giong cho",
    "thu cung",
    "dong vat",
)


def _score_terms(text: str, terms: tuple[str, ...]) -> int:
    return sum(1 for term in terms if _contains_term(text, term))


def _contains_term(text: str, term: str) -> bool:
    pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
    return re.search(pattern, text) is not None


def _looks_like_question(text: str) -> bool:
    question_terms = (
        "ai",
        "gi",
        "nao",
        "sao",
        "tai sao",
        "bao nhieu",
        "may",
        "may gio",
        "may h",
        "khi nao",
        "o dau",
        "lam sao",
    )
    return text.endswith("?") or any(_contains_term(text, term) for term in question_terms)


def _looks_contextual_follow_up(text: str) -> bool:
    contextual_terms = (
        "the con",
        "vay con",
        "con",
        "buoc",
        "phan do",
        "cai do",
        "cai nay",
        "noi tren",
        "y tren",
        "tiep theo",
        "ro hon",
        "giai thich them",
        "chi tiet",
        "huong dan chi tiet",
        "app mobile",
        "mobile",
        "dien thoai",
        "ung dung",
        "mang ngoai",
    )
    return any(_contains_term(text, term) for term in contextual_terms)


def _follow_up_subtype(text: str) -> FollowUpSubtype:
    if _score_terms(text, SOURCE_CHALLENGE_TERMS) > 0:
        return FollowUpSubtype.SOURCE_CHALLENGE
    if text in CONTINUATION_TERMS:
        return FollowUpSubtype.CONTINUATION
    if _score_terms(text, KNOWLEDGE_FOLLOW_UP_TERMS) > 0 or _looks_contextual_follow_up(text):
        return FollowUpSubtype.KNOWLEDGE_FOLLOW_UP
    return FollowUpSubtype.CASUAL_FOLLOW_UP
