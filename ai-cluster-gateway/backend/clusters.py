"""
推理集群 = 与 k8s-cluster-explorer 共享的 OCM ManagedCluster。

Hub 状态文件：k8s-cluster-explorer/data/ocm-hub.json
kubeconfig 仅用于 join bootstrap，以及已接受集群上的真实 Deployment 下发。
"""
from __future__ import annotations

import logging
import os
import sys
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
KUBECONFIG_DIR = os.path.join(DATA_DIR, "kubeconfigs")
EXPLORER_BACKEND = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "k8s-cluster-explorer", "backend")
)
EXPLORER_HUB = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "k8s-cluster-explorer", "data", "ocm-hub.json")
)

os.environ.setdefault("OCM_HUB_FILE", EXPLORER_HUB)
if EXPLORER_BACKEND not in sys.path:
    sys.path.insert(0, EXPLORER_BACKEND)

from ocm_hub import cluster_dns_name, gpu_capacity, hub  # noqa: E402


def list_kube_contexts(kubeconfig_path: str) -> Dict[str, Any]:
    path = os.path.expanduser(kubeconfig_path)
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"kubeconfig 不存在: {path}")
    from kubernetes import config

    contexts, active = config.list_kube_config_contexts(config_file=path)
    active_name = (active or {}).get("name")
    items = []
    for item in contexts or []:
        ctx = item.get("context") or {}
        items.append(
            {
                "name": item.get("name"),
                "cluster": ctx.get("cluster"),
                "user": ctx.get("user"),
                "namespace": ctx.get("namespace") or "default",
                "current": item.get("name") == active_name,
            }
        )
    return {"path": path, "contexts": items, "current": active_name}


def _health(cluster: Dict[str, Any], probe: Optional[str] = None) -> str:
    if not hub._accepted(cluster):
        return "pending"
    local = cluster.get("_local") or {}
    if local.get("source") == "demo":
        return "demo"
    return probe or "offline"


