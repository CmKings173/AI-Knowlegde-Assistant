from __future__ import annotations

import os
import time
from collections.abc import Generator

import requests
import streamlit as st

# Environment settings
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Page Configuration
st.set_page_config(
    page_title="Trợ lý Kiến thức Việt Thái Dương",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for rich aesthetics & modern chat interface (Bot on Left, User on Right)
CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        max-width: 1100px;
    }

    /* Brand Header */
    .brand-header {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 18px 24px;
        background: linear-gradient(
            135deg,
            rgba(37, 99, 235, 0.08) 0%,
            rgba(124, 58, 237, 0.08) 100%
        );
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 16px;
        margin-bottom: 24px;
        backdrop-filter: blur(10px);
    }

    .brand-icon {
        font-size: 36px;
        line-height: 1;
    }

    .brand-title {
        font-size: 1.5rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
        background: linear-gradient(135deg, #1e293b 0%, #2563eb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    @media (prefers-color-scheme: dark) {
        .brand-title {
            background: linear-gradient(135deg, #ffffff 0%, #60a5fa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
    }

    .brand-subtitle {
        font-size: 0.875rem;
        color: #64748b;
        margin: 2px 0 0 0;
    }

    /* Status Badges */
    .status-badge-online {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        background-color: rgba(34, 197, 94, 0.12);
        color: #16a34a;
        border: 1px solid rgba(34, 197, 94, 0.3);
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }

    .status-badge-offline {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        background-color: rgba(239, 68, 68, 0.12);
        color: #dc2626;
        border: 1px solid rgba(239, 68, 68, 0.3);
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }

    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
    }
    .dot-online { background-color: #22c55e; }
    .dot-offline { background-color: #ef4444; }

    /* Custom Chat Message Layout: USER ON RIGHT (Tôi), BOT ON LEFT (Bot) */
    
    /* Overall Chat Message Container */
    [data-testid="stChatMessage"] {
        padding: 8px 0 !important;
        background: transparent !important;
        border: none !important;
    }

    /* 1. USER MESSAGES (RIGHT ALIGNED - TÔI) */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]),
    [data-testid="stChatMessage"]:has([aria-label*="user" i]) {
        flex-direction: row-reverse !important;
        justify-content: flex-start !important;
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
    [data-testid="stChatMessageContent"],
    [data-testid="stChatMessage"]:has([aria-label*="user" i])
    [data-testid="stChatMessageContent"] {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        color: #ffffff !important;
        border-radius: 20px 20px 4px 20px !important;
        padding: 12px 18px !important;
        margin-left: 18% !important;
        margin-right: 8px !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.25) !important;
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
    [data-testid="stChatMessageContent"] p,
    [data-testid="stChatMessage"]:has([aria-label*="user" i])
    [data-testid="stChatMessageContent"] p {
        color: #ffffff !important;
        margin: 0 !important;
        text-align: left !important;
    }

    /* 2. ASSISTANT / BOT MESSAGES (LEFT ALIGNED - BOT) */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]),
    [data-testid="stChatMessage"]:has([aria-label*="assistant" i]) {
        flex-direction: row !important;
        justify-content: flex-start !important;
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"])
    [data-testid="stChatMessageContent"],
    [data-testid="stChatMessage"]:has([aria-label*="assistant" i])
    [data-testid="stChatMessageContent"] {
        background: #f1f5f9 !important;
        color: #0f172a !important;
        border-radius: 20px 20px 20px 4px !important;
        padding: 14px 20px !important;
        margin-right: 15% !important;
        margin-left: 8px !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04) !important;
    }

    @media (prefers-color-scheme: dark) {
        [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"])
        [data-testid="stChatMessageContent"],
        [data-testid="stChatMessage"]:has([aria-label*="assistant" i])
        [data-testid="stChatMessageContent"] {
            background: #1e293b !important;
            color: #f8fafc !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
        }
    }

    /* Metric Badges */
    .metric-tag {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 0.75rem;
        color: #64748b;
        background: rgba(148, 163, 184, 0.15);
        padding: 3px 10px;
        border-radius: 8px;
        margin-right: 6px;
        margin-top: 6px;
        font-weight: 500;
    }

    /* Streamlit Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.2);
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 10px 10px 0 0;
        font-weight: 600;
    }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def check_api_health() -> bool:
    """Check backend API health status."""
    try:
        res = requests.get(f"{API_BASE_URL}/health", timeout=3)
        return res.status_code == 200
    except Exception:
        return False


def stream_text(text: str, delay: float = 0.012) -> Generator[str, None, None]:
    """Stream response text word-by-word with typewriter animation."""
    words = text.split(" ")
    for i, word in enumerate(words):
        yield word + (" " if i < len(words) - 1 else "")
        time.sleep(delay)


# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

# Sidebar Setup
with st.sidebar:
    st.markdown("### 🏢 Việt Thái Dương")
    st.caption("Hệ thống Trợ lý RAG Kiến thức Nội bộ")

    # API Status Check
    is_online = check_api_health()
    if is_online:
        st.markdown(
            """
            <div class="status-badge-online">
                <span class="status-dot dot-online"></span> API Ready (Online)
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="status-badge-offline">
                <span class="status-dot dot-offline"></span> API Không phản hồi
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    # Document Filter for Chat
    st.markdown("#### 🎯 Giới hạn phạm vi tra cứu")
    chat_documents = []
    try:
        docs_res = requests.get(f"{API_BASE_URL}/api/v1/documents", timeout=10)
        if docs_res.status_code == 200:
            chat_documents = docs_res.json().get("documents", [])
    except Exception:
        pass

    doc_options = {
        (
            f"{doc.get('original_name', 'Doc')} "
            f"({doc.get('document_id', '')[:8]}...)"
        ): doc.get("document_id")
        for doc in chat_documents
    }

    selected_doc_labels = st.multiselect(
        "Chọn tài liệu cụ thể (mặc định: Tất cả)",
        options=list(doc_options.keys()),
        placeholder="Tìm kiếm tài liệu...",
    )

    st.divider()

    # Chat Actions
    if st.button("🗑️ Xóa cuộc trò chuyện", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_prompt = None
        st.rerun()

    st.markdown("---")
    st.caption("🔒 Dữ liệu bảo mật & tra cứu nội bộ Việt Thái Dương.")

# Header Render
st.markdown(
    """
    <div class="brand-header">
        <div class="brand-icon">🤖</div>
        <div>
            <h2 class="brand-title">Trợ lý Kiến thức Nội bộ</h2>
            <p class="brand-subtitle">
                Hỏi đáp quy định công ty, ổ NAS, Outlook và thủ tục nội bộ nhanh chóng
            </p>
        </div>
    </div>
""",
    unsafe_allow_html=True,
)

tab_chat, tab_documents = st.tabs(["💬 Trò chuyện & Tra cứu", "📁 Quản lý Tài liệu"])

with tab_chat:
    # Empty State: Suggested Quick Questions
    if not st.session_state.messages:
        st.markdown("#### 💡 Gợi ý câu hỏi phổ biến")
        col1, col2, col3 = st.columns(3)

        suggestions = [
            ("📅 Quy định nghỉ phép", "Quy định về nghỉ phép năm như thế nào?"),
            ("📂 Truy cập ổ NAS", "Cách đăng nhập và kết nối ổ đĩa NAS công ty?"),
            ("📧 Cấu hình Outlook", "Hướng dẫn cài đặt email Outlook trên máy tính mới?"),
        ]

        for col, (label, prompt_text) in zip([col1, col2, col3], suggestions, strict=False):
            with col:
                if st.button(label, help=prompt_text, key=label, use_container_width=True):
                    st.session_state.pending_prompt = prompt_text
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

    # Render History Messages (User on Right, Assistant on Left)
    for msg in st.session_state.messages:
        role = msg["role"]
        with st.chat_message(role):
            st.markdown(msg["content"])

            # Render RAG Timing / Metrics
            timing = msg.get("timing")
            retrieval_info = msg.get("retrieval")
            if timing or retrieval_info:
                total_time = timing.get("total", 0) if timing else 0
                cand_count = retrieval_info.get("candidate_count", 0) if retrieval_info else 0
                st.markdown(
                    f"""
                    <div style="margin-top: 4px; margin-bottom: 8px;">
                        <span class="metric-tag">⚡ Phản hồi: {total_time}ms</span>
                        <span class="metric-tag">📄 Chunks tra cứu: {cand_count}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Render Citations & Images
            citations = msg.get("citations", [])
            if citations:
                with st.expander(f"📚 Nguồn tham khảo ({len(citations)} tài liệu)", expanded=False):
                    for idx, cit in enumerate(citations, 1):
                        doc_name = cit.get("document_name", "Tài liệu")
                        section = cit.get("section", "Chung")
                        excerpt = cit.get("excerpt", "")
                        st.markdown(f"**[{idx}] {doc_name}** — *{section}*")
                        st.caption(f'"{excerpt}"')

                        for img in cit.get("images", []):
                            img_url = f"{API_BASE_URL}{img.get('url')}"
                            st.image(img_url, caption=img.get("file_name", "Hình ảnh"))
                        if idx < len(citations):
                            st.divider()

    # Chat Input Handling
    prompt = st.chat_input("Nhập câu hỏi về quy định, NAS, Outlook...")

    # Handle quick suggestion button click
    if st.session_state.pending_prompt:
        prompt = st.session_state.pending_prompt
        st.session_state.pending_prompt = None

    if prompt:
        # 1. User Message (Rendered on Right)
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Assistant Streaming Response (Rendered on Left)
        with st.chat_message("assistant"):
            payload = {"question": prompt}
            if selected_doc_labels:
                payload["filters"] = {
                    "document_ids": [
                        doc_options[label]
                        for label in selected_doc_labels
                        if label in doc_options
                    ],
                    "include_parent_chunks": False,
                }

            try:
                with st.spinner("🔍 Đang tìm kiếm và tổng hợp thông tin..."):
                    res = requests.post(
                        f"{API_BASE_URL}/api/v1/chat",
                        json=payload,
                        timeout=120,
                    )
                    res.raise_for_status()
                    data = res.json()

                answer = data.get("answer", "Tôi chưa tìm thấy thông tin phù hợp trong tài liệu.")
                citations = data.get("citations", [])
                timing = data.get("timing_ms", {})
                retrieval_info = data.get("retrieval", {})

                # Stream response dynamically with typewriter effect
                st.write_stream(stream_text(answer))

                # Render Metrics
                if timing or retrieval_info:
                    total_time = timing.get("total", 0)
                    cand_count = retrieval_info.get("candidate_count", 0)
                    st.markdown(
                        f"""
                        <div style="margin-top: 4px; margin-bottom: 8px;">
                            <span class="metric-tag">⚡ Phản hồi: {total_time}ms</span>
                            <span class="metric-tag">📄 Chunks tra cứu: {cand_count}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                # Render Citations
                if citations:
                    source_label = f"📚 Nguồn tham khảo ({len(citations)} tài liệu)"
                    with st.expander(source_label, expanded=True):
                        for idx, cit in enumerate(citations, 1):
                            doc_name = cit.get("document_name", "Tài liệu")
                            section = cit.get("section", "Chung")
                            excerpt = cit.get("excerpt", "")
                            st.markdown(f"**[{idx}] {doc_name}** — *{section}*")
                            st.caption(f'"{excerpt}"')

                            for img in cit.get("images", []):
                                img_url = f"{API_BASE_URL}{img.get('url')}"
                                st.image(img_url, caption=img.get("file_name", "Hình ảnh"))
                            if idx < len(citations):
                                st.divider()

                # Save assistant response to session state
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": answer,
                        "citations": citations,
                        "timing": timing,
                        "retrieval": retrieval_info,
                    }
                )

            except requests.RequestException as e:
                st.error("⚠️ Backend đang tạm thời không phản hồi hoặc xảy ra lỗi kết nối.")
                st.caption(f"Chi tiết: {e}")

with tab_documents:
    st.markdown("### 📁 Quản lý & Ingest Tài liệu")
    st.write("Tải lên tài liệu mới (.docx, .md, .txt) để nạp vào bộ nhớ RAG kiến thức nội bộ.")

    col_upload, col_list = st.columns([1, 2], gap="large")

    with col_upload:
        st.markdown("#### 📤 Upload Tài liệu")
        uploaded = st.file_uploader(
            "Chọn tệp tài liệu",
            type=["docx", "md", "txt"],
            help="Hỗ trợ các định dạng .docx, .md, .txt",
        )
        if uploaded:
            if st.button("🚀 Nạp vào hệ thống (Ingest)", use_container_width=True):
                with st.spinner("⏳ Đang xử lý và nạp tài liệu vào Qdrant..."):
                    try:
                        files = {"file": (uploaded.name, uploaded.getvalue())}
                        res = requests.post(
                            f"{API_BASE_URL}/api/v1/documents",
                            files=files,
                            timeout=300,
                        )
                        res.raise_for_status()
                        st.success(f"✅ Ingest thành công tệp **{uploaded.name}**!")
                        st.json(res.json())
                        st.rerun()
                    except requests.RequestException as err:
                        st.error(f"❌ Lỗi khi ingest tài liệu: {err}")

    with col_list:
        st.markdown("#### 📑 Danh sách Tài liệu đã Ingest")
        if st.button("🔄 Làm mới danh sách"):
            st.rerun()

        try:
            docs_res = requests.get(f"{API_BASE_URL}/api/v1/documents", timeout=30)
            docs_res.raise_for_status()
            docs = docs_res.json().get("documents", [])

            if docs:
                st.metric("Tổng số tài liệu đã nạp", len(docs))
                formatted_docs = []
                for d in docs:
                    formatted_docs.append(
                        {
                            "Tên tài liệu": d.get("original_name", "N/A"),
                            "ID": d.get("document_id", ""),
                            "Định dạng": str(d.get("format", "")).upper(),
                            "Số Chunks": d.get("chunk_count", "N/A"),
                        }
                    )
                st.dataframe(formatted_docs, use_container_width=True)
            else:
                st.info("ℹ️ Chưa có tài liệu nào được ingest trong hệ thống.")
        except requests.RequestException:
            st.warning("⚠️ Chưa kết nối được với API để lấy danh sách tài liệu.")
