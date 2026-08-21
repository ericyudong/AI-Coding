"""Forward chat completions to a cluster backend (or mock runtime)."""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from catalog import catalog
from router import resolve

MOCK_REPLIES = {
    "qwen2-72b": "（prod-cn-shanghai / qwen2-72b）这是生产集群上的大模型回答。",
    "llama3-70b": "（prod-cn-shanghai / llama3-70b）failover 后端已承接请求。",
    "qwen2-7b": "（staging-cn-shanghai / qwen2-7b）预发集群上的通用对话模型。",
    "qwen2-1.5b": "（edge-us-west / qwen2-1.5b）边缘小模型，延迟更低。",
}


async def chat_completions(
    payload: Dict[str, Any],
    cluster_id: Optional[str] = None,
    region: Optional[str] = None,
) -> Dict[str, Any]:
    model = payload.get("model") or "default"
    started = time.perf_counter()
    backend = resolve(model, cluster_id=cluster_id, region=region)
    try:
        if str(backend.get("endpoint") or "").startswith("mock://"):
            result = _mock_completion(payload, backend)
        else:
            result = await _proxy_completion(payload, backend)
        latency = (time.perf_counter() - started) * 1000
        catalog.record_request(model, backend["cluster_id"], latency, True)
        result["gateway"] = {
            "model": model,
            "served_as": backend["alias"],
            "cluster_id": backend["cluster_id"],
            "cluster": backend["cluster_name"],
            "region": backend.get("region"),
            "deployment_id": backend["id"],
            "latency_ms": round(latency, 1),
        }
        return result
    except Exception:
        latency = (time.perf_counter() - started) * 1000
        catalog.record_request(model, backend["cluster_id"], latency, False)
        raise


def _mock_completion(payload: Dict[str, Any], backend: Dict[str, Any]) -> Dict[str, Any]:
    messages = payload.get("messages") or []
    last = ""
    for item in reversed(messages):
        if item.get("role") == "user":
            last = item.get("content") or ""
            break
    reply = MOCK_REPLIES.get(backend["alias"], f"已由 {backend['cluster_name']} 上的 {backend['alias']} 处理。")
    if last:
        reply += f"\n\n用户问：{last[:180]}"
    prompt_tokens = max(1, len(last) // 4)
    completion_tokens = max(1, len(reply) // 4)
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": backend["alias"],
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


async def _proxy_completion(payload: Dict[str, Any], backend: Dict[str, Any]) -> Dict[str, Any]:
    import httpx

    url = backend["endpoint"].rstrip("/")
    if not url.endswith("/chat/completions"):
        url = url + "/chat/completions"
    body = {**payload, "model": backend["alias"], "stream": False}
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(url, json=body)
        response.raise_for_status()
        return response.json()
