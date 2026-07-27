from __future__ import annotations

import re

from app.domain.enums import KnowledgeType


def classify_knowledge_type(text: str, heading_path: list[str] | None = None) -> KnowledgeType:
    haystack = " ".join([*(heading_path or []), text]).lower()
    if re.search(r"\b(faq|câu hỏi thường gặp|hỏi đáp)\b", haystack):
        return KnowledgeType.FAQ
    if re.search(r"(lỗi|khắc phục|không truy cập|can't access|troubleshoot)", haystack):
        return KnowledgeType.TROUBLESHOOTING
    if re.search(r"(bước\s*\d+|nhấn|chọn|click|mở\s+|vào menu)", haystack):
        return KnowledgeType.TUTORIAL
    if re.search(r"(smtp|pop3|imap|port|ip|nas|outlook|windows|smb|cifs)", haystack):
        return KnowledgeType.TECHNICAL_GUIDE
    if re.search(r"(checklist|danh sách|cần thực hiện|đảm bảo)", haystack):
        return KnowledgeType.CHECKLIST
    if re.search(r"(văn hóa|giá trị|chính trực|học hỏi)", haystack):
        return KnowledgeType.CULTURE
    if re.search(r"(điều\s+\d+|không được|phải|quy định|xử phạt|bảo mật)", haystack):
        return KnowledgeType.POLICY
    if re.search(r"(quy trình|sop|hướng dẫn)", haystack):
        return KnowledgeType.SOP
    return KnowledgeType.BEST_PRACTICE


def infer_domain(text: str, heading_path: list[str] | None = None) -> str:
    haystack = " ".join([*(heading_path or []), text]).lower()
    checks = [
        ("NAS", ["nas", "\\\\", "smb", "cifs"]),
        ("OUTLOOK", ["outlook", "smtp", "pop3", "imap", "email", "mail"]),
        ("WINDOWS", ["windows", "sleep", "shutdown", "hibernate", "gập máy"]),
        ("BROWSER", ["chrome", "bookmark"]),
        ("HR_POLICY", ["điều", "nội quy", "nghỉ", "làm việc", "hối lộ"]),
        ("CULTURE", ["văn hóa", "giá trị", "chính trực"]),
    ]
    for domain, keywords in checks:
        if any(keyword in haystack for keyword in keywords):
            return domain
    return "GENERAL"

