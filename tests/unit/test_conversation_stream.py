from __future__ import annotations

import asyncio

import pytest

from app.rag.execution.conversation_stream import (
    LANGUAGE_FALLBACK_VI,
    STREAM_INTERRUPTED_VI,
    ConversationComplete,
    ConversationDelta,
    ConversationStreamExecutor,
)
from app.rag.guards.language_guard import LanguageDecision, VietnameseLanguageGuard


class FragmentLLM:
    def __init__(self, responses: list[list[str] | Exception]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []
        self.closed = 0

    async def stream_generate(self, system_prompt: str, user_prompt: str):
        self.calls.append((system_prompt, user_prompt))
        response = self.responses[len(self.calls) - 1]
        try:
            if isinstance(response, Exception):
                raise response
            for fragment in response:
                await asyncio.sleep(0)
                yield fragment
        finally:
            self.closed += 1


def _executor(llm: FragmentLLM) -> ConversationStreamExecutor:
    return ConversationStreamExecutor(
        llm,
        VietnameseLanguageGuard(),
        prefix_chars=30,
    )


class CompleteRejectingGuard(VietnameseLanguageGuard):
    def validate_complete(self, text: str) -> LanguageDecision:
        del text
        return LanguageDecision(False, "latin_non_vietnamese", "final_rejected")


@pytest.mark.asyncio
async def test_stream_buffers_prefix_then_emits_progressive_deltas() -> None:
    llm = FragmentLLM(
        [
            [
                "Mình sẽ giải thích ",
                "lại rõ hơn cho bạn.",
                " Nội dung tiếp theo.",
            ]
        ]
    )

    items = [
        item
        async for item in _executor(llm).stream(
            "system",
            "question",
            "clean retry",
        )
    ]

    deltas = [item.text for item in items if isinstance(item, ConversationDelta)]
    complete = next(item for item in items if isinstance(item, ConversationComplete))
    assert deltas == [
        "Mình sẽ giải thích lại rõ hơn cho bạn.",
        " Nội dung tiếp theo.",
    ]
    assert complete.answer == "".join(deltas)
    assert not complete.retry_used
    assert not complete.fallback_used


@pytest.mark.asyncio
async def test_invalid_prefix_retries_once_without_copying_raw_output() -> None:
    invalid = "请告诉我您遇到的问题，我会尽力帮助。"
    llm = FragmentLLM(
        [
            [invalid],
            ["Mình sẽ trả lời lại hoàn toàn bằng tiếng Việt."],
        ]
    )

    items = [
        item
        async for item in _executor(llm).stream(
            "system",
            "original user prompt",
            "retry from a clean prompt",
        )
    ]

    deltas = [item.text for item in items if isinstance(item, ConversationDelta)]
    complete = next(item for item in items if isinstance(item, ConversationComplete))
    assert len(llm.calls) == 2
    assert llm.calls[1][1] == "retry from a clean prompt"
    assert invalid not in llm.calls[1][1]
    assert invalid not in "".join(deltas)
    assert complete.retry_used
    assert not complete.fallback_used
    assert complete.answer == "".join(deltas)


@pytest.mark.asyncio
async def test_second_invalid_prefix_returns_fixed_vietnamese_fallback() -> None:
    llm = FragmentLLM(
        [
            ["这是第一次错误。"],
            ["这是第二次错误。"],
        ]
    )

    items = [
        item
        async for item in _executor(llm).stream(
            "system",
            "question",
            "retry",
        )
    ]

    deltas = [item.text for item in items if isinstance(item, ConversationDelta)]
    complete = next(item for item in items if isinstance(item, ConversationComplete))
    assert deltas == [LANGUAGE_FALLBACK_VI]
    assert complete.answer == LANGUAGE_FALLBACK_VI
    assert complete.retry_used
    assert complete.fallback_used


@pytest.mark.asyncio
async def test_invalid_midstream_fragment_is_not_emitted() -> None:
    llm = FragmentLLM(
        [
            [
                "Mình sẽ giải thích rõ cho bạn về nội dung này.",
                " 这是错误的语言。",
                "Phần này không được chạy.",
            ]
        ]
    )

    items = [
        item
        async for item in _executor(llm).stream(
            "system",
            "question",
            "retry",
        )
    ]

    deltas = [item.text for item in items if isinstance(item, ConversationDelta)]
    complete = next(item for item in items if isinstance(item, ConversationComplete))
    assert deltas == [
        "Mình sẽ giải thích rõ cho bạn về nội dung này.",
        STREAM_INTERRUPTED_VI,
    ]
    assert "这是" not in complete.answer
    assert "không được chạy" not in complete.answer
    assert complete.interrupted
    assert complete.answer == "".join(deltas)


@pytest.mark.asyncio
async def test_provider_error_before_first_delta_returns_fallback() -> None:
    llm = FragmentLLM([RuntimeError("provider unavailable")])

    items = [
        item
        async for item in _executor(llm).stream(
            "system",
            "question",
            "retry",
        )
    ]

    deltas = [item.text for item in items if isinstance(item, ConversationDelta)]
    complete = next(item for item in items if isinstance(item, ConversationComplete))
    assert deltas == [LANGUAGE_FALLBACK_VI]
    assert complete.fallback_used
    assert complete.error == "provider_error"


@pytest.mark.asyncio
async def test_final_rejection_after_delta_interrupts_without_retrying() -> None:
    llm = FragmentLLM(
        [["Mình sẽ giải thích rõ cho bạn về nội dung này.", " Phần tiếp theo."]]
    )
    executor = ConversationStreamExecutor(
        llm,
        CompleteRejectingGuard(),
        prefix_chars=30,
    )

    items = [
        item
        async for item in executor.stream(
            "system",
            "question",
            "retry",
        )
    ]

    deltas = [item.text for item in items if isinstance(item, ConversationDelta)]
    complete = next(item for item in items if isinstance(item, ConversationComplete))
    assert len(llm.calls) == 1
    assert deltas[-1] == STREAM_INTERRUPTED_VI
    assert complete.interrupted
    assert complete.answer == "".join(deltas)


@pytest.mark.asyncio
async def test_closing_executor_stream_closes_provider_generator() -> None:
    llm = FragmentLLM(
        [["Mình sẽ giải thích rõ cho bạn về nội dung này.", " Phần tiếp theo."]]
    )
    stream = _executor(llm).stream("system", "question", "retry")

    first = await anext(stream)
    await stream.aclose()

    assert isinstance(first, ConversationDelta)
    assert llm.closed == 1
