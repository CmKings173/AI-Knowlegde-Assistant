from __future__ import annotations

import os

import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


st.set_page_config(page_title="Trợ lý kiến thức nội bộ Việt Thái Dương", page_icon="VTD")
st.title("Trợ lý kiến thức nội bộ Việt Thái Dương")

if "messages" not in st.session_state:
    st.session_state.messages = []

tab_chat, tab_documents = st.tabs(["Chat", "Tài liệu"])

with tab_chat:
    if st.button("Xóa cuộc trò chuyện"):
        st.session_state.messages = []
        st.rerun()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            for citation in message.get("citations", []):
                with st.expander(f"{citation['document_name']} — {citation['section']}"):
                    st.write(citation["excerpt"])
                    for image in citation.get("images", []):
                        st.image(f"{API_BASE_URL}{image['url']}", caption=image.get("file_name"))

    question = st.chat_input("Nhập câu hỏi về nội quy, NAS, Outlook...")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            try:
                response = requests.post(
                    f"{API_BASE_URL}/api/v1/chat",
                    json={"question": question},
                    timeout=120,
                )
                response.raise_for_status()
                data = response.json()
                st.markdown(data["answer"])
                for citation in data.get("citations", []):
                    with st.expander(f"{citation['document_name']} — {citation['section']}"):
                        st.write(citation["excerpt"])
                        for image in citation.get("images", []):
                            st.image(
                                f"{API_BASE_URL}{image['url']}",
                                caption=image.get("file_name"),
                            )
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": data["answer"],
                        "citations": data.get("citations", []),
                    }
                )
            except requests.RequestException:
                st.error("Backend đang tạm thời không phản hồi. Kiểm tra API rồi thử lại.")

with tab_documents:
    uploaded = st.file_uploader("Tải tài liệu vào hệ thống", type=["docx", "md", "txt"])
    if uploaded and st.button("Ingest tài liệu"):
        try:
            files = {"file": (uploaded.name, uploaded.getvalue())}
            response = requests.post(
                f"{API_BASE_URL}/api/v1/documents",
                files=files,
                timeout=300,
            )
            response.raise_for_status()
            st.success(response.json())
        except requests.RequestException:
            st.error("Không ingest được tài liệu. Kiểm tra API, Qdrant và embedding provider.")

    try:
        docs_response = requests.get(f"{API_BASE_URL}/api/v1/documents", timeout=30)
        docs_response.raise_for_status()
        documents = docs_response.json().get("documents", [])
        if documents:
            st.dataframe(documents, use_container_width=True)
        else:
            st.info("Chưa có tài liệu nào được ingest.")
    except requests.RequestException:
        st.warning("Chưa lấy được danh sách tài liệu từ API.")
