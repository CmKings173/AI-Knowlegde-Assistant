from __future__ import annotations

import contextlib
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.providers.llm.base import LLMProvider
from app.rag.guards.language_guard import VietnameseLanguageGuard

LANGUAGE_FALLBACK_VI = (
    "Mình chưa thể tạo câu trả lời tiếng Việt ổn định lúc này. "
    "Bạn vui lòng thử lại."
)
STREAM_INTERRUPTED_VI = (
    " Mình đã dừng phần trả lời còn lại vì ngôn ngữ tạo ra không hợp lệ."
)


@dataclass(frozen=True)
class ConversationDelta:
    text: str


@dataclass(frozen=True)
class ConversationComplete:
    answer: str
    retry_used: bool
    fallback_used: bool
    interrupted: bool
    language_decision: str
    llm_ms: int
    error: str | None = None


@dataclass(frozen=True)
class _AttemptComplete:
    answer: str
    accepted: bool
    interrupted: bool
    language_decision: str
    error: str | None = None


class ConversationStreamExecutor:
    def __init__(
        self,
        llm_provider: LLMProvider,
        language_guard: VietnameseLanguageGuard,
        *,
        prefix_chars: int = 30,
        rolling_window_chars: int = 160,
    ) -> None:
        if prefix_chars < 1:
            raise ValueError("prefix_chars must be positive")
        if rolling_window_chars < prefix_chars:
            raise ValueError("rolling_window_chars must cover the prefix")
        self.llm_provider = llm_provider
        self.language_guard = language_guard
        self.prefix_chars = prefix_chars
        self.rolling_window_chars = rolling_window_chars

    async def stream(
        self,
        system_prompt: str,
        user_prompt: str,
        retry_user_prompt: str,
    ) -> AsyncIterator[ConversationDelta | ConversationComplete]:
        started = time.perf_counter()
        retry_used = False
        prompts = (user_prompt, retry_user_prompt)

        for attempt_index, prompt in enumerate(prompts):
            terminal: _AttemptComplete | None = None
            attempt_stream = self._stream_attempt(system_prompt, prompt)
            try:
                async for item in attempt_stream:
                    if isinstance(item, ConversationDelta):
                        yield item
                    else:
                        terminal = item
            finally:
                await attempt_stream.aclose()

            if terminal is None:
                terminal = _AttemptComplete(
                    answer="",
                    accepted=False,
                    interrupted=False,
                    language_decision="missing_terminal_state",
                    error="executor_error",
                )

            if terminal.accepted:
                yield ConversationComplete(
                    answer=terminal.answer,
                    retry_used=retry_used,
                    fallback_used=False,
                    interrupted=terminal.interrupted,
                    language_decision=terminal.language_decision,
                    llm_ms=_elapsed_ms(started),
                    error=terminal.error,
                )
                return

            if terminal.error == "provider_error":
                yield ConversationDelta(LANGUAGE_FALLBACK_VI)
                yield ConversationComplete(
                    answer=LANGUAGE_FALLBACK_VI,
                    retry_used=retry_used,
                    fallback_used=True,
                    interrupted=False,
                    language_decision=terminal.language_decision,
                    llm_ms=_elapsed_ms(started),
                    error=terminal.error,
                )
                return

            if attempt_index == 0:
                retry_used = True
                continue

            yield ConversationDelta(LANGUAGE_FALLBACK_VI)
            yield ConversationComplete(
                answer=LANGUAGE_FALLBACK_VI,
                retry_used=True,
                fallback_used=True,
                interrupted=False,
                language_decision=terminal.language_decision,
                llm_ms=_elapsed_ms(started),
            )
            return

    async def _stream_attempt(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> AsyncIterator[ConversationDelta | _AttemptComplete]:
        source = self.llm_provider.stream_generate(system_prompt, user_prompt)
        prefix = ""
        rolling_window = ""
        emitted: list[str] = []
        prefix_accepted = False

        try:
            async for fragment in source:
                if not fragment:
                    continue
                if not prefix_accepted:
                    prefix += fragment
                    if len(prefix) < self.prefix_chars:
                        continue
                    decision = self.language_guard.validate_prefix(prefix)
                    if not decision.accepted:
                        yield _AttemptComplete(
                            answer="",
                            accepted=False,
                            interrupted=False,
                            language_decision=decision.reason,
                        )
                        return
                    prefix_accepted = True
                    rolling_window = prefix[-self.rolling_window_chars :]
                    emitted.append(prefix)
                    yield ConversationDelta(prefix)
                    continue

                candidate_window = (
                    rolling_window + fragment
                )[-self.rolling_window_chars :]
                decision = self.language_guard.validate_window(candidate_window)
                if not decision.accepted:
                    emitted.append(STREAM_INTERRUPTED_VI)
                    yield ConversationDelta(STREAM_INTERRUPTED_VI)
                    yield _AttemptComplete(
                        answer="".join(emitted),
                        accepted=True,
                        interrupted=True,
                        language_decision=decision.reason,
                    )
                    return
                rolling_window = candidate_window
                emitted.append(fragment)
                yield ConversationDelta(fragment)

            if not prefix_accepted:
                decision = self.language_guard.validate_complete(prefix)
                if not decision.accepted:
                    yield _AttemptComplete(
                        answer="",
                        accepted=False,
                        interrupted=False,
                        language_decision=decision.reason,
                    )
                    return
                emitted.append(prefix)
                yield ConversationDelta(prefix)

            answer = "".join(emitted)
            decision = self.language_guard.validate_complete(answer)
            if not decision.accepted and emitted:
                emitted.append(STREAM_INTERRUPTED_VI)
                yield ConversationDelta(STREAM_INTERRUPTED_VI)
                yield _AttemptComplete(
                    answer="".join(emitted),
                    accepted=True,
                    interrupted=True,
                    language_decision=decision.reason,
                )
                return
            yield _AttemptComplete(
                answer=answer,
                accepted=decision.accepted,
                interrupted=False,
                language_decision=decision.reason,
            )
        except Exception:  # noqa: BLE001 - provider boundary returns safe fallback
            if emitted:
                emitted.append(STREAM_INTERRUPTED_VI)
                yield ConversationDelta(STREAM_INTERRUPTED_VI)
                yield _AttemptComplete(
                    answer="".join(emitted),
                    accepted=True,
                    interrupted=True,
                    language_decision="provider_error_after_delta",
                    error="provider_error",
                )
            else:
                yield _AttemptComplete(
                    answer="",
                    accepted=False,
                    interrupted=False,
                    language_decision="provider_error_before_delta",
                    error="provider_error",
                )
        finally:
            close = getattr(source, "aclose", None)
            if callable(close):
                with contextlib.suppress(Exception):
                    await close()


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
