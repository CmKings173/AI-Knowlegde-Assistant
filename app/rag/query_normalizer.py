from app.config import Settings
from app.utils.text import normalize_query


class QueryNormalizer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def normalize(self, question: str) -> str:
        return normalize_query(question, self.settings.synonyms)

