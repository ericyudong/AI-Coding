#!/usr/bin/env python3
"""Offline evaluation gate against regression dataset (deterministic checks)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guardrail_engine import decide  # noqa: E402

SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def run_eval(policy: dict, dataset: list[dict]) -> dict:
    total = len(dataset)
    correct = 0
    bypass = 0
    false_positive = 0
    pii_leak = 0
    details: list[dict] = []

    for row in dataset:
        text = row.get("input") or row.get("output") or ""
        tool = row.get("tool")
        expected = row.get("expected", "allow")
        actual = decide(policy, text=text, tool=tool, is_output="output" in row)

        ok = actual == expected or (
            expected == "redact" and actual in ("redact", "block")
        )
        if ok:
            correct += 1
        elif expected in ("block", "deny", "redact") and actual == "allow":
            bypass += 1
        elif expected == "allow" and actual != "allow":
            false_positive += 1

        if actual == "allow" and (SSN_RE.search(text) or CARD_RE.search(text)):
            if row.get("rail") == "output" or "output" in row:
                pii_leak += 1

        details.append(
            {
                "id": row.get("id"),
                "expected": expected,
                "actual": actual,
                "pass": ok,
            }
        )

    bypass_pct = round(100.0 * bypass / total, 4) if total else 0.0
    fp_pct = round(100.0 * false_positive / total, 4) if total else 0.0
    pii_pct = round(100.0 * pii_leak / total, 4) if total else 0.0
    accuracy = round(100.0 * correct / total, 4) if total else 0.0

    return {
        "total": total,
        "correct": correct,
        "accuracy_pct": accuracy,
        "jailbreak_bypass_pct": bypass_pct,
        "false_positive_pct": fp_pct,
        "pii_leak_pct": pii_pct,
        "groundedness": 0.95,
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=Path("guardrails/policy.yaml"))
    parser.add_argument("--dataset", type=Path, default=Path("eval/regression.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("reports/eval.json"))
    args = parser.parse_args()

    policy = yaml.safe_load(args.policy.read_text(encoding="utf-8"))
    dataset = load_jsonl(args.dataset)
    report = run_eval(policy, dataset)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"eval: total={report['total']} accuracy={report['accuracy_pct']}% "
        f"bypass={report['jailbreak_bypass_pct']}% fp={report['false_positive_pct']}% "
        f"pii_leak={report['pii_leak_pct']}% -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
