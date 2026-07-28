from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    data_dir: Path = Path("data")
    upload_dir: Path = Path("data/uploads")
    documents_dir: Path = Path("data/documents")
    processed_dir: Path = Path("data/processed")
    max_upload_mb: int = 50
    max_question_chars: int = 2000

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "company_knowledge"

    embedding_provider: str = "openai"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_embedding_model: str = "text-embedding-3-small"
    gemini_api_key: str = ""
    gemini_embedding_model: str = "text-embedding-004"
    embedding_batch_size: int = 16

    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b-instruct"
    llm_timeout_seconds: int = 240
    openai_model: str = ""
    gemini_model: str = "gemini-1.5-flash"

    reranker_enabled: bool = False
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    dense_top_k: int = 15
    lexical_top_k: int = 15
    fusion_top_k: int = 20
    rerank_top_k: int = 20
    final_context_top_n: int = 4
    min_retrieval_score: float = 0.01
    max_context_tokens: int = 3000

    chunk_target_tokens: int = 350
    chunk_max_tokens: int = 550
    chunk_overlap_tokens: int = 40
    parent_max_tokens: int = 1200

    debug_endpoints_enabled: bool = True

    synonyms: dict[str, str] = Field(
        default_factory=lambda: {
            "mail": "email",
            "outlook": "microsoft outlook",
            "ổ mạng": "NAS",
            "mạng nội bộ": "LAN",
            "gập máy": "đóng nắp laptop",
        }
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
