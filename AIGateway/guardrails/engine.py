"""不依赖 LiteLLM 的确定性护栏引擎，供评估门与单测使用。"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

DEFAULT_POLICY = Path(__file__).resolve().parent / "policy.yaml"

DENY_TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "illegal_advice": ["how to launder", "evade tax illegally", "forge documents"],
    "internal_policy_leak": ["internal policy dump", "leak confidential policy"],
    "market_manipulation": ["pump and dump scheme", "manipulate the stock"],
}

PII_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "[REDACTED_CARD]"),
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[REDACTED_EMAIL]",
    ),
]


@lru_cache(maxsize=4)
def load_policy(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def check_injection(text: str, policy: dict) -> Optional[str]:
    cfg = ((policy.get("rails") or {}).get("input") or {}).get("prompt_injection") or {}
    patterns = [p.lower() for p in (cfg.get("deny_patterns") or [])]
    lowered = text.lower()
    for pat in patterns:
        if pat and pat in lowered:
            return f"injection matched '{pat}'"
    return None


def check_dialog(text: str, messages: List[dict], policy: dict) -> Optional[str]:
    dialog = (policy.get("rails") or {}).get("dialog") or {}
    max_turns = int(dialog.get("max_turns") or 40)
    turns = sum(1 for m in messages if isinstance(m, dict) and m.get("role") == "user")
    if turns > max_turns:
        return f"max_turns={max_turns} exceeded"
    joined = text.lower()
    for topic in dialog.get("deny_topics") or []:
        for kw in DENY_TOPIC_KEYWORDS.get(topic, []):
            if kw in joined:
                return f"deny_topic='{topic}'"
    return None


def _tool_name(tool: Any) -> Optional[str]:
    if not isinstance(tool, dict):
        return None
    if "function" in tool and isinstance(tool["function"], dict):
        return tool["function"].get("name")
    return tool.get("name")


def check_tools(tools: List[Any], policy: dict) -> Optional[str]:
    tool_cfg = (policy.get("rails") or {}).get("tool") or {}
    allowlist = set(tool_cfg.get("allowlist") or [])
    denylist = set(tool_cfg.get("deny_list") or [])
    for t in tools or []:
        name = _tool_name(t)
        if not name:
            continue
        if name in denylist:
            return f"tool '{name}' in deny_list"
        if allowlist and name not in allowlist:
            return f"tool '{name}' not in allowlist"
    return None


def redact_pii(text: str) -> Tuple[str, bool]:
    """返回 (脱敏后文本, 是否命中过 PII)。"""
    hit = False
    out = text
    for pattern, repl in PII_PATTERNS:
        if pattern.search(out):
            hit = True
            out = pattern.sub(repl, out)
    return out, hit


def evaluate_request(
    text: str,
    policy: dict,
    *,
    tools: Optional[List[Any]] = None,
    messages: Optional[List[dict]] = None,
) -> Optional[str]:
    """若应拦截则返回原因，否则 None。"""
    msgs = messages or [{"role": "user", "content": text}]
    for checker in (
        lambda: check_injection(text, policy),
        lambda: check_dialog(text, msgs, policy),
        lambda: check_tools(tools or [], policy),
    ):
        reason = checker()
        if reason:
            return reason
    return None


def validate_tool_args(name: str, args: dict, schema: dict) -> Optional[str]:
    if schema.get("type") == "object" and not isinstance(args, dict):
        return f"'{name}' args must be object"
    for key in schema.get("required") or []:
        if key not in args:
            return f"'{name}' missing required '{key}'"
    props = schema.get("properties") or {}
    for key, prop in props.items():
        if key not in args:
            continue
        val = args[key]
        expected = prop.get("type")
        if expected == "string" and not isinstance(val, str):
            return f"'{name}.{key}' must be string"
        if expected == "integer" and not isinstance(val, int):
            return f"'{name}.{key}' must be integer"
        if "enum" in prop and val not in prop["enum"]:
            return f"'{name}.{key}' not in enum"
        if isinstance(val, str):
            if "minLength" in prop and len(val) < prop["minLength"]:
                return f"'{name}.{key}' too short"
            if "maxLength" in prop and len(val) > prop["maxLength"]:
                return f"'{name}.{key}' too long"
        if isinstance(val, (int, float)):
            if "minimum" in prop and val < prop["minimum"]:
                return f"'{name}.{key}' below minimum"
            if "maximum" in prop and val > prop["maximum"]:
                return f"'{name}.{key}' above maximum"
    return None


def parse_tool_args(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    raise ValueError("invalid tool args")
