"""
LiteLLM 自定义护栏：Injection / Dialog / Tool / Output PII
逻辑核心在 guardrails.engine；本模块仅做 LiteLLM CustomGuardrail 适配。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

from litellm.caching.caching import DualCache
from litellm.integrations.custom_guardrail import CustomGuardrail
from litellm.proxy._types import UserAPIKeyAuth

from guardrails.engine import (
    check_dialog,
    check_injection,
    check_tools,
    load_policy,
    parse_tool_args,
    redact_pii,
    validate_tool_args,
)

if TYPE_CHECKING:
    from litellm.litellm_core_utils.litellm_logging import Logging as LiteLLMLoggingObj
    from litellm.types.utils import GenericGuardrailAPIInputs
else:
    GenericGuardrailAPIInputs = Dict[str, Any]


DEFAULT_POLICY = Path(__file__).resolve().parent / "guardrails" / "policy.yaml"


def _policy_path(explicit: Optional[str] = None) -> str:
    return explicit or os.getenv("GUARDRAIL_POLICY_PATH", str(DEFAULT_POLICY))


def _texts_from_inputs(inputs: GenericGuardrailAPIInputs) -> List[str]:
    texts = list(inputs.get("texts") or [])
    if texts:
        return texts
    messages = inputs.get("structured_messages") or []
    out: List[str] = []
    for m in messages:
        content = m.get("content") if isinstance(m, dict) else None
        if isinstance(content, str):
            out.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    out.append(str(part.get("text", "")))
    return out


class _PolicyGuardrail(CustomGuardrail):
    def __init__(self, policy_path: Optional[str] = None, **kwargs: Any):
        self.policy_path = _policy_path(policy_path)
        load_policy.cache_clear()
        self.policy = load_policy(self.policy_path)
        super().__init__(**kwargs)

    @property
    def rails(self) -> dict:
        return self.policy.get("rails") or {}


class InjectionRail(_PolicyGuardrail):
    async def apply_guardrail(
        self,
        inputs: GenericGuardrailAPIInputs,
        request_data: dict,
        input_type: Literal["request", "response"],
        logging_obj: Optional["LiteLLMLoggingObj"] = None,
    ) -> GenericGuardrailAPIInputs:
        if input_type != "request":
            return inputs
        cfg = (self.rails.get("input") or {}).get("prompt_injection") or {}
        action = cfg.get("action", "block")
        reroute = cfg.get("on_block_reroute")
        for text in _texts_from_inputs(inputs):
            reason = check_injection(text, self.policy)
            if not reason:
                continue
            if reroute:
                request_data["model"] = reroute
                request_data.setdefault("metadata", {})["guardrail_reroute"] = {
                    "from": "injection-rail",
                    "to": reroute,
                    "reason": reason,
                }
                return inputs
            if action == "block":
                raise Exception(f"Guardrail injection-rail blocked: {reason}")
        return inputs


class DialogRail(_PolicyGuardrail):
    async def apply_guardrail(
        self,
        inputs: GenericGuardrailAPIInputs,
        request_data: dict,
        input_type: Literal["request", "response"],
        logging_obj: Optional["LiteLLMLoggingObj"] = None,
    ) -> GenericGuardrailAPIInputs:
        if input_type != "request":
            return inputs
        messages = inputs.get("structured_messages") or request_data.get("messages") or []
        text = " ".join(_texts_from_inputs(inputs))
        reason = check_dialog(text, messages, self.policy)
        if reason:
            raise Exception(f"Guardrail dialog-rail blocked: {reason}")
        return inputs


class ToolRail(_PolicyGuardrail):
    async def apply_guardrail(
        self,
        inputs: GenericGuardrailAPIInputs,
        request_data: dict,
        input_type: Literal["request", "response"],
        logging_obj: Optional["LiteLLMLoggingObj"] = None,
    ) -> GenericGuardrailAPIInputs:
        tools = inputs.get("tools") or request_data.get("tools") or []
        reason = check_tools(tools, self.policy)
        if reason:
            raise Exception(f"Guardrail tool-rail blocked: {reason}")

        schemas = (self.rails.get("tool") or {}).get("schemas") or {}
        tool_calls = list(inputs.get("tool_calls") or [])
        if input_type == "response" or tool_calls:
            for tc in tool_calls:
                name = (tc.get("function") or {}).get("name") if isinstance(tc, dict) else None
                if not name:
                    continue
                reason = check_tools(
                    [{"type": "function", "function": {"name": name}}], self.policy
                )
                if reason:
                    raise Exception(f"Guardrail tool-rail blocked: {reason}")
                raw = (tc.get("function") or {}).get("arguments")
                if name in schemas and raw is not None:
                    try:
                        args = parse_tool_args(raw)
                    except Exception as exc:
                        raise Exception(
                            f"Guardrail tool-rail blocked: invalid JSON args ({exc})"
                        ) from exc
                    err = validate_tool_args(name, args, schemas[name])
                    if err:
                        raise Exception(f"Guardrail tool-rail blocked: {err}")
        return inputs

    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        cache: DualCache,
        data: dict,
        call_type: Literal[
            "completion",
            "text_completion",
            "embeddings",
            "image_generation",
            "moderation",
            "audio_transcription",
            "pass_through_endpoint",
            "rerank",
        ],
    ):
        reason = check_tools(data.get("tools") or [], self.policy)
        if reason:
            raise Exception(f"Guardrail tool-rail blocked: {reason}")
        schemas = (self.rails.get("tool") or {}).get("schemas") or {}
        for msg in data.get("messages") or []:
            if not isinstance(msg, dict):
                continue
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                name = fn.get("name")
                if not name:
                    continue
                reason = check_tools(
                    [{"type": "function", "function": {"name": name}}], self.policy
                )
                if reason:
                    raise Exception(f"Guardrail tool-rail blocked: {reason}")
                if name in schemas and fn.get("arguments") is not None:
                    args = parse_tool_args(fn.get("arguments"))
                    err = validate_tool_args(name, args, schemas[name])
                    if err:
                        raise Exception(f"Guardrail tool-rail blocked: {err}")
        return data


class OutputPiiRail(_PolicyGuardrail):
    async def apply_guardrail(
        self,
        inputs: GenericGuardrailAPIInputs,
        request_data: dict,
        input_type: Literal["request", "response"],
        logging_obj: Optional["LiteLLMLoggingObj"] = None,
    ) -> GenericGuardrailAPIInputs:
        if input_type != "response":
            return inputs
        action = ((self.rails.get("output") or {}).get("pii") or {}).get("action", "redact")
        new_texts: List[str] = []
        for text in inputs.get("texts") or []:
            redacted, hit = redact_pii(text)
            if hit and action == "block":
                raise Exception("Guardrail output-pii-rail blocked: PII in response")
            new_texts.append(redacted if action == "redact" else text)
        inputs["texts"] = new_texts
        return inputs
