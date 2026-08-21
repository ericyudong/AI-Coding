"""
OCM Hub 适配层：把 ManagedCluster 接到本机资源采集。

生产 OCM 中 Hub 不保存 spoke kubeconfig，由 Klusterlet pull ManifestWork。
本演示里 kubeconfig 仅用于：
1. clusteradm join 式引导（创建 CSR / ManagedCluster）
2. 模拟 cluster-proxy addon，在已接受集群上做只读 inventory
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from k8s_service import (
    K8sClusterService,
    format_cpu,
    format_memory,
    list_kube_contexts,
)
from ocm_hub import hub

logger = logging.getLogger(__name__)

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
KUBECONFIG_DIR = os.path.join(DATA_DIR, "kubeconfigs")


def _percent(used: float, total: float) -> float:
    if not total:
        return 0.0
    return round(min(100.0, max(0.0, (used / total) * 100.0)), 1)


def _cond_map(cluster: Dict[str, Any]) -> Dict[str, str]:
    return {
        c.get("type"): c.get("status")
        for c in (cluster.get("status") or {}).get("conditions") or []
    }


def _ocm_health(cluster: Dict[str, Any]) -> str:
    local = cluster.get("_local") or {}
    cond = _cond_map(cluster)
    if cond.get("HubAcceptedManagedCluster") != "True":
        return "pending"
    if local.get("source") == "demo":
        return "demo"
    if cond.get("ManagedClusterAvailable") == "True":
        return "healthy"
    if cond.get("ManagedClusterJoined") == "True":
        return "degraded"
    return "offline"


class ClusterManager:
    """ManagedCluster 生命周期 + 已接受集群的 inventory 连接。"""

    def __init__(self) -> None:
        os.makedirs(KUBECONFIG_DIR, exist_ok=True)
        self.services: Dict[str, K8sClusterService] = {}
        self._attach_all()

    def _attach_all(self) -> None:
        for name, cluster in hub.managed_clusters.items():
            if hub._accepted(cluster):
                self._attach_service(name, persist=False)

    def _attach_service(self, name: str, persist: bool = True) -> None:
        cluster = hub.get_managed_cluster(name)
        local = cluster.get("_local") or {}
        existing = self.services.get(name)
        if existing:
            existing._close_client()
        service = K8sClusterService(
            mock_profile=local.get("mock_profile") if local.get("source") == "demo" else None
        )
        if local.get("source") == "demo":
            service.use_mock(local.get("mock_profile") or "prod")
        elif local.get("kubeconfig_path"):
            result = service.connect(local["kubeconfig_path"], local.get("context"))
            if not result.get("ok"):
                logger.warning("ManagedCluster %s 连接失败: %s", name, result.get("error"))
        else:
            service.mark_offline("未配置 kubeconfig（OCM 生产模式由 klusterlet pull）")
        self.services[name] = service

    def _sync_heartbeat(self, name: str) -> None:
        cluster = hub.get_managed_cluster(name)
        if not hub._accepted(cluster):
            return
        service = self.services.get(name)
        if not service:
            return
        overview = service.get_overview()
        status = overview.get("status") or {}
        resources = overview.get("resources") or {}
        cpu = resources.get("cpu") or {}
        mem = resources.get("memory") or {}
        gpu = resources.get("gpu") or {}
        labels = cluster.get("metadata", {}).get("labels") or {}
        claims = [
            {"name": "id.k8s.io", "value": name},
            {"name": "region.open-cluster-management.io", "value": labels.get("region", "")},
            {
                "name": "gpu.open-cluster-management.io",
                "value": "true" if (gpu.get("capacity") or 0) > 0 else "false",
            },
        ]
        capacity: Dict[str, Any] = {
            "cpu": str(int(cpu.get("allocatable") or 0)),
            "memory": format_memory(int(mem.get("allocatable") or 0)).replace(" ", ""),
        }
        if gpu.get("capacity"):
            capacity["nvidia.com/gpu"] = str(int(gpu["capacity"]))
        version = status.get("version") or "Unknown"
        hub.update_heartbeat(name, claims, version, capacity)

    def _sync_from_hub(self) -> None:
        hub.reload_if_changed()
        for name, cluster in list(hub.managed_clusters.items()):
            if hub._accepted(cluster) and name not in self.services:
                self._attach_service(name, persist=False)
            if not hub._accepted(cluster) and name in self.services:
                service = self.services.pop(name)
                service._close_client()

    def list_clusters(self) -> List[Dict[str, Any]]:
        self._sync_from_hub()
        return [self.get_cluster(name) for name in hub.managed_clusters]

    def get_cluster(self, name: str) -> Dict[str, Any]:
        self._sync_from_hub()
        cluster = hub.get_managed_cluster(name)
        local = cluster.get("_local") or {}
        labels = cluster.get("metadata", {}).get("labels") or {}
        health = _ocm_health(cluster)
        counts: Dict[str, Any] = {}
        resources: Dict[str, Any] = {}
        pod_phases: Dict[str, Any] = {}
        k8s_status: Dict[str, Any] = {}
        if hub._accepted(cluster) and name in self.services:
            overview = self.services[name].get_overview()
            k8s_status = overview.get("status") or self.services[name].get_status()
            counts = overview.get("counts") or {}
            resources = overview.get("resources") or {}
            pod_phases = overview.get("pod_phases") or {}
            if k8s_status.get("connected") and counts.get("nodes") and counts.get("nodes_ready", 0) < counts["nodes"]:
                if health not in ("demo", "pending"):
                    health = "degraded"
            if self.services[name].mode == "demo":
                health = "degraded" if counts.get("nodes") and counts.get("nodes_ready", 0) < counts["nodes"] else "demo"
        cond = _cond_map(cluster)
        return {
            "id": name,
            "name": name,
            "kind": "ManagedCluster",
            "apiVersion": cluster.get("apiVersion"),
            "environment": labels.get("environment") or "production",
            "region": labels.get("region") or "",
            "labels": labels,
            "source": local.get("source") or "ocm",
            "kubeconfig_path": local.get("kubeconfig_path"),
            "context": local.get("context"),
            "hubAcceptsClient": bool((cluster.get("spec") or {}).get("hubAcceptsClient")),
            "clusterNamespace": local.get("clusterNamespace") or name,
            "csr": local.get("csr"),
            "conditions": (cluster.get("status") or {}).get("conditions") or [],
            "clusterClaims": (cluster.get("status") or {}).get("clusterClaims") or [],
            "capacity": (cluster.get("status") or {}).get("capacity") or {},
            "joined": cond.get("ManagedClusterJoined") == "True",
            "available": cond.get("ManagedClusterAvailable") == "True",
            "status": {**k8s_status, "health": health, "version": ((cluster.get("status") or {}).get("version") or {}).get("kubernetes")},
            "counts": counts,
            "resources": resources,
            "pod_phases": pod_phases,
            "managedCluster": cluster,
        }

    def join_cluster(
        self,
        name: str,
        kubeconfig_path: str,
        context: Optional[str] = None,
        environment: str = "production",
        region: str = "",
        labels: Optional[Dict[str, str]] = None,
        auto_accept: bool = False,
    ) -> Dict[str, Any]:
        path = os.path.expanduser(kubeconfig_path)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"kubeconfig 不存在: {path}")
        ctx_info = list_kube_contexts(path)
        context = context or ctx_info.get("current")
        display = (name or "").strip() or context or os.path.basename(path)
        merged = {"environment": environment or "production", "region": region or "", **(labels or {})}
        if region:
            merged["region"] = region
        cluster = hub.join(
            name=display,
            kubeconfig_path=path,
            context=context,
            labels=merged,
            client_url=None,
            source="kubeconfig",
            auto_accept=auto_accept,
        )
        joined = cluster["metadata"]["name"]
        if hub._accepted(cluster):
            self._attach_service(joined)
            self._sync_heartbeat(joined)
        return self.get_cluster(joined)

    def add_cluster(self, **kwargs: Any) -> Dict[str, Any]:
        """兼容旧 API：注册即发起 join，默认不自动 accept（OCM 双向握手）。"""
        kwargs.setdefault("auto_accept", False)
        return self.join_cluster(**kwargs)

    def import_kubeconfig(
        self,
        kubeconfig_path: str,
        environment: str = "production",
        region: str = "",
        auto_accept: bool = False,
    ) -> List[Dict[str, Any]]:
        path = os.path.expanduser(kubeconfig_path)
        ctx_info = list_kube_contexts(path)
        created = []
        existing = set(hub.managed_clusters)
        for ctx in ctx_info.get("contexts", []):
            if ctx["name"] in existing:
                continue
            created.append(
                self.join_cluster(
                    name=ctx["name"],
                    kubeconfig_path=path,
                    context=ctx["name"],
                    environment=environment,
                    region=region,
                    auto_accept=auto_accept,
                )
            )
        return created

    def add_from_upload(
        self,
        content: str,
        name: Optional[str] = None,
        context: Optional[str] = None,
        environment: str = "production",
        region: str = "",
        import_all: bool = False,
        auto_accept: bool = False,
    ) -> List[Dict[str, Any]]:
        token = uuid.uuid4().hex[:10]
        path = os.path.join(KUBECONFIG_DIR, f"{token}.yaml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        if import_all:
            return self.import_kubeconfig(path, environment, region, auto_accept=auto_accept)
        return [
            self.join_cluster(
                name=name or "",
                kubeconfig_path=path,
                context=context,
                environment=environment,
                region=region,
                auto_accept=auto_accept,
            )
        ]

    def accept(self, name: str) -> Dict[str, Any]:
        hub.accept(name)
        self._attach_service(name)
        self._sync_heartbeat(name)
        return self.get_cluster(name)

    def deny(self, name: str) -> Dict[str, Any]:
        service = self.services.pop(name, None)
        if service:
            service._close_client()
        hub.deny(name)
        return self.get_cluster(name)

    def update_cluster(self, name: str, **fields: Any) -> Dict[str, Any]:
        cluster = hub.get_managed_cluster(name)
        labels = cluster["metadata"].setdefault("labels", {})
        if fields.get("environment") is not None:
            labels["environment"] = fields["environment"]
        if fields.get("region") is not None:
            labels["region"] = fields["region"]
        if fields.get("labels"):
            labels.update(fields["labels"])
        local = cluster.setdefault("_local", {})
        if fields.get("context") is not None:
            local["context"] = fields["context"]
            if local.get("kubeconfig_path") and local.get("source") != "demo" and name in self.services:
                self.services[name].connect(local["kubeconfig_path"], local.get("context"))
        hub._save()
        return self.get_cluster(name)

    def delete_cluster(self, name: str) -> None:
        cluster = hub.get_managed_cluster(name)
        local = cluster.get("_local") or {}
        service = self.services.pop(name, None)
        if service:
            service._close_client()
        path = local.get("kubeconfig_path") or ""
        if local.get("source") != "demo" and path.startswith(KUBECONFIG_DIR) and os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass
        hub.delete(name)

    def refresh_cluster(self, name: str) -> Dict[str, Any]:
        cluster = hub.get_managed_cluster(name)
        if not hub._accepted(cluster):
            return self.get_cluster(name)
        if name not in self.services:
            self._attach_service(name)
        local = cluster.get("_local") or {}
        service = self.services[name]
        if local.get("source") == "demo":
            service.use_mock(local.get("mock_profile") or "prod")
        elif local.get("kubeconfig_path"):
            service.connect(local["kubeconfig_path"], local.get("context"))
        self._sync_heartbeat(name)
        return self.get_cluster(name)

    def service(self, name: str) -> K8sClusterService:
        cluster = hub.get_managed_cluster(name)
        if not hub._accepted(cluster):
            raise PermissionError("集群尚未被 Hub 接受，无法通过 cluster-proxy 读取资源")
        if name not in self.services:
            self._attach_service(name)
        return self.services[name]

    def load_demo_clusters(self) -> List[Dict[str, Any]]:
        names = hub.seed_demo()
        self._attach_all()
        return [self.get_cluster(n) for n in names if n in hub.managed_clusters]

    def fleet_overview(self) -> Dict[str, Any]:
        clusters = self.list_clusters()
        totals = {
            "clusters": len(clusters),
            "healthy": 0,
            "degraded": 0,
            "offline": 0,
            "demo": 0,
            "pending": 0,
            "nodes": 0,
            "nodes_ready": 0,
            "pods": 0,
            "deployments": 0,
            "services": 0,
        }
        cpu_alloc = cpu_req = mem_alloc = mem_req = gpu_cap = gpu_req = 0.0
        for item in clusters:
            health = (item.get("status") or {}).get("health")
            if health in totals:
                totals[health] += 1
            counts = item.get("counts") or {}
            resources = item.get("resources") or {}
            totals["nodes"] += counts.get("nodes") or 0
            totals["nodes_ready"] += counts.get("nodes_ready") or 0
            totals["pods"] += counts.get("pods") or 0
            totals["deployments"] += counts.get("deployments") or 0
            totals["services"] += counts.get("services") or 0
            cpu = resources.get("cpu") or {}
            mem = resources.get("memory") or {}
            gpu = resources.get("gpu") or {}
            cpu_alloc += cpu.get("allocatable") or 0
            cpu_req += cpu.get("requested") or 0
            mem_alloc += mem.get("allocatable") or 0
            mem_req += mem.get("requested") or 0
            gpu_cap += gpu.get("capacity") or 0
            gpu_req += gpu.get("requested") or 0
        info = hub.info()
        return {
            "hub": info,
            "totals": totals,
            "resources": {
                "cpu": {
                    "allocatable": cpu_alloc,
                    "requested": cpu_req,
                    "allocatable_text": format_cpu(cpu_alloc),
                    "requested_text": format_cpu(cpu_req),
                    "percent": _percent(cpu_req, cpu_alloc),
                },
                "memory": {
                    "allocatable": mem_alloc,
                    "requested": mem_req,
                    "allocatable_text": format_memory(int(mem_alloc)),
                    "requested_text": format_memory(int(mem_req)),
                    "percent": _percent(mem_req, mem_alloc),
                },
                "gpu": {
                    "capacity": gpu_cap,
                    "requested": gpu_req,
                    "percent": _percent(gpu_req, gpu_cap),
                },
            },
            "clusters": clusters,
        }


manager = ClusterManager()
