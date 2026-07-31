from __future__ import annotations

import pytest

from app.rag.guards.language_guard import VietnameseLanguageGuard


@pytest.fixture
def guard() -> VietnameseLanguageGuard:
    return VietnameseLanguageGuard()


@pytest.mark.parametrize(
    "text",
    [
        "Mình có thể hỗ trợ bạn tra cứu tài liệu nội bộ.",
        "Nếu Outlook không gửi được email, bạn hãy kiểm tra kết nối mạng.",
        "NAS lỗi rồi",
        "OK",
        "Mở http://10.10.12.158:8501 rồi đăng nhập bằng email it@example.com.",
        "Chạy `uv run python main.py` để khởi động API trên port 8000.",
    ],
)
def test_guard_accepts_vietnamese_and_safe_technical_text(
    guard: VietnameseLanguageGuard,
    text: str,
) -> None:
    decision = guard.validate_complete(text)

    assert decision.accepted
    assert decision.detected in {"vi", "short_or_technical"}


@pytest.mark.parametrize(
    ("text", "detected"),
    [
        ("Rất tiếc, 请告诉我 vấn đề bạn đang gặp.", "mixed_cjk"),
        ("请告诉我您遇到的问题，我会尽力帮助。", "cjk"),
        (
            "This response is written entirely in English and does not answer "
            "the user in the required Vietnamese language.",
            "latin_non_vietnamese",
        ),
        ("bad raw token", "latin_non_vietnamese"),
    ],
)
def test_guard_rejects_cjk_mixed_and_long_english(
    guard: VietnameseLanguageGuard,
    text: str,
    detected: str,
) -> None:
    decision = guard.validate_complete(text)

    assert not decision.accepted
    assert decision.detected == detected
    assert decision.reason


def test_prefix_and_window_use_the_same_fail_closed_policy(
    guard: VietnameseLanguageGuard,
) -> None:
    valid_prefix = guard.validate_prefix("Mình sẽ giải thích lại rõ hơn.")
    invalid_window = guard.validate_window(
        "Mình sẽ giải thích lại rõ hơn. 这是错误的语言。"
    )

    assert valid_prefix.accepted
    assert not invalid_window.accepted
    assert invalid_window.detected == "mixed_cjk"


def test_guard_rejects_empty_complete_output(guard: VietnameseLanguageGuard) -> None:
    decision = guard.validate_complete("   ")

    assert not decision.accepted
    assert decision.detected == "empty"
