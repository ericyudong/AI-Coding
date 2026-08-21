"""Validate editable pipeline specs (Scheme B)."""
from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

# Allow import both as package and from console (sys.path)
try:
    from pipelines.components.catalog import CATALOG_BY_ID
except ImportError:
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from pipelines.components.catalog import CATALOG_BY_ID


def _topo_ok(steps: List[Dict[str, Any]]) -> Tuple[bool, str]:
    ids = {s["id"] for s in steps}
    deps: Dict[str, Set[str]] = {s["id"]: set(s.get("needs") or []) for s in steps}
    for sid, need in deps.items():
        unknown = need - ids
        if unknown:
            return False, f"step '{sid}' needs unknown: {sorted(unknown)}"
    remaining = set(ids)
    while remaining:
        ready = [sid for sid in remaining if deps[sid].isdisjoint(remaining)]
        if not ready:
            return False, "cycle detected in step needs"
        for sid in ready:
            remaining.remove(sid)
    return True, ""


def validate_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Return {ok, errors[], warnings[]}."""
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(spec, dict):
        return {"ok": False, "errors": ["spec must be an object"], "warnings": []}

    name = spec.get("name") or ""
    if not name or not isinstance(name, str):
        errors.append("name is required")

    steps = spec.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("steps must be a non-empty list")
        return {"ok": False, "errors": errors, "warnings": warnings}

    ids: List[str] = []
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(f"steps[{i}] must be an object")
            continue
        sid = step.get("id")
        if not sid or not isinstance(sid, str):
            errors.append(f"steps[{i}].id is required")
            continue
        if sid in ids:
            errors.append(f"duplicate step id: {sid}")
        ids.append(sid)

        cid = step.get("component")
        if cid not in CATALOG_BY_ID:
            errors.append(f"step '{sid}': unknown component '{cid}'")
            continue

        meta = CATALOG_BY_ID[cid]
        params = step.get("params") or {}
        if not isinstance(params, dict):
            errors.append(f"step '{sid}': params must be an object")
        else:
            known = {p["name"] for p in meta["params"]}
            for k in params:
                if k not in known:
                    warnings.append(f"step '{sid}': unknown param '{k}' (ignored at compile)")

        inputs = step.get("inputs") or {}
        if not isinstance(inputs, dict):
            errors.append(f"step '{sid}': inputs must be an object")
        else:
            required = {inp["name"] for inp in meta["inputs"]}
            enabled = step.get("enabled", True)
            if enabled:
                missing = required - set(inputs)
                if missing:
                    errors.append(f"step '{sid}': missing inputs {sorted(missing)}")
                for key, ref in inputs.items():
                    if key not in required:
                        warnings.append(f"step '{sid}': unexpected input '{key}'")
                    if not isinstance(ref, str) or "." not in ref:
                        errors.append(f"step '{sid}': input '{key}' must be 'step.output'")

        needs = step.get("needs") or []
        if not isinstance(needs, list):
            errors.append(f"step '{sid}': needs must be a list")

    ok_topo, topo_msg = _topo_ok([s for s in steps if isinstance(s, dict) and s.get("id")])
    if not ok_topo:
        errors.append(topo_msg)

    # Cross-step: input refs must point to existing enabled producers
    by_id = {s["id"]: s for s in steps if isinstance(s, dict) and s.get("id")}
    for step in steps:
        if not isinstance(step, dict) or not step.get("enabled", True):
            continue
        sid = step.get("id")
        for key, ref in (step.get("inputs") or {}).items():
            if not isinstance(ref, str) or "." not in ref:
                continue
            src_id, out_name = ref.split(".", 1)
            src = by_id.get(src_id)
            if not src:
                errors.append(f"step '{sid}': input {key} refs missing step '{src_id}'")
                continue
            if not src.get("enabled", True):
                errors.append(f"step '{sid}': input {key} refs disabled step '{src_id}'")
                continue
            src_meta = CATALOG_BY_ID.get(src.get("component") or "")
            if src_meta:
                outs = {o["name"] for o in src_meta["outputs"]}
                if out_name not in outs:
                    errors.append(
                        f"step '{sid}': '{ref}' — step '{src_id}' has no output '{out_name}'"
                    )
            needs = set(step.get("needs") or [])
            if src_id not in needs:
                warnings.append(f"step '{sid}': input from '{src_id}' but not listed in needs")

    # Gate rule: register requires evaluate when both present
    enabled = [s for s in steps if isinstance(s, dict) and s.get("enabled", True)]
    comps = {s.get("component") for s in enabled}
    allow_skip = bool(spec.get("allow_skip_evaluate", False))
    if "register_artifact" in comps and "evaluate_model" not in comps and not allow_skip:
        errors.append("register_artifact requires evaluate_model (or set allow_skip_evaluate: true)")

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}
