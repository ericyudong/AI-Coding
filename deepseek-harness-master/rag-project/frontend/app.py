"""Streamlit web frontend for the RAG application."""

from __future__ import annotations

import streamlit as st
import httpx

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="RAG 知识库问答", page_icon="📚", layout="wide")

# ── Sidebar: Document Management ─────────────────────────────────────

with st.sidebar:
    st.title("📚 RAG 知识库")
    st.caption("上传文档 → 自动分块嵌入 → 智能问答")

    st.divider()
    st.subheader("📤 上传文档")
    uploaded_file = st.file_uploader(
        "选择文件",
        type=["txt", "pdf", "md", "docx"],
        help="支持 .txt / .pdf / .md / .docx 格式",
    )
    if uploaded_file is not None:
        with st.spinner("正在上传并处理文档..."):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            try:
                resp = httpx.post(f"{API_BASE}/api/upload", files=files, timeout=120)
                resp.raise_for_status()
                data = resp.json()
                st.success(f"✅ {data['filename']} — {data['chunks_ingested']} 个文本块已入库")
            except httpx.HTTPStatusError as e:
                st.error(f"❌ 上传失败: {e.response.text}")
            except httpx.ConnectError:
                st.error("❌ 无法连接后端服务，请确认 FastAPI 已启动 (端口 8000)")

    st.divider()
    st.subheader("📋 已入库文档")
    try:
        docs_resp = httpx.get(f"{API_BASE}/api/documents", timeout=10)
        docs_resp.raise_for_status()
        docs = docs_resp.json()
        if docs:
            for doc in docs:
                col1, col2 = st.columns([3, 1])
                col1.text(f"📄 {doc['filename']}")
                col2.caption(f"{doc['chunks']} 块")
                if col2.button("🗑️", key=f"del_{doc['filename']}", help="删除此文档"):
                    del_resp = httpx.delete(f"{API_BASE}/api/documents/{doc['filename']}", timeout=10)
                    if del_resp.status_code == 200:
                        st.rerun()
                    else:
                        st.error("删除失败")
        else:
            st.info("暂无文档，请先上传")
    except httpx.ConnectError:
        st.warning("⚠️ 后端未连接")

    st.divider()
    st.caption("Powered by ChromaDB + Sentence Transformers + DeepSeek")


# ── Main Area: Chat Interface ─────────────────────────────────────────

st.title("💬 知识库问答")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander(f"📎 引用来源 ({len(msg['sources'])} 条)"):
                for i, src in enumerate(msg["sources"], 1):
                    st.caption(f"**[{i}] {src['filename']}** (距离: {src['distance']})")
                    st.code(src["preview"], language=None)

if prompt := st.chat_input("输入你的问题..."):
    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Query backend
    with st.chat_message("assistant"):
        with st.spinner("检索中..."):
            try:
                resp = httpx.post(
                    f"{API_BASE}/api/query",
                    json={"question": prompt, "top_k": 5},
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()
                answer = data["answer"]
                sources = data["sources"]
            except httpx.ConnectError:
                answer = "❌ 无法连接后端服务，请确认 FastAPI 已启动。"
                sources = []
            except httpx.HTTPStatusError as e:
                answer = f"❌ 查询失败: {e.response.text}"
                sources = []

        st.markdown(answer)
        if sources:
            with st.expander(f"📎 引用来源 ({len(sources)} 条)"):
                for i, src in enumerate(sources, 1):
                    st.caption(f"**[{i}] {src['filename']}** (距离: {src['distance']})")
                    st.code(src["preview"], language=None)

    st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
