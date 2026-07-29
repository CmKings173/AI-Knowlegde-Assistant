from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_frontend_copy_decodes_unicode_escape_at_runtime() -> None:
    app_source = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    runtime_source = (ROOT / "frontend" / "src" / "chat-runtime.tsx").read_text(
        encoding="utf-8"
    )

    assert ">\\u" not in app_source
    assert 'placeholder="Nh\\u' not in app_source
    assert 'placeholder={"Nh\\u1eadp c\\u00e2u h\\u1ecfi' in app_source
    assert '{"Tr\\u1ee3 l\\u00fd Ki\\u1ebfn th\\u1ee9c N\\u1ed9i b\\u1ed9"}' in app_source
    assert "`Ngu\\u1ed3n tham kh\\u1ea3o" in app_source
    assert "\\u0110ang ph\\u00e2n lo\\u1ea1i c\\u00e2u h\\u1ecfi" in runtime_source


def test_frontend_copy_has_no_known_mojibake_tokens() -> None:
    checked_source = "\n".join(
        [
            (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8"),
            (ROOT / "frontend" / "src" / "chat-runtime.tsx").read_text(
                encoding="utf-8"
            ),
        ]
    )
    forbidden_tokens = [
        "Kh\u201c",
        "T\u201c",
        "Ch\u2026",
        "t\u2026i",
        "h\u008d",
        "Dang ph",
    ]

    for token in forbidden_tokens:
        assert token not in checked_source


def test_frontend_uses_custom_three_dot_typing_indicator() -> None:
    app_source = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    css_source = (ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")

    assert "function TypingIndicator()" in app_source
    assert app_source.count("<span />") >= 3
    assert ".typing-indicator span:nth-child(3)" in css_source
    assert "@keyframes typing-pulse" in css_source


def test_frontend_formats_source_markers_and_labels_from_citation_ids() -> None:
    app_source = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    runtime_source = (ROOT / "frontend" / "src" / "chat-runtime.tsx").read_text(
        encoding="utf-8"
    )

    assert "sourceDisplayLabel(citation, index)" in app_source
    assert "citation.citation_id.match" in app_source
    assert "formatCitationMarkers" in runtime_source
    assert "splitSourceMarkerList" in runtime_source
    assert "[SOURCE_1, SOURCE_3]" not in runtime_source
