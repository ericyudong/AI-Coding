"""Deployments, routes, and request stats."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
CATALOG_FILE = os.path.join(DATA_DIR, "catalog.json")

_CLUSTER_ID_MAP = {
    "demo-prod": "prod-cn-shanghai",
    "demo-staging": "staging-cn-shanghai",
    "demo-edge": "edge-us-west",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _migrate_cluster_id(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    return _CLUSTER_ID_MAP.get(value, value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Catalog:
    def __init__(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        self.deployments: Dict[str, Dict[str, Any]] = {}
        self.routes: Dict[str, Dict[str, Any]] = {}
        self.stats: Dict[str, Any] = {
            "requests": 0,
            "errors": 0,
            "latency_ms_sum": 0.0,
            "by_cluster": {},
            "by_model": {},
        }
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        if not os.path.isfile(CATALOG_FILE):
            return
        try:
            with open(CATALOG_FILE, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            for item in payload.get("deployments", []):
                old = item.get("cluster_id")
                item["cluster_id"] = _migrate_cluster_id(old)
                if old and old != item["cluster_id"] and item.get("endpoint"):
                    item["endpoint"] = str(item["endpoint"]).replace(f"mock://{old}", f"mock://{item['cluster_id']}")
                self.deployments[item["id"]] = item
            for item in payload.get("routes", []):
                self.routes[item["name"]] = item
        except Exception:
            pass

    def save(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CATALOG_FILE, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "deployments": list(self.deployments.values()),
                    "routes": list(self.routes.values()),
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )

    def gpu_used(self, cluster_id: str) -> int:
        used = 0
        for item in self.deployments.values():
            if item["cluster_id"] == cluster_id and item["status"] in ("running", "deploying"):
                used += int(item.get("gpu") or 0) * int(item.get("replicas") or 1)
        return used

    def list_deployments(self, cluster_id: Optional[str] = None) -> List[Dict[str, Any]]:
        items = list(self.deployments.values())
        if cluster_id:
            items = [x for x in items if x["cluster_id"] == cluster_id]
        return items

    def put_deployment(self, record: Dict[str, Any]) -> Dict[str, Any]:
        record["updated_at"] = _now()
        self.deployments[record["id"]] = record
        self.save()
        return record

    def delete_deployment(self, deployment_id: str) -> Dict[str, Any]:
        record = self.deployments.pop(deployment_id)
        # drop from routes
        for route in list(self.routes.values()):
            route["backends"] = [b for b in route.get("backends", []) if b.get("deployment_id") != deployment_id]
            if not route["backends"]:
                self.routes.pop(route["name"], None)
        self.save()
        return record

    def upsert_route(self, name: str, strategy: str, backends: List[Dict[str, Any]]) -> Dict[str, Any]:
        route = {"name": name, "strategy": strategy, "backends": backends, "updated_at": _now()}
        self.routes[name] = route
        self.save()
        return route

    def record_request(self, model: str, cluster_id: str, latency_ms: float, ok: bool) -> None:
        with self._lock:
            self.stats["requests"] += 1
            if not ok:
                self.stats["errors"] += 1
            self.stats["latency_ms_sum"] += latency_ms
            by_c = self.stats["by_cluster"].setdefault(cluster_id, {"requests": 0, "errors": 0})
            by_c["requests"] += 1
            if not ok:
                by_c["errors"] += 1
            by_m = self.stats["by_model"].setdefault(model, {"requests": 0, "errors": 0})
            by_m["requests"] += 1
            if not ok:
                by_m["errors"] += 1

    def snapshot(self) -> Dict[str, Any]:
        req = self.stats["requests"]
        avg = (self.stats["latency_ms_sum"] / req) if req else 0
        return {**self.stats, "avg_latency_ms": round(avg, 1)}


catalog = Catalog()
