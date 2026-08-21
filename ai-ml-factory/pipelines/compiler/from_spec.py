"""Compile editable pipeline specs → Kubeflow Pipelines IR (Scheme B)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

try:
    from pipelines.components import get_function
    from pipelines.components.catalog import CATALOG_BY_ID
    from pipelines.compiler.validate import validate_spec
except ImportError:
    import sys

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from pipelines.components import get_function
    from pipelines.components.catalog import CATALOG_BY_ID
    from pipelines.compiler.validate import validate_spec

PIPELINES_ROOT = Path(__file__).resolve().parents[1]
SPECS_DIR = PIPELINES_ROOT / "specs"
COMPILED_DIR = PIPELINES_ROOT / "compiled"


def load_spec(path: str | Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("spec YAML must be a mapping")
    return data


def dump_spec(spec: Dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(spec, f, sort_keys=False, allow_unicode=True)


def list_specs() -> List[Dict[str, Any]]:
    SPECS_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for p in sorted(SPECS_DIR.glob("*.yaml")) + sorted(SPECS_DIR.glob("*.yml")):
        try:
            spec = load_spec(p)
            items.append(
                {
                    "id": p.stem,
                    "path": str(p.relative_to(PIPELINES_ROOT.parent)),
                    "name": spec.get("name", p.stem),
                    "description": spec.get("description", ""),
                    "steps": len(spec.get("steps") or []),
                }
            )
        except Exception as exc:  # noqa: BLE001
            items.append({"id": p.stem, "path": str(p), "error": str(exc)})
    return items


def _resolve_ref(ref: str, tasks: Dict[str, Any]) -> Any:
    step_id, out_name = ref.split(".", 1)
    task = tasks[step_id]
    return task.outputs[out_name]


def build_pipeline_func(spec: Dict[str, Any]):
    """Return a @dsl.pipeline function constructed from the editable spec.

    Step params from the YAML are baked into the IR at compile time.
    Re-edit the spec and recompile to change topology or hyperparameters.
    """
    from kfp import dsl

    result = validate_spec(spec)
    if not result["ok"]:
        raise ValueError("invalid spec: " + "; ".join(result["errors"]))

    pipe_name = spec["name"]
    description = spec.get("description") or f"Compiled from editable spec: {pipe_name}"
    enabled_steps = [s for s in spec["steps"] if s.get("enabled", True)]

    @dsl.pipeline(name=pipe_name, description=description)
    def compiled_pipeline():
        tasks: Dict[str, Any] = {}
        for step in enabled_steps:
            fn = get_function(step["component"])
            meta = CATALOG_BY_ID[step["component"]]
            kwargs: Dict[str, Any] = {}
            step_params = step.get("params") or {}
            for p in meta["params"]:
                pname = p["name"]
                kwargs[pname] = step_params.get(pname, p.get("default"))
            for iname, ref in (step.get("inputs") or {}).items():
                kwargs[iname] = _resolve_ref(ref, tasks)
            tasks[step["id"]] = fn(**kwargs)

    return compiled_pipeline


def compile_spec(
    spec: Dict[str, Any],
    package_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Validate + compile spec to KFP YAML IR."""
    from kfp import compiler

    validation = validate_spec(spec)
    if not validation["ok"]:
        return {"ok": False, "validation": validation, "package_path": None}

    COMPILED_DIR.mkdir(parents=True, exist_ok=True)
    if package_path is None:
        safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in spec["name"])
        package_path = COMPILED_DIR / f"{safe}.yaml"
    package_path = Path(package_path)

    fn = build_pipeline_func(spec)
    compiler.Compiler().compile(pipeline_func=fn, package_path=str(package_path))
    return {
        "ok": True,
        "validation": validation,
        "package_path": str(package_path),
        "name": spec["name"],
        "steps_compiled": len([s for s in spec["steps"] if s.get("enabled", True)]),
    }


def compile_spec_file(spec_path: str | Path, package_path: Optional[str | Path] = None) -> Dict[str, Any]:
    return compile_spec(load_spec(spec_path), package_path=package_path)
