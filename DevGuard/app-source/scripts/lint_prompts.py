#!/usr/bin/env python3
"""Lint prompt templates for risky patterns."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RISKY = [
    "ignore previous",
    "system override",
    "do anything now",
    "{{untrusted}}",
]


def lint_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8").lower()
    hits = [p for p in RISKY if p in text]
    return [f"{path}: contains risky pattern '{h}'" for h in hits]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=Path("prompts"))
    args = parser.parse_args()

    if not args.dir.is_dir():
        print(f"OK: prompts dir missing, skip ({args.dir})")
        return 0

    errors: list[str] = []
    for path in sorted(args.dir.rglob("*")):
        if path.is_file() and path.suffix in {".txt", ".md", ".j2", ".yaml", ".yml"}:
            errors.extend(lint_file(path))

    if errors:
        print("PROMPT LINT FAIL:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"OK: prompts under {args.dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
