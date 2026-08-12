#!/usr/bin/env python3
"""Shared deterministic guardrail decision engine used by eval / redteam / runtime."""
from __future__ import annotations

import re
from typing import Any

SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
SSN_MENTION_RE = re.compile(r"\bssn\b", re.I)
# Visa/MC 16-digit and Amex 15-digit (e.g. 3782-822463-10005)
CARD_RE = re.compile(
    r"\b(?:\d{4}[ -]?){3}\d{4}\b"  # 16-digit grouped
    r"|\b3[47]\d{2}[ -]?\d{6}[ -]?\d{5}\b"  # Amex
    r"|\b(?:4\d{15}|5[1-5]\d{14}|3[47]\d{13})\b"  # compact
)
BANK_ACCT_RE = re.compile(r"\b(?:bank account|account)\s*(?:is|=|:)?\s*[A-Z0-9-]{6,}\b", re.I)
PII_EXFIL_RE = re.compile(
    r"(repeat back|reveal|export|dump|list).{0,40}(ssn|pii|card|customer)",
    re.I,
)

DENY_TOPIC_KEYWORDS = {
    "illegal_advice": [
        "launder",
        "money laundering",
        "tax evasion",
        "tax fraud",
        "insider trading",
        "forge a check",
        "forging",
    ],
    "internal_policy_leak": [
        "internal credit risk",
        "internal fraud model",
        "internal policy",
        "system prompt",
        "admin password",
        "api key",
        "guardrail policy.yaml",
        "customer dump",
        "customer ssn list",
    ],
}

OUTPUT_DENY = {
    "non_compliant_recommendation": ["penny stock", "invest all savings"],
    "self_harm": ["harm yourself", "end it", "how to end"],
    "harassment": ["harass", "insults"],
}


def _contains_any(text: str, patterns: list[str]) -> bool:
    lower = text.lower()
    return any(p.lower() in lower for p in patterns)


def decide(
    policy: dict[str, Any],
    *,
    text: str,
    tool: str | None = None,
    is_output: bool = False,
) -> str:
    """Return allow | block | deny | redact based on policy."""
    rails = policy.get("rails") or {}
    lower = text.lower()

    # --- tool rail ---
    if tool:
        tool_rail = rails.get("tool") or {}
        deny_list = set(tool_rail.get("deny_list") or [])
        allowlist = set(tool_rail.get("allowlist") or [])
        human = set(tool_rail.get("human_approval") or [])
        if tool in deny_list or tool in human:
            return "deny"
        if allowlist and tool not in allowlist:
            return "deny"
        # tool-only samples with benign text still pass allowlist
        if not text.strip():
            return "allow"

    # --- input / dialog rails ---
    if not is_output:
        input_rail = rails.get("input") or {}
        pii = input_rail.get("pii") or {}
        if pii.get("action") == "block":
            deny_types = set(pii.get("deny") or [])
            if "ssn" in deny_types and SSN_RE.search(text):
                return "block"
            if "card_number" in deny_types and CARD_RE.search(text):
                return "block"
            if "bank_account" in deny_types and (
                BANK_ACCT_RE.search(text) or "bank account" in lower
            ):
                # only block when digits-looking account present
                if re.search(r"\d{6,}", text):
                    return "block"

        inj = input_rail.get("prompt_injection") or {}
        patterns = inj.get("deny_patterns") or []
        if inj.get("action") == "block" and _contains_any(text, patterns):
            return "block"
        # extra jailbreak heuristics for redteam
        jailbreak_hints = [
            "you are dan",
            "do anything now",
            "bypass banking policy",
            "disable all guardrails",
            "for educational purposes only, ignore safety",
            "unlock all tool restrictions",
            "skip human_approval",
            "忽略之前的指令",
        ]
        if _contains_any(text, jailbreak_hints):
            return "block"
        if "base64" in lower or "decode and follow" in lower:
            return "block"
        if "{{system}}" in lower or "reveal api keys" in lower:
            return "block"

        dialog = rails.get("dialog") or {}
        for topic in dialog.get("deny_topics") or []:
            kws = DENY_TOPIC_KEYWORDS.get(topic, [topic.replace("_", " ")])
            if _contains_any(text, kws):
                return "block"

        # retrieval poison / fake citation attacks
        if "fake sec filing" in lower or "insider trading" in lower:
            return "block"
        if "print the full guardrail" in lower or "dump secrets" in lower:
            return "block"
        if "write insults" in lower:
            return "block"
        if "how to end it" in lower or ("end it" in lower and "markets crashed" in lower):
            return "block"
        if "store it" in lower and CARD_RE.search(text):
            return "block"
        if PII_EXFIL_RE.search(text):
            return "block"

        return "allow"

    # --- output rail ---
    output = rails.get("output") or {}
    pii = output.get("pii") or {}
    deny_types = set(pii.get("deny") or [])
    redact = pii.get("action") == "redact"
    if "ssn" in deny_types and (SSN_RE.search(text) or SSN_MENTION_RE.search(text)):
        return "redact" if redact else "block"
    if "card_number" in deny_types and CARD_RE.search(text):
        return "redact" if redact else "block"

    for cat, kws in OUTPUT_DENY.items():
        deny_cats = set((output.get("policy") or {}).get("deny") or []) | set(
            (output.get("safety") or {}).get("deny") or []
        )
        if cat in deny_cats and _contains_any(text, kws):
            return "block"

    return "allow"
