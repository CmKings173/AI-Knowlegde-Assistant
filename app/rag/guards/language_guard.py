from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.rag.response_validator import CJK_PATTERN

_WORD_PATTERN = re.compile(r"[^\W\d_]+", flags=re.UNICODE)
_MIN_LANGUAGE_SAMPLE_LETTERS = 32
_VIETNAMESE_WORDS = {
    "bạn",
    "bằng",
    "cần",
    "chào",
    "chỉ",
    "chưa",
    "có",
    "công",
    "của",
    "đang",
    "để",
    "được",
    "giúp",
    "hãy",
    "hiện",
    "hỗ",
    "không",
    "khi",
    "là",
    "lại",
    "liệu",
    "lòng",
    "mình",
    "một",
    "mở",
    "này",
    "nếu",
    "nội",
    "phần",
    "quy",
    "rồi",
    "sẽ",
    "thể",
    "thông",
    "tài",
    "tôi",
    "trả",
    "trong",
    "trợ",
    "và",
    "về",
    "vui",
}


@dataclass(frozen=True)
class LanguageDecision:
    accepted: bool
    detected: str
    reason: str


class VietnameseLanguageGuard:
    def validate_prefix(self, text: str) -> LanguageDecision:
        return self._validate(text)

    def validate_window(self, text: str) -> LanguageDecision:
        return self._validate(text)

    def validate_complete(self, text: str) -> LanguageDecision:
        return self._validate(text)

    def _validate(self, text: str) -> LanguageDecision:
        value = text.strip()
        if not value:
            return LanguageDecision(False, "empty", "empty_output")

        has_cjk = bool(CJK_PATTERN.search(value))
        has_latin = any(_is_latin_letter(char) for char in value)
        if has_cjk:
            return LanguageDecision(
                False,
                "mixed_cjk" if has_latin else "cjk",
                "disallowed_cjk",
            )

        letters = [char for char in value if char.isalpha()]
        if len(letters) < _MIN_LANGUAGE_SAMPLE_LETTERS:
            return LanguageDecision(True, "short_or_technical", "sample_too_short")

        words = {word.casefold() for word in _WORD_PATTERN.findall(value)}
        vietnamese_word_count = len(words & _VIETNAMESE_WORDS)
        vietnamese_mark_count = sum(_has_vietnamese_mark(char) for char in letters)
        if vietnamese_word_count >= 1 and vietnamese_mark_count >= 2:
            return LanguageDecision(True, "vi", "vietnamese_signals")

        return LanguageDecision(
            False,
            "latin_non_vietnamese",
            "missing_vietnamese_signals",
        )


def _is_latin_letter(char: str) -> bool:
    return char.isalpha() and "LATIN" in unicodedata.name(char, "")


def _has_vietnamese_mark(char: str) -> bool:
    if char.casefold() == "đ":
        return True
    decomposed = unicodedata.normalize("NFD", char)
    return any(unicodedata.category(item) == "Mn" for item in decomposed[1:])
