"""Embedding API integration."""
import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _parse_embedding_response(data: dict) -> list[list[float]]:
    if "data" in data and isinstance(data["data"], list):
        items = data["data"]
        if items and isinstance(items[0], dict) and "embedding" in items[0]:
            sorted_data = sorted(items, key=lambda x: x.get("index", 0))
            return [item["embedding"] for item in sorted_data]
    if "embeddings" in data and isinstance(data["embeddings"], list):
        return data["embeddings"]
    # MaaS / wrapped responses: { flag, data: { data: [...] } }
    inner = data.get("data")
    if isinstance(inner, dict):
        return _parse_embedding_response(inner)
    raise ValueError(f"Unrecognized embedding response: {list(data.keys())}")


async def embed_texts(texts: list[str]) -> list[list[float]] | None:
    settings = get_settings()
    if not settings.openai_api_key.strip() or not texts:
        return None

    url = f"{settings.openai_base_url.rstrip('/')}/embeddings"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    batch_size = settings.embedding_batch_size
    all_vectors: list[list[float]] = []

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                payload = {"model": settings.embedding_model, "input": batch}
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code >= 400:
                    logger.warning("Embedding API error %s: %s", resp.status_code, resp.text[:200])
                    return None
                data = resp.json()
                if isinstance(data, dict) and data.get("error"):
                    logger.warning("Embedding API error: %s", data.get("error"))
                    return None
                all_vectors.extend(_parse_embedding_response(data))
    except Exception as exc:
        logger.warning("Embedding failed: %s", exc)
        return None
    return all_vectors if all_vectors else None


async def embed_query(query: str) -> list[float] | None:
    vectors = await embed_texts([query])
    return vectors[0] if vectors else None
