"""
Monitoring Rail：不可变审计回调 + x-model-tier 路由改写。

LiteLLM config:
  litellm_settings:
    callbacks: [..., custom_callbacks.audit_callback]
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from litellm.integrations.custom_logger import CustomLogger


TIER_TO_MODEL = {
    "premium": "default",
    "default": "default",
    "reasoning": "reasoning",
    "fast": "fast",
    "vision": "vision",
    "local": "local",
}


class AuditCallback(CustomLogger):
    """
    每次成功/失败请求写一行 JSONL 审计日志：
    路由后端、命中护栏、token、耗时、租户。
    """

    def __init__(self, log_path: Optional[str] = None, **kwargs: Any):
        super().__init__(**kwargs)
        self.log_path = Path(
            log_path
            or os.getenv("AUDIT_LOG_PATH", "/var/log/ai-gateway/audit.jsonl")
        )
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, record: dict) -> None:
        record["ts"] = datetime.now(timezone.utc).isoformat()
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._emit(kwargs, response_obj, start_time, end_time, status="success")

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        self._emit(kwargs, response_obj, start_time, end_time, status="failure")

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._emit(kwargs, response_obj, start_time, end_time, status="success")

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        self._emit(kwargs, response_obj, start_time, end_time, status="failure")

    def _emit(self, kwargs, response_obj, start_time, end_time, status: str) -> None:
        try:
            duration_ms = None
            if start_time is not None and end_time is not None:
                try:
                    duration_ms = (end_time - start_time).total_seconds() * 1000
                except Exception:
                    duration_ms = None

            usage = {}
            if response_obj is not None and hasattr(response_obj, "usage"):
                u = response_obj.usage
                usage = {
                    "prompt_tokens": getattr(u, "prompt_tokens", None),
                    "completion_tokens": getattr(u, "completion_tokens", None),
                    "total_tokens": getattr(u, "total_tokens", None),
                }

            litellm_params = kwargs.get("litellm_params") or {}
            metadata = litellm_params.get("metadata") or kwargs.get("metadata") or {}

            self._write(
                {
                    "status": status,
                    "model": kwargs.get("model"),
                    "call_type": kwargs.get("call_type"),
                    "duration_ms": duration_ms,
                    "usage": usage,
                    "guardrails": metadata.get("guardrail_information")
                    or kwargs.get("guardrails"),
                    "guardrail_reroute": metadata.get("guardrail_reroute"),
                    "user_api_key_hash": metadata.get("user_api_key_hash"),
                    "user_api_key_user_id": metadata.get("user_api_key_user_id"),
                    "user_api_key_team_id": metadata.get("user_api_key_team_id"),
                    "request_id": metadata.get("litellm_call_id")
                    or kwargs.get("litellm_call_id"),
                }
            )
        except Exception as exc:  # 审计失败不得影响主路径
            print(f"[audit_callback] write failed: {exc}")


audit_callback = AuditCallback()


# ---------------------------------------------------------------------------
# x-model-tier 中间件：在 proxy 请求进入路由前改写 model
# 通过 litellm 的 custom callback pre-call 钩子实现
# ---------------------------------------------------------------------------

class TierRoutingCallback(CustomLogger):
    """请求头 x-model-tier: premium|fast|local|... → 改写 data['model']。"""

    async def async_pre_call_hook(
        self,
        user_api_key_dict,
        cache,
        data: dict,
        call_type: str,
    ):
        headers = data.get("proxy_server_request", {}).get("headers") or {}
        # httpx / starlette 头名小写
        tier = (
            headers.get("x-model-tier")
            or headers.get("X-Model-Tier")
            or (data.get("metadata") or {}).get("model_tier")
        )
        if not tier:
            return data
        mapped = TIER_TO_MODEL.get(str(tier).lower().strip())
        if mapped:
            data.setdefault("metadata", {})["model_tier_original"] = data.get("model")
            data["model"] = mapped
        return data


tier_routing_callback = TierRoutingCallback()
