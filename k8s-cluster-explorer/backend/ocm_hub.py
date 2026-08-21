"""
CNCF Open Cluster Management (OCM) Hub 控制面。

实现 Hub-Spoke 核心对象，语义对齐上游 API：
- ManagedCluster + 双向 opt-in（hubAcceptsClient）
- 每个 spoke 在 Hub 上的 cluster namespace
- ClusterClaim 由 klusterlet 上报
- ManifestWork：Hub 写入处方，klusterlet pull/reconcile
- Placement / PlacementDecision：按 label / claim 选择集群

本地演示用 in-process klusterlet 模拟 pull；真实集群可用 kubeconfig 完成
clusteradm join 式接入。生产 OCM 中 Hub 不保存 spoke 凭据、由 agent pull。
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
HUB_FILE = os.environ.get("OCM_HUB_FILE") or os.path.join(DATA_DIR, "ocm-hub.json")
API_CLUSTER = "cluster.open-cluster-management.io/v1"
API_WORK = "work.open-cluster-management.io/v1"
API_PLACEMENT = "cluster.open-cluster-management.io/v1beta1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def cluster_dns_name(name: str) -> str:
    """ManagedCluster 名称需符合 DNS-1123 subdomain。"""
    text = (name or "").strip().lower().replace("_", "-").replace(" ", "-")
    text = re.sub(r"[^a-z0-9.-]", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-.")
    return text[:63] or f"cluster-{uuid.uuid4().hex[:8]}"


def _condition(ctype: str, status: str, reason: str, message: str = "") -> Dict[str, str]:
    return {
        "type": ctype,
        "status": status,
        "reason": reason,
        "message": message,
        "lastTransitionTime": _now(),
    }


def gpu_capacity(cluster: Dict[str, Any]) -> int:
    cap = (cluster.get("status") or {}).get("capacity") or {}
    try:
        return int(float(cap.get("nvidia.com/gpu") or 0))
    except (TypeError, ValueError):
        return 0


class OCMHub:
    """In-process ClusterManager + Placement + Work 控制器。"""

    def __init__(self) -> None:
        os.makedirs(os.path.dirname(HUB_FILE) or ".", exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)
        self.hub_name = "local-hub"
        self.managed_clusters: Dict[str, Dict[str, Any]] = {}
        self.manifest_works: Dict[str, Dict[str, Any]] = {}  # key: ns/name
        self.placements: Dict[str, Dict[str, Any]] = {}
        self._mtime = 0.0
        self._load_or_seed()

    def _touch_mtime(self) -> None:
        if os.path.isfile(HUB_FILE):
            self._mtime = os.path.getmtime(HUB_FILE)

    def _read_payload(self, payload: Dict[str, Any]) -> None:
        self.managed_clusters = {}
        self.manifest_works = {}
        self.placements = {}
        for item in payload.get("managedClusters", []):
            name = item["metadata"]["name"]
            self.managed_clusters[name] = item
        for item in payload.get("manifestWorks", []):
            key = f"{item['metadata']['namespace']}/{item['metadata']['name']}"
            self.manifest_works[key] = item
        for item in payload.get("placements", []):
            self.placements[item["metadata"]["name"]] = item

    def reload_if_changed(self) -> bool:
        """多进程共享同一份 ocm-hub.json 时，读之前同步磁盘。"""
        if not os.path.isfile(HUB_FILE):
            return False
        mtime = os.path.getmtime(HUB_FILE)
        if mtime <= self._mtime:
            return False
        try:
            with open(HUB_FILE, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self._read_payload(payload)
            self._mtime = mtime
            return True
        except Exception as exc:
            logger.warning("重新加载 OCM Hub 失败: %s", exc)
            return False

    def _load_or_seed(self) -> None:
        if os.path.isfile(HUB_FILE):
            try:
                with open(HUB_FILE, "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                self._read_payload(payload)
                self._touch_mtime()
                if self.managed_clusters:
                    logger.info("已加载 OCM Hub，ManagedCluster=%s", len(self.managed_clusters))
                    return
            except Exception as exc:
                logger.warning("读取 OCM Hub 状态失败: %s", exc)
        self.seed_demo()

    def _save(self) -> None:
        payload = {
            "hub": {"name": self.hub_name, "architecture": "hub-spoke"},
            "managedClusters": list(self.managed_clusters.values()),
            "manifestWorks": list(self.manifest_works.values()),
            "placements": list(self.placements.values()),
        }
        os.makedirs(os.path.dirname(HUB_FILE) or ".", exist_ok=True)
        with open(HUB_FILE, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        self._touch_mtime()

    def info(self) -> Dict[str, Any]:
        self.reload_if_changed()
        accepted = [c for c in self.managed_clusters.values() if self._accepted(c)]
        available = [c for c in accepted if self._available(c)]
        pending = [c for c in self.managed_clusters.values() if not self._accepted(c)]
        return {
            "hub": self.hub_name,
            "architecture": "hub-spoke",
            "project": "open-cluster-management",
            "modules": ["registration", "work", "placement"],
            "counts": {
                "managedClusters": len(self.managed_clusters),
                "accepted": len(accepted),
                "available": len(available),
                "pending": len(pending),
                "manifestWorks": len(self.manifest_works),
                "placements": len(self.placements),
            },
        }

    @staticmethod
    def _accepted(cluster: Dict[str, Any]) -> bool:
        return bool((cluster.get("spec") or {}).get("hubAcceptsClient"))

    @staticmethod
    def _available(cluster: Dict[str, Any]) -> bool:
        for cond in (cluster.get("status") or {}).get("conditions") or []:
            if cond.get("type") == "ManagedClusterAvailable" and cond.get("status") == "True":
                return True
        return False

    def list_managed_clusters(self) -> List[Dict[str, Any]]:
        self.reload_if_changed()
        return list(self.managed_clusters.values())

    def get_managed_cluster(self, name: str) -> Dict[str, Any]:
        if name not in self.managed_clusters:
            raise KeyError(name)
        return self.managed_clusters[name]

    def join(
        self,
        name: str,
        kubeconfig_path: Optional[str] = None,
        context: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        claims: Optional[List[Dict[str, str]]] = None,
        client_url: Optional[str] = None,
        source: str = "kubeconfig",
        mock_profile: Optional[str] = None,
        auto_accept: bool = False,
    ) -> Dict[str, Any]:
        """Klusterlet 侧发起注册：创建未接受的 ManagedCluster（模拟 CSR）。"""
        self.reload_if_changed()
        name = cluster_dns_name(name)
        if name in self.managed_clusters:
            raise ValueError(f"ManagedCluster {name} 已存在")
        labels = dict(labels or {})
        cluster = {
            "apiVersion": API_CLUSTER,
            "kind": "ManagedCluster",
            "metadata": {
                "name": name,
                "labels": labels,
                "creationTimestamp": _now(),
                "uid": uuid.uuid4().hex,
            },
            "spec": {
                "hubAcceptsClient": False,
                "leaseDurationSeconds": 60,
                "managedClusterClientConfigs": [{"url": client_url}] if client_url else [],
            },
            "status": {
                "conditions": [
                    _condition("HubAcceptedManagedCluster", "False", "Pending", "等待 Hub 管理员批准"),
                    _condition("ManagedClusterJoined", "False", "Pending", "尚未加入"),
                    _condition("ManagedClusterAvailable", "False", "Pending", "等待心跳"),
                ],
                "clusterClaims": claims or [],
                "version": {"kubernetes": "Unknown"},
                "capacity": {},
                "allocatable": {},
            },
            "_local": {
                "kubeconfig_path": kubeconfig_path,
                "context": context,
                "source": source,
                "mock_profile": mock_profile,
                "clusterNamespace": name,
                "csr": f"managedcluster-import-{name}-{uuid.uuid4().hex[:6]}",
            },
        }
        self.managed_clusters[name] = cluster
        self._save()
        if auto_accept:
            return self.accept(name)
        return cluster

    def accept(self, name: str) -> Dict[str, Any]:
        self.reload_if_changed()
        cluster = self.get_managed_cluster(name)
        cluster["spec"]["hubAcceptsClient"] = True
        cluster["status"]["conditions"] = [
            _condition("HubAcceptedManagedCluster", "True", "HubClusterAdminAccepted", "Hub 已接受该集群"),
            _condition("ManagedClusterJoined", "True", "ManagedClusterJoined", "Klusterlet 已加入"),
            _condition("ManagedClusterAvailable", "True", "ManagedClusterAvailable", "心跳正常"),
        ]
        cluster["_local"]["clusterNamespace"] = name
        self.managed_clusters[name] = cluster
        self._save()
        return cluster

    def deny(self, name: str) -> Dict[str, Any]:
        self.reload_if_changed()
        cluster = self.get_managed_cluster(name)
        cluster["spec"]["hubAcceptsClient"] = False
        cluster["status"]["conditions"] = [
            _condition("HubAcceptedManagedCluster", "False", "HubClusterAdminDenied", "Hub 拒绝接入"),
            _condition("ManagedClusterJoined", "False", "Denied", ""),
            _condition("ManagedClusterAvailable", "False", "Denied", ""),
        ]
        self._save()
        return cluster

    def delete(self, name: str) -> None:
        self.reload_if_changed()
        if name not in self.managed_clusters:
            raise KeyError(name)
        self.managed_clusters.pop(name)
        for key in [k for k in self.manifest_works if k.startswith(name + "/")]:
            self.manifest_works.pop(key, None)
        self._save()

    def update_heartbeat(self, name: str, claims: List[Dict[str, str]], version: str, capacity: Dict[str, Any]) -> None:
        self.reload_if_changed()
        cluster = self.get_managed_cluster(name)
        if not self._accepted(cluster):
            return
        cluster["status"]["clusterClaims"] = claims
        cluster["status"]["version"] = {"kubernetes": version}
        cluster["status"]["capacity"] = capacity
        cluster["status"]["allocatable"] = capacity
        cluster["status"]["conditions"] = [
            _condition("HubAcceptedManagedCluster", "True", "HubClusterAdminAccepted", ""),
            _condition("ManagedClusterJoined", "True", "ManagedClusterJoined", ""),
            _condition("ManagedClusterAvailable", "True", "ManagedClusterAvailable", "klusterlet lease refreshed"),
        ]
        labels = cluster["metadata"].setdefault("labels", {})
        for claim in claims:
            key = claim.get("name") or ""
            if key.endswith(".open-cluster-management.io") or key in ("region", "environment"):
                labels[key.split(".")[0] if "." in key else key] = str(claim.get("value") or "")
        self._save()

    def list_manifest_works(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        self.reload_if_changed()
        items = list(self.manifest_works.values())
        if namespace:
            items = [w for w in items if w["metadata"]["namespace"] == namespace]
        return items

    def create_manifest_work(self, cluster: str, name: str, manifests: List[Dict[str, Any]]) -> Dict[str, Any]:
        self.reload_if_changed()
        mc = self.get_managed_cluster(cluster)
        if not self._accepted(mc):
            raise ValueError("只能向已接受的 ManagedCluster 下发 ManifestWork")
        key = f"{cluster}/{name}"
        work = {
            "apiVersion": API_WORK,
            "kind": "ManifestWork",
            "metadata": {
                "name": name,
                "namespace": cluster,
                "creationTimestamp": _now(),
            },
            "spec": {"workload": {"manifests": manifests}},
            "status": {
                "conditions": [
                    _condition("Applied", "False", "Pending", "等待 klusterlet work-agent pull")
                ],
                "resourceStatus": {"manifests": []},
            },
        }
        self.manifest_works[key] = work
        self.reconcile_work(cluster, name)
        return work

    def delete_manifest_work(self, cluster: str, name: str) -> None:
        self.reload_if_changed()
        key = f"{cluster}/{name}"
        if key not in self.manifest_works:
            raise KeyError(key)
        self.manifest_works.pop(key)
        self._save()

    def reconcile_work(self, cluster: str, name: str) -> Dict[str, Any]:
        """模拟 spoke 上 work-agent 从 Hub namespace pull ManifestWork 并 Applied。"""
        self.reload_if_changed()
        key = f"{cluster}/{name}"
        work = self.manifest_works.get(key)
        if not work:
            raise KeyError(key)
        mc = self.get_managed_cluster(cluster)
        if not self._accepted(mc) or not self._available(mc):
            work["status"]["conditions"] = [
                _condition("Applied", "False", "ClusterUnavailable", "spoke 不可用，work-agent 无法 reconcile")
            ]
            self._save()
            return work
        resources = []
        for manifest in work["spec"]["workload"]["manifests"]:
            resources.append(
                {
                    "resourceMeta": {
                        "group": manifest.get("apiVersion", "").split("/")[0] if "/" in manifest.get("apiVersion", "") else "",
                        "version": (manifest.get("apiVersion") or "v1").split("/")[-1],
                        "kind": manifest.get("kind"),
                        "namespace": (manifest.get("metadata") or {}).get("namespace"),
                        "name": (manifest.get("metadata") or {}).get("name"),
                    },
                    "status": "Applied",
                }
            )
        work["status"] = {
            "conditions": [_condition("Applied", "True", "ManifestsApplied", "klusterlet work-agent 已应用到 spoke")],
            "resourceStatus": {"manifests": resources},
        }
        self._save()
        return work

    def list_placements(self) -> List[Dict[str, Any]]:
        self.reload_if_changed()
        return [self._with_decision(p) for p in self.placements.values()]

    def create_placement(
        self,
        name: str,
        match_labels: Optional[Dict[str, str]] = None,
        claim_equals: Optional[Dict[str, str]] = None,
        cluster_set: str = "default",
    ) -> Dict[str, Any]:
        self.reload_if_changed()
        placement = {
            "apiVersion": API_PLACEMENT,
            "kind": "Placement",
            "metadata": {"name": name, "namespace": "default", "creationTimestamp": _now()},
            "spec": {
                "clusterSets": [cluster_set],
                "predicates": [
                    {
                        "requiredClusterSelector": {
                            "labelSelector": {"matchLabels": match_labels or {}},
                            "claimSelector": {
                                "matchExpressions": [
                                    {"key": k, "operator": "In", "values": [v]} for k, v in (claim_equals or {}).items()
                                ]
                            },
                        }
                    }
                ],
            },
        }
        self.placements[name] = placement
        self._save()
        return self._with_decision(placement)

    def delete_placement(self, name: str) -> None:
        self.reload_if_changed()
        if name not in self.placements:
            raise KeyError(name)
        self.placements.pop(name)
        self._save()

    def _with_decision(self, placement: Dict[str, Any]) -> Dict[str, Any]:
        decisions = self.evaluate_placement(placement)
        return {
            **placement,
            "decision": {
                "apiVersion": API_PLACEMENT,
                "kind": "PlacementDecision",
                "metadata": {"name": f"{placement['metadata']['name']}-decision", "namespace": "default"},
                "status": {"decisions": decisions},
            },
        }

    def evaluate_placement(self, placement: Dict[str, Any]) -> List[Dict[str, str]]:
        pred = ((placement.get("spec") or {}).get("predicates") or [{}])[0]
        selector = (pred.get("requiredClusterSelector") or {})
        labels = ((selector.get("labelSelector") or {}).get("matchLabels")) or {}
        claims = ((selector.get("claimSelector") or {}).get("matchExpressions")) or []
        matched = []
        for cluster in self.managed_clusters.values():
            if not self._accepted(cluster) or not self._available(cluster):
                continue
            clabels = cluster["metadata"].get("labels") or {}
            if any(clabels.get(k) != v for k, v in labels.items()):
                continue
            reported = {c["name"]: str(c.get("value")) for c in (cluster.get("status") or {}).get("clusterClaims") or []}
            ok = True
            for expr in claims:
                actual = reported.get(expr["key"], clabels.get(expr["key"].split(".")[0], ""))
                if expr.get("operator") == "In" and actual not in (expr.get("values") or []):
                    ok = False
                    break
            if ok:
                matched.append({"clusterName": cluster["metadata"]["name"], "reason": ""})
        return matched

    def seed_demo(self) -> List[str]:
        self.reload_if_changed()
        created = []
        demos = [
            {
                "name": "prod-cn-shanghai",
                "labels": {"environment": "production", "region": "cn-shanghai", "vendor": "ocm"},
                "claims": [
                    {"name": "id.k8s.io", "value": "prod-cn-shanghai"},
                    {"name": "region.open-cluster-management.io", "value": "cn-shanghai"},
                    {"name": "platform.open-cluster-management.io", "value": "OpenStack"},
                    {"name": "gpu.open-cluster-management.io", "value": "true"},
                ],
                "url": "https://k8s.prod.internal:6443",
                "profile": "prod",
                "version": "v1.29.4",
                "capacity": {"cpu": "36", "memory": "136Gi", "nvidia.com/gpu": "8"},
            },
            {
                "name": "staging-cn-shanghai",
                "labels": {"environment": "staging", "region": "cn-shanghai", "vendor": "ocm"},
                "claims": [
                    {"name": "id.k8s.io", "value": "staging-cn-shanghai"},
                    {"name": "region.open-cluster-management.io", "value": "cn-shanghai"},
                    {"name": "platform.open-cluster-management.io", "value": "OpenStack"},
                    {"name": "gpu.open-cluster-management.io", "value": "true"},
                ],
                "url": "https://k8s.staging.internal:6443",
                "profile": "staging",
                "version": "v1.28.9",
                "capacity": {"cpu": "12", "memory": "40Gi", "nvidia.com/gpu": "2"},
            },
            {
                "name": "edge-us-west",
                "labels": {"environment": "edge", "region": "us-west-1", "vendor": "ocm"},
                "claims": [
                    {"name": "id.k8s.io", "value": "edge-us-west"},
                    {"name": "region.open-cluster-management.io", "value": "us-west-1"},
                    {"name": "platform.open-cluster-management.io", "value": "BareMetal"},
                    {"name": "gpu.open-cluster-management.io", "value": "true"},
                ],
                "url": "https://k8s.edge.internal:6443",
                "profile": "edge",
                "version": "v1.27.12",
                "capacity": {"cpu": "16", "memory": "32Gi", "nvidia.com/gpu": "1"},
            },
        ]
        for item in demos:
            if item["name"] not in self.managed_clusters:
                self.join(
                    name=item["name"],
                    labels=item["labels"],
                    claims=item["claims"],
                    client_url=item["url"],
                    source="demo",
                    mock_profile=item["profile"],
                    auto_accept=True,
                )
                created.append(item["name"])
            if self._accepted(self.managed_clusters[item["name"]]):
                self.update_heartbeat(item["name"], item["claims"], item["version"], item["capacity"])
        if "kind-dev" not in self.managed_clusters:
            self.join(
                name="kind-dev",
                labels={"environment": "development", "region": "local", "vendor": "ocm"},
                claims=[{"name": "id.k8s.io", "value": "kind-dev"}],
                client_url="https://127.0.0.1:6443",
                source="demo",
                mock_profile="staging",
                auto_accept=False,
            )
            created.append("kind-dev")
        if "gpu-inference" not in self.placements:
            self.create_placement(
                "gpu-inference",
                match_labels={},
                claim_equals={"gpu.open-cluster-management.io": "true"},
            )
        if "prod-only" not in self.placements:
            self.create_placement("prod-only", match_labels={"environment": "production"})
        nginx = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "demo-nginx", "namespace": "default"},
            "spec": {"replicas": 1, "selector": {"matchLabels": {"app": "nginx"}}},
        }
        if "prod-cn-shanghai/demo-nginx" not in self.manifest_works:
            self.create_manifest_work("prod-cn-shanghai", "demo-nginx", [nginx])
        self._save()
        return created


hub = OCMHub()
