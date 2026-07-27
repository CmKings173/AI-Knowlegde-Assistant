class ApplicationError(Exception):
    code = "APPLICATION_ERROR"
    user_message = "Hệ thống đang tạm thời không khả dụng."


class ConfigurationError(ApplicationError):
    code = "CONFIGURATION_ERROR"
    user_message = "Cấu hình hệ thống chưa hợp lệ."


class DocumentParseError(ApplicationError):
    code = "DOCUMENT_PARSE_ERROR"
    user_message = "Không thể đọc tài liệu đã tải lên."


class EmbeddingError(ApplicationError):
    code = "EMBEDDING_ERROR"
    user_message = "Dịch vụ embedding đang tạm thời không khả dụng."


class VectorStoreError(ApplicationError):
    code = "VECTOR_STORE_ERROR"
    user_message = "Kho tri thức đang tạm thời không khả dụng."


class RetrievalError(ApplicationError):
    code = "RETRIEVAL_ERROR"
    user_message = "Không thể tìm kiếm tài liệu liên quan."


class RerankerError(ApplicationError):
    code = "RERANKER_ERROR"
    user_message = "Không thể sắp xếp lại kết quả tìm kiếm."


class LLMProviderError(ApplicationError):
    code = "LLM_PROVIDER_UNAVAILABLE"
    user_message = "Hệ thống trả lời đang tạm thời không khả dụng."

