from __future__ import annotations

import re
import unicodedata


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_query(query: str, synonyms: dict[str, str] | None = None) -> str:
    normalized = normalize_text(query)
    if not synonyms:
        return normalized
    result = normalized
    for source, target in synonyms.items():
        result = re.sub(rf"\b{re.escape(source)}\b", target, result, flags=re.IGNORECASE)
    return result


def estimate_tokens(text: str) -> int:
    return max(1, len(re.findall(r"\S+", text)))


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[\w./:\\+-]+", text, flags=re.UNICODE)]


def excerpt(text: str, limit: int = 280) -> str:
    clean = normalize_text(text)
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"