class ClusterRegistry:
    """OCM ManagedCluster 上的推理集群视图。"""

    def __init__(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(KUBECONFIG_DIR, exist_ok=True)
        self._clients: Dict[str, Any] = {}
        hub.seed_demo()

    def view(self, cluster: Dict[str, Any], probe: Optional[str] = None, error: Optional[str] = None) -> Dict[str, Any]:
        name = cluster["metadata"]["name"]
        labels = cluster.get("metadata", {}).get("labels") or {}
        local = cluster.get("_local") or {}
        spec = cluster.get("spec") or {}
        status = cluster.get("status") or {}
        health = _health(cluster, probe)
        return {
            "id": name,
            "name": name,
            "kind": "ManagedCluster",
            "environment": labels.get("environment") or "production",
            "region": labels.get("region") or "",
            "labels": labels,
            "gpu_total": gpu_capacity(cluster),
            "source": local.get("source") or "ocm",
            "kubeconfig_path": local.get("kubeconfig_path"),
            "context": local.get("context"),
            "server": ((spec.get("managedClusterClientConfigs") or [{}])[0] or {}).get("url"),
            "status": health,
            "error": error,
            "hubAcceptsClient": bool(spec.get("hubAcceptsClient")),
            "clusterNamespace": local.get("clusterNamespace") or name,
            "csr": local.get("csr"),
            "conditions": status.get("conditions") or [],
            "clusterClaims": status.get("clusterClaims") or [],
            "capacity": status.get("capacity") or {},
            "joined": any(c.get("type") == "ManagedClusterJoined" and c.get("status") == "True" for c in status.get("conditions") or []),
            "available": any(c.get("type") == "ManagedClusterAvailable" and c.get("status") == "True" for c in status.get("conditions") or []),
        }

    def list(self) -> List[Dict[str, Any]]:
        return [self.view(item) for item in hub.list_managed_clusters()]

    def get(self, cluster_id: str) -> Dict[str, Any]:
        hub.reload_if_changed()
        return self.view(hub.get_managed_cluster(cluster_id))

    def raw(self, cluster_id: str) -> Dict[str, Any]:
        hub.reload_if_changed()
        return hub.get_managed_cluster(cluster_id)

    def accepted(self, cluster_id: str) -> bool:
        return hub._accepted(self.raw(cluster_id))

    def join(
        self,
        name: str,
        kubeconfig_path: str,
        context: Optional[str] = None,
        environment: str = "production",
        region: str = "",
        gpu_total: int = 0,
        auto_accept: bool = False,
    ) -> Dict[str, Any]:
        path = os.path.expanduser(kubeconfig_path)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"kubeconfig 不存在: {path}")
        from kubernetes import client, config

        api_client = config.new_client_from_config(config_file=path, context=context)
        core = client.CoreV1Api(api_client)
        core.list_namespace(_request_timeout=8)
        gpu_count = gpu_total
        if not gpu_count:
            gpu_count = 0
            for node in core.list_node(_request_timeout=10).items:
                cap = (node.status.capacity or {}) if node.status else {}
                gpu_count += int(float(cap.get("nvidia.com/gpu") or 0))
        ctx = context
        if not ctx:
            _, active = config.list_kube_config_contexts(config_file=path)
            ctx = (active or {}).get("name")
        display = cluster_dns_name(name or ctx or os.path.basename(path))
        labels = {"environment": environment or "production", "region": region or ""}
        claims = [
            {"name": "id.k8s.io", "value": display},
            {"name": "region.open-cluster-management.io", "value": region or ""},
            {"name": "gpu.open-cluster-management.io", "value": "true" if gpu_count else "false"},
        ]
        cluster = hub.join(
            name=display,
            kubeconfig_path=path,
            context=ctx,
            labels=labels,
            claims=claims,
            source="kubeconfig",
            auto_accept=auto_accept,
        )
        joined = cluster["metadata"]["name"]
        self._clients[joined] = api_client
        if hub._accepted(cluster):
            hub.update_heartbeat(
                joined,
                claims,
                "Unknown",
                {"nvidia.com/gpu": str(gpu_count)} if gpu_count else {},
            )
        else:
            cluster["_local"]["pending_gpu"] = gpu_count
            hub._save()
        return self.get(joined)

    def register(self, **kwargs: Any) -> Dict[str, Any]:
        kwargs.setdefault("auto_accept", False)
        return self.join(**kwargs)

    def import_kubeconfig(
        self,
        kubeconfig_path: str,
        environment: str = "production",
        region: str = "",
        auto_accept: bool = False,
    ) -> List[Dict[str, Any]]:
        info = list_kube_contexts(kubeconfig_path)
        path = info["path"]
        created = []
        existing = set(hub.managed_clusters)
        for ctx in info.get("contexts", []):
            if cluster_dns_name(ctx["name"]) in existing:
                continue
            created.append(
                self.join(
                    name=ctx["name"],
                    kubeconfig_path=path,
                    context=ctx["name"],
                    environment=environment,
                    region=region,
                    auto_accept=auto_accept,
                )
            )
        return created

    def register_from_content(
        self,
        content: str,
        name: str = "",
        context: Optional[str] = None,
        environment: str = "production",
        region: str = "",
        import_all: bool = False,
        gpu_total: int = 0,
        auto_accept: bool = False,
    ) -> List[Dict[str, Any]]:
        token = uuid.uuid4().hex[:10]
        path = os.path.join(KUBECONFIG_DIR, f"{token}.yaml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        if import_all:
            return self.import_kubeconfig(path, environment, region, auto_accept=auto_accept)
        return [
            self.join(
                name=name,
                kubeconfig_path=path,
                context=context,
                environment=environment,
                region=region,
                gpu_total=gpu_total,
                auto_accept=auto_accept,
            )
        ]

    def accept(self, name: str) -> Dict[str, Any]:
        cluster = hub.accept(name)
        local = cluster.get("_local") or {}
        gpu = int(local.get("pending_gpu") or gpu_capacity(cluster) or 0)
        claims = (cluster.get("status") or {}).get("clusterClaims") or []
        if gpu:
            hub.update_heartbeat(name, claims, ((cluster.get("status") or {}).get("version") or {}).get("kubernetes") or "Unknown", {"nvidia.com/gpu": str(gpu)})
        return self.get(name)

    def deny(self, name: str) -> Dict[str, Any]:
        hub.deny(name)
        client = self._clients.pop(name, None)
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        return self.get(name)

    def update(self, cluster_id: str, **fields: Any) -> Dict[str, Any]:
        cluster = self.raw(cluster_id)
        labels = cluster["metadata"].setdefault("labels", {})
        if fields.get("environment") is not None:
            labels["environment"] = fields["environment"]
        if fields.get("region") is not None:
            labels["region"] = fields["region"]
        if fields.get("gpu_total") is not None:
            cap = cluster.setdefault("status", {}).setdefault("capacity", {})
            cap["nvidia.com/gpu"] = str(int(fields["gpu_total"]))
            claims = cluster.setdefault("status", {}).setdefault("clusterClaims", [])
            found = False
            for claim in claims:
                if claim.get("name") == "gpu.open-cluster-management.io":
                    claim["value"] = "true" if int(fields["gpu_total"]) else "false"
                    found = True
            if not found:
                claims.append({"name": "gpu.open-cluster-management.io", "value": "true" if int(fields["gpu_total"]) else "false"})
        hub._save()
        return self.get(cluster_id)

    def delete(self, cluster_id: str) -> Dict[str, Any]:
        record = self.get(cluster_id)
        local = self.raw(cluster_id).get("_local") or {}
        client = self._clients.pop(cluster_id, None)
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        path = local.get("kubeconfig_path") or ""
        if local.get("source") != "demo" and path.startswith(KUBECONFIG_DIR) and os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass
        hub.delete(cluster_id)
        return record

    def refresh(self, cluster_id: str) -> Dict[str, Any]:
        cluster = self.raw(cluster_id)
        if not hub._accepted(cluster):
            return self.view(cluster)
        local = cluster.get("_local") or {}
        if local.get("source") == "demo":
            return self.view(cluster, probe="demo")
        try:
            from kubernetes import client, config

            api_client = config.new_client_from_config(
                config_file=local["kubeconfig_path"],
                context=local.get("context"),
            )
            core = client.CoreV1Api(api_client)
            core.list_namespace(_request_timeout=8)
            gpu_count = 0
            for node in core.list_node(_request_timeout=10).items:
                cap = (node.status.capacity or {}) if node.status else {}
                gpu_count += int(float(cap.get("nvidia.com/gpu") or 0))
            self._clients[cluster_id] = api_client
            labels = cluster.get("metadata", {}).get("labels") or {}
            claims = [
                {"name": "id.k8s.io", "value": cluster_id},
                {"name": "region.open-cluster-management.io", "value": labels.get("region", "")},
                {"name": "gpu.open-cluster-management.io", "value": "true" if gpu_count else "false"},
            ]
            cap = dict((cluster.get("status") or {}).get("capacity") or {})
            if gpu_count:
                cap["nvidia.com/gpu"] = str(gpu_count)
            hub.update_heartbeat(cluster_id, claims, "Unknown", cap)
            return self.view(hub.get_managed_cluster(cluster_id), probe="healthy")
        except Exception as exc:
            logger.warning("刷新 ManagedCluster %s 失败: %s", cluster_id, exc)
            return self.view(cluster, probe="offline", error=str(exc))

    def seed_demo(self) -> List[Dict[str, Any]]:
        names = hub.seed_demo()
        return [self.get(n) for n in names if n in hub.managed_clusters]

    def k8s_apps(self, cluster_id: str):
        cluster = self.raw(cluster_id)
        if not hub._accepted(cluster):
            raise PermissionError("集群尚未被 Hub 接受，无法下发 ManifestWork")
        local = cluster.get("_local") or {}
        if local.get("source") == "demo":
            return None
        from kubernetes import client, config

        if cluster_id not in self._clients:
            self._clients[cluster_id] = config.new_client_from_config(
                config_file=local["kubeconfig_path"],
                context=local.get("context"),
            )
        return client.AppsV1Api(self._clients[cluster_id]), client.CoreV1Api(self._clients[cluster_id])


clusters = ClusterRegistry()
