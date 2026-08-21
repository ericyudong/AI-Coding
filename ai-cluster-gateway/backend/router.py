"""Pick a healthy backend for a public model name."""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from catalog import catalog
from clusters import clusters


class RouteError(Exception):
    def __init__(self, message: str, status_code: int = 404):
        super().__init__(message)
        self.status_code = status_code


def _healthy(deployment: Dict[str, Any]) -> bool:
    if deployment.get("status") != "running" or not deployment.get("endpoint"):
        return False
    try:
        return clusters.accepted(deployment["cluster_id"])
    except KeyError:
        return False


def resolve(
    model: str,
    cluster_id: Optional[str] = None,
    region: Optional[str] = None,
) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []

    if cluster_id:
        for item in catalog.list_deployments(cluster_id):
            if item["alias"] == model or model in catalog.routes:
                if item["alias"] == model or any(
                    b.get("deployment_id") == item["id"]
                    for b in (catalog.routes.get(model) or {}).get("backends", [])
                ):
                    if _healthy(item):
                        candidates.append(item)
        if not candidates:
            raise RouteError(f"集群 {cluster_id} 上没有可用模型 {model}", 404)
        return candidates[0]

    route = catalog.routes.get(model)
    if route:
        ordered = []
        for backend in route.get("backends", []):
            dep = catalog.deployments.get(backend["deployment_id"])
            if not dep or not _healthy(dep):
                continue
            if region and dep.get("region") != region:
                continue
            ordered.append((dep, int(backend.get("weight") or 1)))
        if not ordered:
            raise RouteError(f"模型 {model} 没有健康后端", 503)
        if route.get("strategy") == "failover":
            return ordered[0][0]
        weights = [w for _, w in ordered]
        return random.choices([d for d, _ in ordered], weights=weights, k=1)[0]

    for item in catalog.list_deployments():
        if item["alias"] == model and _healthy(item):
            if region and item.get("region") != region:
                continue
            candidates.append(item)
    if not candidates:
        raise RouteError(f"未知模型 {model}", 404)
    return candidates[0]


def list_public_models() -> List[Dict[str, Any]]:
    models = []
    for name, route in catalog.routes.items():
        backends = []
        for backend in route.get("backends", []):
            dep = catalog.deployments.get(backend["deployment_id"])
            if dep:
                backends.append(
                    {
                        "alias": dep["alias"],
                        "cluster": dep["cluster_name"],
                        "region": dep.get("region"),
                        "status": dep["status"],
                        "weight": backend.get("weight"),
                    }
                )
        models.append({"id": name, "object": "model", "owned_by": "ai-cluster-gateway", "route": route["strategy"], "backends": backends})
    seen = {m["id"] for m in models}
    for dep in catalog.list_deployments():
        if dep["alias"] not in seen:
            models.append(
                {
                    "id": dep["alias"],
                    "object": "model",
                    "owned_by": "ai-cluster-gateway",
                    "route": "direct",
                    "backends": [{"alias": dep["alias"], "cluster": dep["cluster_name"], "region": dep.get("region"), "status": dep["status"]}],
                }
            )
    return models
