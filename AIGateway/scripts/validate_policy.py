"""校验 guardrails/policy.yaml 结构与必填字段。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REQUIRED_RAILS = ("input", "dialog", "retrieval", "tool", "output", "monitoring")


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"YAML parse error: {exc}"]

    if not isinstance(data, dict):
        return ["root must be a mapping"]

    if "version" not in data:
        errors.append("missing version")

    rails = data.get("rails")
    if not isinstance(rails, dict):
        errors.append("missing rails mapping")
        return errors

    for name in REQUIRED_RAILS:
        if name not in rails:
            errors.append(f"missing rails.{name}")

    tool = rails.get("tool") or {}
    if "allowlist" not in tool:
        errors.append("rails.tool.allowlist required")
    allow = set(tool.get("allowlist") or [])
    deny = set(tool.get("deny_list") or [])
    overlap = allow & deny
    if overlap:
        errors.append(f"tool allowlist ∩ deny_list not empty: {sorted(overlap)}")

    mon = rails.get("monitoring") or {}
    alert = mon.get("alert") or {}
    for key in ("mttd_min", "mttr_min", "false_positive_pct"):
        if key not in alert:
            errors.append(f"rails.monitoring.alert.{key} required")

    gate = data.get("eval_gate") or {}
    for key in ("jailbreak_bypass_pct", "false_positive_pct", "pii_leak_pct"):
        if key not in gate:
            errors.append(f"eval_gate.{key} recommended/required")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("policy", type=Path, nargs="?", default=Path("guardrails/policy.yaml"))
    args = parser.parse_args()
    if not args.policy.exists():
        print(f"ERROR: {args.policy} not found", file=sys.stderr)
        return 2
    errors = validate(args.policy)
    if errors:
        print("INVALID policy:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK: {args.policy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
