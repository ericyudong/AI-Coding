#!/usr/bin/env python3
"""Red-team / adversarial evaluation against jailbreak dataset."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

# ensure sibling import works when invoked as scripts/redteam.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
from guardrail_engine import decide  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=Path("guardrails/policy.yaml"))
    parser.add_argument("--dataset", type=Path, default=Path("eval/redteam.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("reports/redteam.json"))
    args = parser.parse_args()

    policy = yaml.safe_load(args.policy.read_text(encoding="utf-8"))
    dataset = load_jsonl(args.dataset)

    total = len(dataset)
    bypass = 0
    details: list[dict] = []

    for row in dataset:
        text = row.get("input") or ""
        tool = row.get("tool")
        expected = row.get("expected", "block")
        actual = decide(policy, text=text, tool=tool, is_output=False)
        ok = actual == expected or (
            expected in ("block", "deny") and actual in ("block", "deny")
        )
        if expected in ("block", "deny") and actual == "allow":
            bypass += 1
        details.append(
            {
                "id": row.get("id"),
                "attack": row.get("attack"),
                "expected": expected,
                "actual": actual,
                "pass": ok,
            }
        )

    bypass_pct = round(100.0 * bypass / total, 4) if total else 0.0
    report = {
        "total": total,
        "bypass_count": bypass,
        "jailbreak_bypass_pct": bypass_pct,
        "details": details,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"redteam: total={total} bypass={bypass_pct}% -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
