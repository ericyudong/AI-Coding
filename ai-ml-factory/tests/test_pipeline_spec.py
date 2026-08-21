"""Scheme B: editable pipeline specs validate + compile."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipelines.compiler.from_spec import SPECS_DIR, compile_spec, load_spec
from pipelines.compiler.validate import validate_spec


def test_fraud_default_validates():
    spec = load_spec(SPECS_DIR / "fraud-default.yaml")
    r = validate_spec(spec)
    assert r["ok"], r["errors"]


def test_register_requires_evaluate():
    spec = load_spec(SPECS_DIR / "fraud-default.yaml")
    for step in spec["steps"]:
        if step["id"] == "evaluate":
            step["enabled"] = False
    r = validate_spec(spec)
    assert not r["ok"]
    assert any("evaluate" in e for e in r["errors"])


def test_train_only_compiles(tmp_path):
    try:
        import kfp  # noqa: F401
    except ImportError:
        return  # skip when kfp not installed
    spec = load_spec(SPECS_DIR / "train-only.yaml")
    out = tmp_path / "out.yaml"
    result = compile_spec(spec, package_path=out)
    assert result["ok"], result
    assert out.is_file()
    assert result["steps_compiled"] == 3
