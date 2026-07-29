from app.config import Settings
from app.domain.exceptions import LLMProviderError
from app.providers.llm.base import LLMProvider
from app.providers.llm.gemini_provider import GeminiProvider
from app.providers.llm.ollama_provider import OllamaProvider
from app.providers.llm.openai_provider import OpenAICompatibleProvider


class EchoLLMProvider(LLMProvider):
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        del system_prompt, user_prompt
        return "Tôi chỉ có thể trả lời khi provider LLM thật được cấu hình. [SOURCE_1]"


def create_llm_provider(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        return OllamaProvider(settings)
    if provider == "openai":
        return OpenAICompatibleProvider(settings)
    if provider == "gemini":
        return GeminiProvider(settings)
    if provider == "echo":
        return EchoLLMProvider()
    raise LLMProviderError(f"Unsupported LLM provider: {settings.llm_provider}")
