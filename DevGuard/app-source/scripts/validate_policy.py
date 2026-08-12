#!/usr/bin/env python3
"""Validate guardrail policy YAML schema and required fields."""
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
    except Exception as exc:  # noqa: BLE001
        return [f"YAML parse error: {exc}"]

    if not isinstance(data, dict):
        return ["policy root must be a mapping"]

    if "version" not in data:
        errors.append("missing field: version")
    rails = data.get("rails")
    if not isinstance(rails, dict):
        errors.append("missing or invalid field: rails")
        return errors

    for name in REQUIRED_RAILS:
        if name not in rails:
            errors.append(f"missing rail: rails.{name}")

    tool = rails.get("tool") or {}
    if isinstance(tool, dict):
        allow = set(tool.get("allowlist") or [])
        deny = set(tool.get("deny_list") or [])
        overlap = allow & deny
        if overlap:
            errors.append(f"tool allowlist/deny_list overlap: {sorted(overlap)}")

    monitoring = rails.get("monitoring") or {}
    alert = (monitoring.get("alert") or {}) if isinstance(monitoring, dict) else {}
    fp = alert.get("false_positive_pct")
    if fp is not None and (not isinstance(fp, (int, float)) or fp < 0 or fp > 100):
        errors.append("monitoring.alert.false_positive_pct must be 0..100")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy", type=Path, help="Path to policy.yaml")
    args = parser.parse_args()

    if not args.policy.is_file():
        print(f"ERROR: file not found: {args.policy}", file=sys.stderr)
        return 2

    errors = validate(args.policy)
    if errors:
        print(f"FAIL: {args.policy} ({len(errors)} error(s))", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"OK: {args.policy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
