"""Component registry: metadata always; KFP callables lazy-loaded for compile."""
from __future__ import annotations

from typing import Any, Callable, Dict

from .catalog import CATALOG, CATALOG_BY_ID

__all__ = ["CATALOG", "CATALOG_BY_ID", "get_function"]

_FUNCTIONS: Dict[str, Callable[..., Any]] | None = None


def _load_functions() -> Dict[str, Callable[..., Any]]:
    global _FUNCTIONS
    if _FUNCTIONS is None:
        from .library import evaluate_model, prepare_data, register_artifact, train_model

        _FUNCTIONS = {
            "prepare_data": prepare_data,
            "train_model": train_model,
            "evaluate_model": evaluate_model,
            "register_artifact": register_artifact,
        }
    return _FUNCTIONS


def get_function(component_id: str) -> Callable[..., Any]:
    fns = _load_functions()
    if component_id not in fns:
        raise KeyError(f"unknown component: {component_id}")
    return fns[component_id]
