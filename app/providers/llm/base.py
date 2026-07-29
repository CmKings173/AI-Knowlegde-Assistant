from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

    async def stream_generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> AsyncIterator[str]:
        yield await self.generate(system_prompt, user_prompt)
