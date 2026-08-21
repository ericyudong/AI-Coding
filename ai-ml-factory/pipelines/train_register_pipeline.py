"""Kubeflow Pipelines entrypoint — compiles default editable spec (Scheme B).

Edit pipelines/specs/*.yaml (or use the Console Pipeline Editor), then:

  python -m pipelines.train_register_pipeline
  # or
  python -m pipelines.compiler.from_spec
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.compiler.from_spec import SPECS_DIR, compile_spec_file  # noqa: E402


def main(spec_id: str = "fraud-default") -> None:
    spec_path = SPECS_DIR / f"{spec_id}.yaml"
    if not spec_path.is_file():
        raise SystemExit(f"spec not found: {spec_path}")
    result = compile_spec_file(spec_path)
    if not result["ok"]:
        print("validation failed:", result["validation"]["errors"])
        raise SystemExit(1)
    print(f"compiled → {result['package_path']} ({result['steps_compiled']} steps)")


if __name__ == "__main__":
    sid = sys.argv[1] if len(sys.argv) > 1 else "fraud-default"
    main(sid)
