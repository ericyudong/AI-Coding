"""CLI: python -m pipelines.compiler.from_spec [spec-id]"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.compiler.from_spec import SPECS_DIR, compile_spec_file, list_specs  # noqa: E402


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("-l", "--list"):
        for item in list_specs():
            print(f"{item['id']}\t{item.get('name')}\tsteps={item.get('steps')}")
        return
    sid = sys.argv[1] if len(sys.argv) > 1 else "fraud-default"
    path = SPECS_DIR / f"{sid}.yaml"
    if not path.is_file():
        raise SystemExit(f"spec not found: {path}")
    result = compile_spec_file(path)
    if not result["ok"]:
        print("FAIL", result["validation"])
        raise SystemExit(1)
    print("OK", result["package_path"])


if __name__ == "__main__":
    main()
