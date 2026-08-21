"""LLM integration via OpenAI-compatible API."""

from __future__ import annotations

import os

from openai import OpenAI

from app.config import LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS

SYSTEM_PROMPT = """\
You are a helpful assistant that answers questions based on the provided context \
retrieved from uploaded documents. Follow these rules:
1. Answer ONLY using information from the context below.
2. If the context does not contain enough information, say so clearly.
3. Cite the source filename when referencing specific information.
4. Be concise and accurate. Do not fabricate information.
"""


def _client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY", "sk-placeholder")
    base_url = os.environ.get("OPENAI_BASE_URL", None)
    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def generate_answer(question: str, context_chunks: list[dict]) -> str:
    """Generate an answer grounded in the retrieved context."""
    if not context_chunks:
        return "未找到相关文档内容。请先上传相关文档后再提问。"

    context_parts = []
    for i, chunk in enumerate(context_chunks, 1):
        src = chunk["metadata"].get("filename", "unknown")
        context_parts.append(f"[Source {i}: {src}]\n{chunk['text']}")
    context_block = "\n\n---\n\n".join(context_parts)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Context:\n\n{context_block}\n\n---\n\nQuestion: {question}",
        },
    ]

    client = _client()
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
    )
    return response.choices[0].message.content or "(empty response)"
