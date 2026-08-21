"""
单集群 Kubernetes 资源采集服务。

每个集群实例使用独立 ApiClient，避免多集群共用全局 kubeconfig。
真实集群连不上时标记为 offline，不会用模拟数据冒充。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_KUBECONFIG = os.environ.get("KUBECONFIG") or os.path.expanduser("~/.kube/config")


def parse_cpu(value: Optional[str]) -> float:
    if value is None or value == "":
        return 0.0
    text = str(value).strip()
    try:
        if text.endswith("n"):
            return int(text[:-1]) / 1_000_000_000
        if text.endswith("u"):
            return int(text[:-1]) / 1_000_000
        if text.endswith("m"):
            return int(text[:-1]) / 1000
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def parse_memory_bytes(value: Optional[str]) -> int:
    if value is None or value == "":
        return 0
    text = str(value).strip()
    multipliers = (
        ("Ki", 1024),
        ("Mi", 1024**2),
        ("Gi", 1024**3),
        ("Ti", 1024**4),
        ("Pi", 1024**5),
        ("Ei", 1024**6),
        ("k", 1000),
        ("K", 1000),
        ("M", 1000**2),
        ("G", 1000**3),
        ("T", 1000**4),
        ("P", 1000**5),
        ("E", 1000**6),
    )
    try:
        for suffix, factor in multipliers:
            if text.endswith(suffix):
                return int(float(text[: -len(suffix)]) * factor)
        return int(float(text))
    except (TypeError, ValueError):
        return 0


def format_cpu(cores: float) -> str:
    if cores >= 10:
        return f"{cores:.1f}"
    return f"{cores:.2f}"


def format_memory(num_bytes: int) -> str:
    if num_bytes <= 0:
        return "0 B"
    units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")
    value = float(num_bytes)
    idx = 0
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    if idx == 0:
        return f"{int(value)} {units[idx]}"
    return f"{value:.1f} {units[idx]}"


def format_age(timestamp) -> str:
    if not timestamp:
        return "-"
    if hasattr(timestamp, "timestamp"):
        created = timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp
        now = datetime.now(timezone.utc)
        seconds = int((now - created).total_seconds())
    else:
        return str(timestamp)
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def _quantity_map(resource_dict) -> Dict[str, str]:
    if not resource_dict:
        return {}
    return {k: str(v) for k, v in dict(resource_dict).items()}


def _percent(used: float, total: float) -> float:
    if not total:
        return 0.0
    return round(min(100.0, max(0.0, (used / total) * 100.0)), 1)


def list_kube_contexts(kubeconfig_path: Optional[str] = None) -> Dict[str, Any]:
    path = os.path.expanduser(kubeconfig_path or DEFAULT_KUBECONFIG)
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


def read_cluster_server(kubeconfig_path: str, context_name: Optional[str]) -> Dict[str, Optional[str]]:
    import yaml

    with open(kubeconfig_path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    cluster_name = None
    for ctx in raw.get("contexts", []):
        if ctx.get("name") == context_name:
            cluster_name = (ctx.get("context") or {}).get("cluster")
            break
    if not cluster_name and raw.get("contexts"):
        cluster_name = (raw["contexts"][0].get("context") or {}).get("cluster")
    server = None
    for cluster in raw.get("clusters", []):
        if cluster.get("name") == cluster_name:
            server = (cluster.get("cluster") or {}).get("server")
            break
    return {"cluster": cluster_name, "server": server}


class K8sClusterService:
    """单个集群的连接与资源采集。"""

    def __init__(self, mock_profile: Optional[str] = None) -> None:
        self.mode = "offline"
        self.mock_profile = mock_profile
        self.kubeconfig_path: Optional[str] = None
        self.current_context: Optional[str] = None
        self.cluster_name: Optional[str] = None
        self.server: Optional[str] = None
        self.k8s_version: Optional[str] = None
        self.platform: Optional[str] = None
        self.error: Optional[str] = None
        self._api_client = None
        self._core = None
        self._apps = None
        self._custom = None
        self._version_api = None
        if mock_profile:
            self.use_mock(mock_profile)

    def use_mock(self, profile: str = "prod") -> Dict[str, Any]:
        meta = MOCK_PROFILES.get(profile) or MOCK_PROFILES["prod"]
        self.mode = "demo"
        self.mock_profile = profile
        self.error = None
        self._close_client()
        self.k8s_version = meta["version"]
        self.platform = "linux/amd64"
        self.cluster_name = meta["cluster"]
        self.server = meta["server"]
        self.current_context = meta["context"]
        self.kubeconfig_path = f"(demo:{profile})"
        return self.get_status()

    def mark_offline(self, reason: str) -> Dict[str, Any]:
        self.mode = "offline"
        self.error = reason
        self._close_client()
        return self.get_status()

    def _close_client(self) -> None:
        if self._api_client is not None:
            try:
                self._api_client.close()
            except Exception:
                pass
        self._api_client = None
        self._core = None
        self._apps = None
        self._custom = None
        self._version_api = None

    def connect(self, kubeconfig_path: str, context: Optional[str] = None) -> Dict[str, Any]:
        path = os.path.expanduser(kubeconfig_path)
        if not os.path.isfile(path):
            return {**self.mark_offline(f"kubeconfig 不存在: {path}"), "ok": False}

        try:
            from kubernetes import client, config

            api_client = config.new_client_from_config(config_file=path, context=context)
            self._close_client()
            self._api_client = api_client
            self._core = client.CoreV1Api(api_client)
            self._apps = client.AppsV1Api(api_client)
            self._custom = client.CustomObjectsApi(api_client)
            self._version_api = client.VersionApi(api_client)
            self.kubeconfig_path = path
            self.mode = "kubeconfig"
            self.mock_profile = None
            self.error = None

            ctx_info = list_kube_contexts(path)
            self.current_context = context or ctx_info.get("current")
            identity = read_cluster_server(path, self.current_context)
            self.cluster_name = identity.get("cluster")
            self.server = identity.get("server")

            self._core.list_namespace(_request_timeout=8)
            self._refresh_cluster_identity()
            logger.info("已连接集群: path=%s context=%s", path, self.current_context)
            return {"ok": True, **self.get_status()}
        except Exception as exc:
            logger.warning("连接集群失败: %s", exc)
            return {**self.mark_offline(str(exc)), "ok": False, "error": str(exc)}

    def _refresh_cluster_identity(self) -> None:
        try:
            info = self._version_api.get_code()
            self.k8s_version = getattr(info, "git_version", None)
            self.platform = getattr(info, "platform", None)
        except Exception as exc:
            logger.warning("获取集群版本失败: %s", exc)

    def health(self) -> str:
        if self.mode == "demo":
            return "demo"
        if self.mode != "kubeconfig" or self._core is None:
            return "offline"
        try:
            nodes = self.get_nodes()
            if nodes and any(not n["ready"] for n in nodes):
                return "degraded"
            return "healthy"
        except Exception:
            return "degraded"

    def get_status(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "connected": self.mode in ("kubeconfig", "in_cluster"),
            "health": self.health() if self.mode != "kubeconfig" else self._cached_or_live_health(),
            "kubeconfig_path": self.kubeconfig_path,
            "context": self.current_context,
            "cluster": self.cluster_name,
            "server": self.server,
            "version": self.k8s_version,
            "platform": self.platform,
            "error": self.error,
        }

    def _cached_or_live_health(self) -> str:
        if self.mode == "demo":
            return "demo"
        if self.mode != "kubeconfig" or self._core is None:
            return "offline"
        return "healthy"

    def get_overview(self) -> Dict[str, Any]:
        if self.mode == "demo":
            return self._mock_overview()
        if self.mode == "offline" or self._core is None:
            return self._empty_overview()

        nodes = self.get_nodes()
        namespaces = self.get_namespaces()
        pods = self.get_pods()
        workloads = self.get_workloads()
        services = self.get_services()
        return self._build_overview(nodes, namespaces, pods, workloads, services)

    def get_nodes(self) -> List[Dict[str, Any]]:
        if self.mode == "demo":
            return self._mock_nodes()
        if self.mode == "offline" or self._core is None:
            return []

        pods = self._core.list_pod_for_all_namespaces(_request_timeout=15).items
        usage_by_node = self._pod_usage_by_node(pods)
        metrics_by_node = self._node_metrics()

        result = []
        for node in self._core.list_node(_request_timeout=15).items:
            meta = node.metadata
            status = node.status
            labels = meta.labels or {}
            capacity = _quantity_map(status.capacity)
            allocatable = _quantity_map(status.allocatable)
            conditions = {c.type: c.status for c in (status.conditions or [])}
            addresses = {a.type: a.address for a in (status.addresses or [])}
            roles = self._node_roles(labels)
            usage = usage_by_node.get(meta.name, {"cpu": 0.0, "memory": 0, "gpu": 0, "pods": 0})
            metrics = metrics_by_node.get(meta.name, {})
            cpu_alloc = parse_cpu(allocatable.get("cpu"))
            mem_alloc = parse_memory_bytes(allocatable.get("memory"))
            gpu_cap = int(float(capacity.get("nvidia.com/gpu") or 0))
            result.append(
                {
                    "name": meta.name,
                    "roles": roles,
                    "ready": conditions.get("Ready") == "True",
                    "unschedulable": bool(getattr(node.spec, "unschedulable", False)),
                    "kubelet_version": getattr(status.node_info, "kubelet_version", None) if status.node_info else None,
                    "os_image": getattr(status.node_info, "os_image", None) if status.node_info else None,
                    "container_runtime": getattr(status.node_info, "container_runtime_version", None)
                    if status.node_info
                    else None,
                    "internal_ip": addresses.get("InternalIP"),
                    "external_ip": addresses.get("ExternalIP"),
                    "cpu_capacity": parse_cpu(capacity.get("cpu")),
                    "cpu_allocatable": cpu_alloc,
                    "cpu_requested": usage["cpu"],
                    "cpu_usage": metrics.get("cpu"),
                    "memory_capacity": parse_memory_bytes(capacity.get("memory")),
                    "memory_allocatable": mem_alloc,
                    "memory_requested": usage["memory"],
                    "memory_usage": metrics.get("memory"),
                    "gpu_capacity": gpu_cap,
                    "gpu_requested": usage["gpu"],
                    "pods": usage["pods"],
                    "pod_capacity": int(float(allocatable.get("pods") or 0)),
                    "cpu_percent": _percent(usage["cpu"], cpu_alloc),
                    "memory_percent": _percent(usage["memory"], mem_alloc),
                    "age": format_age(meta.creation_timestamp),
                    "conditions": conditions,
                }
            )
        result.sort(key=lambda item: (0 if "control-plane" in item["roles"] or "master" in item["roles"] else 1, item["name"]))
        return result

    def get_namespaces(self) -> List[Dict[str, Any]]:
        if self.mode == "demo":
            return self._mock_namespaces()
        if self.mode == "offline" or self._core is None:
            return []
        items = []
        for ns in self._core.list_namespace(_request_timeout=15).items:
            items.append(
                {
                    "name": ns.metadata.name,
                    "status": getattr(ns.status, "phase", None),
                    "age": format_age(ns.metadata.creation_timestamp),
                    "labels": ns.metadata.labels or {},
                }
            )
        return items

    def get_pods(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.mode == "demo":
            pods = self._mock_pods()
            if namespace:
                return [p for p in pods if p["namespace"] == namespace]
            return pods
        if self.mode == "offline" or self._core is None:
            return []

        if namespace:
            items = self._core.list_namespaced_pod(namespace, _request_timeout=15).items
        else:
            items = self._core.list_pod_for_all_namespaces(_request_timeout=20).items

        result = []
        for pod in items:
            cpu_req, mem_req, gpu_req, cpu_lim, mem_lim = self._container_resources(pod)
            restarts = 0
            ready_count = 0
            total = len(pod.spec.containers or [])
            phase = pod.status.phase
            if pod.status.container_statuses:
                for cs in pod.status.container_statuses:
                    restarts += cs.restart_count or 0
                    if cs.ready:
                        ready_count += 1
                    waiting = getattr(cs.state, "waiting", None)
                    if waiting and waiting.reason in ("CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull"):
                        phase = waiting.reason
            result.append(
                {
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "node": pod.spec.node_name,
                    "phase": phase,
                    "ready": f"{ready_count}/{total}",
                    "restarts": restarts,
                    "qos": getattr(pod.status, "qos_class", None),
                    "ip": pod.status.pod_ip,
                    "cpu_request": cpu_req,
                    "memory_request": mem_req,
                    "cpu_limit": cpu_lim,
                    "memory_limit": mem_lim,
                    "gpu_request": gpu_req,
                    "cpu_request_text": format_cpu(cpu_req),
                    "memory_request_text": format_memory(mem_req),
                    "age": format_age(pod.metadata.creation_timestamp),
                    "controlled_by": self._owner_kind(pod),
                }
            )
        result.sort(key=lambda p: (p["namespace"], p["name"]))
        return result

    def get_workloads(self, namespace: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        if self.mode == "demo":
            data = self._mock_workloads()
            if namespace:
                return {k: [x for x in v if x["namespace"] == namespace] for k, v in data.items()}
            return data
        if self.mode == "offline" or self._apps is None:
            return {"deployments": [], "statefulsets": [], "daemonsets": []}

        def collect(list_all, list_ns, kind: str) -> List[Dict[str, Any]]:
            items = list_ns(namespace, _request_timeout=15).items if namespace else list_all(_request_timeout=15).items
            rows = []
            for item in items:
                spec = item.spec
                status = item.status
                replicas = getattr(spec, "replicas", None)
                ready = getattr(status, "ready_replicas", None) or getattr(status, "number_ready", None)
                desired = replicas
                if kind == "DaemonSet":
                    desired = getattr(status, "desired_number_scheduled", None)
                    ready = getattr(status, "number_ready", None)
                rows.append(
                    {
                        "kind": kind,
                        "name": item.metadata.name,
                        "namespace": item.metadata.namespace,
                        "desired": desired or 0,
                        "ready": ready or 0,
                        "updated": getattr(status, "updated_replicas", None)
                        or getattr(status, "updated_number_scheduled", None),
                        "available": getattr(status, "available_replicas", None)
                        or getattr(status, "number_available", None),
                        "age": format_age(item.metadata.creation_timestamp),
                    }
                )
            return rows

        return {
            "deployments": collect(self._apps.list_deployment_for_all_namespaces, self._apps.list_namespaced_deployment, "Deployment"),
            "statefulsets": collect(self._apps.list_stateful_set_for_all_namespaces, self._apps.list_namespaced_stateful_set, "StatefulSet"),
            "daemonsets": collect(self._apps.list_daemon_set_for_all_namespaces, self._apps.list_namespaced_daemon_set, "DaemonSet"),
        }

    def get_services(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.mode == "demo":
            items = self._mock_services()
            if namespace:
                return [s for s in items if s["namespace"] == namespace]
            return items
        if self.mode == "offline" or self._core is None:
            return []

        raw = (
            self._core.list_namespaced_service(namespace, _request_timeout=15).items
            if namespace
            else self._core.list_service_for_all_namespaces(_request_timeout=15).items
        )
        result = []
        for svc in raw:
            ports = []
            for port in svc.spec.ports or []:
                ports.append(f"{port.port}/{port.protocol}" + (f":{port.node_port}" if port.node_port else ""))
            result.append(
                {
                    "name": svc.metadata.name,
                    "namespace": svc.metadata.namespace,
                    "type": svc.spec.type,
                    "cluster_ip": svc.spec.cluster_ip,
                    "external_ip": ",".join(svc.spec.external_i_ps or []) if svc.spec.external_i_ps else None,
                    "ports": ", ".join(ports),
                    "age": format_age(svc.metadata.creation_timestamp),
                }
            )
        result.sort(key=lambda s: (s["namespace"], s["name"]))
        return result

    def get_events(self, namespace: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if self.mode == "demo":
            items = self._mock_events()
            if namespace:
                items = [e for e in items if e["namespace"] == namespace]
            return items[:limit]
        if self.mode == "offline" or self._core is None:
            return []

        raw = (
            self._core.list_namespaced_event(namespace, _request_timeout=15).items
            if namespace
            else self._core.list_event_for_all_namespaces(_request_timeout=20).items
        )
        rows = []
        for event in raw:
            last = event.last_timestamp or event.event_time or event.metadata.creation_timestamp
            rows.append(
                {
                    "type": event.type,
                    "reason": event.reason,
                    "message": event.message,
                    "namespace": event.metadata.namespace,
                    "object": f"{getattr(event.involved_object, 'kind', '')}/{getattr(event.involved_object, 'name', '')}",
                    "count": event.count or 1,
                    "age": format_age(last),
                    "timestamp": last.isoformat() if last and hasattr(last, "isoformat") else str(last),
                }
            )
        rows.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
        return rows[:limit]

    def _pod_usage_by_node(self, pods) -> Dict[str, Dict[str, Any]]:
        usage: Dict[str, Dict[str, Any]] = {}
        for pod in pods:
            if pod.status.phase in ("Succeeded", "Failed"):
                continue
            node = pod.spec.node_name or "unscheduled"
            bucket = usage.setdefault(node, {"cpu": 0.0, "memory": 0, "gpu": 0, "pods": 0})
            cpu, mem, gpu, _, _ = self._container_resources(pod)
            bucket["cpu"] += cpu
            bucket["memory"] += mem
            bucket["gpu"] += gpu
            bucket["pods"] += 1
        return usage

    def _container_resources(self, pod) -> tuple:
        cpu_req = mem_req = gpu_req = cpu_lim = mem_lim = 0
        for container in pod.spec.containers or []:
            resources = container.resources
            if not resources:
                continue
            requests = _quantity_map(resources.requests)
            limits = _quantity_map(resources.limits)
            cpu_req += parse_cpu(requests.get("cpu"))
            mem_req += parse_memory_bytes(requests.get("memory"))
            gpu_req += int(float(requests.get("nvidia.com/gpu") or limits.get("nvidia.com/gpu") or 0))
            cpu_lim += parse_cpu(limits.get("cpu"))
            mem_lim += parse_memory_bytes(limits.get("memory"))
        return cpu_req, mem_req, gpu_req, cpu_lim, mem_lim

    def _node_metrics(self) -> Dict[str, Dict[str, Any]]:
        if self._custom is None:
            return {}
        try:
            data = self._custom.list_cluster_custom_object("metrics.k8s.io", "v1beta1", "nodes")
            result = {}
            for item in data.get("items", []):
                name = item.get("metadata", {}).get("name")
                usage = item.get("usage") or {}
                result[name] = {
                    "cpu": parse_cpu(usage.get("cpu")),
                    "memory": parse_memory_bytes(usage.get("memory")),
                }
            return result
        except Exception:
            return {}

    @staticmethod
    def _node_roles(labels: Dict[str, str]) -> List[str]:
        roles = []
        for key in labels:
            if key.startswith("node-role.kubernetes.io/"):
                role = key.split("/", 1)[-1] or "node"
                roles.append(role)
        if labels.get("node.kubernetes.io/role"):
            roles.append(labels["node.kubernetes.io/role"])
        return sorted(set(roles)) or ["worker"]

    @staticmethod
    def _owner_kind(pod) -> Optional[str]:
        owners = pod.metadata.owner_references or []
        if not owners:
            return None
        owner = owners[0]
        return f"{owner.kind}/{owner.name}"

    def _empty_overview(self) -> Dict[str, Any]:
        return self._build_overview([], [], [], {"deployments": [], "statefulsets": [], "daemonsets": []}, [])

    def _build_overview(self, nodes, namespaces, pods, workloads, services) -> Dict[str, Any]:
        cpu_capacity = sum(n["cpu_capacity"] for n in nodes)
        cpu_allocatable = sum(n["cpu_allocatable"] for n in nodes)
        cpu_requested = sum(n["cpu_requested"] for n in nodes)
        mem_capacity = sum(n["memory_capacity"] for n in nodes)
        mem_allocatable = sum(n["memory_allocatable"] for n in nodes)
        mem_requested = sum(n["memory_requested"] for n in nodes)
        gpu_capacity = sum(n["gpu_capacity"] for n in nodes)
        gpu_requested = sum(n["gpu_requested"] for n in nodes)
        pod_phases: Dict[str, int] = {}
        for pod in pods:
            pod_phases[pod["phase"]] = pod_phases.get(pod["phase"], 0) + 1
        return {
            "status": self.get_status(),
            "counts": {
                "nodes": len(nodes),
                "nodes_ready": sum(1 for n in nodes if n["ready"]),
                "namespaces": len(namespaces),
                "pods": len(pods),
                "deployments": len(workloads.get("deployments", [])),
                "statefulsets": len(workloads.get("statefulsets", [])),
                "daemonsets": len(workloads.get("daemonsets", [])),
                "services": len(services),
            },
            "pod_phases": pod_phases,
            "resources": {
                "cpu": {
                    "capacity": cpu_capacity,
                    "allocatable": cpu_allocatable,
                    "requested": cpu_requested,
                    "capacity_text": format_cpu(cpu_capacity),
                    "allocatable_text": format_cpu(cpu_allocatable),
                    "requested_text": format_cpu(cpu_requested),
                    "percent": _percent(cpu_requested, cpu_allocatable),
                },
                "memory": {
                    "capacity": mem_capacity,
                    "allocatable": mem_allocatable,
                    "requested": mem_requested,
                    "capacity_text": format_memory(mem_capacity),
                    "allocatable_text": format_memory(mem_allocatable),
                    "requested_text": format_memory(mem_requested),
                    "percent": _percent(mem_requested, mem_allocatable),
                },
                "gpu": {
                    "capacity": gpu_capacity,
                    "requested": gpu_requested,
                    "percent": _percent(gpu_requested, gpu_capacity),
                },
            },
        }

    def _mock_overview(self) -> Dict[str, Any]:
        nodes = self._mock_nodes()
        pods = self._mock_pods()
        workloads = self._mock_workloads()
        return self._build_overview(nodes, self._mock_namespaces(), pods, workloads, self._mock_services())

    def _profile(self) -> Dict[str, Any]:
        return MOCK_PROFILES.get(self.mock_profile or "prod") or MOCK_PROFILES["prod"]

    def _mock_nodes(self) -> List[Dict[str, Any]]:
        return [self._node_from_spec(spec) for spec in self._profile()["nodes"]]

    def _node_from_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        mem = spec["mem_gi"] * 1024**3
        mem_req = int(spec["mem_req_gi"] * 1024**3)
        cpu = spec["cpu"]
        cpu_req = spec["cpu_req"]
        return {
            "name": spec["name"],
            "roles": spec["roles"],
            "ready": spec.get("ready", True),
            "unschedulable": False,
            "kubelet_version": self._profile()["version"],
            "os_image": "Ubuntu 22.04.4 LTS",
            "container_runtime": "containerd://1.7.13",
            "internal_ip": spec["ip"],
            "external_ip": None,
            "cpu_capacity": float(cpu),
            "cpu_allocatable": cpu - 0.2,
            "cpu_requested": cpu_req,
            "cpu_usage": cpu_req * 0.72,
            "memory_capacity": mem,
            "memory_allocatable": int(mem * 0.92),
            "memory_requested": mem_req,
            "memory_usage": int(mem_req * 0.8),
            "gpu_capacity": spec["gpu"],
            "gpu_requested": spec["gpu_req"],
            "pods": spec["pods"],
            "pod_capacity": spec.get("pod_capacity", 110),
            "cpu_percent": _percent(cpu_req, cpu - 0.2),
            "memory_percent": _percent(mem_req, int(mem * 0.92)),
            "age": spec.get("age", "18d"),
            "conditions": {
                "Ready": "True" if spec.get("ready", True) else "False",
                "MemoryPressure": "False",
                "DiskPressure": "False",
                "PIDPressure": "False",
            },
        }

    def _mock_namespaces(self) -> List[Dict[str, Any]]:
        return [{"name": n, "status": "Active", "age": a, "labels": {}} for n, a in self._profile()["namespaces"]]

    def _mock_pods(self) -> List[Dict[str, Any]]:
        rows = []
        for item in self._profile()["pods"]:
            mem = item[7] * 1024**2
            rows.append(
                {
                    "name": item[1],
                    "namespace": item[0],
                    "node": item[2],
                    "phase": item[3],
                    "ready": item[4],
                    "restarts": item[5],
                    "qos": "Burstable",
                    "ip": "10.244.1." + str(abs(hash(item[1])) % 200 + 2),
                    "cpu_request": item[6],
                    "memory_request": mem,
                    "cpu_limit": item[6] * 2,
                    "memory_limit": mem * 2,
                    "gpu_request": item[8],
                    "cpu_request_text": format_cpu(item[6]),
                    "memory_request_text": format_memory(mem),
                    "age": "3d",
                    "controlled_by": item[9],
                }
            )
        return rows

    def _mock_workloads(self) -> Dict[str, List[Dict[str, Any]]]:
        return self._profile()["workloads"]

    def _mock_services(self) -> List[Dict[str, Any]]:
        return self._profile()["services"]

    def _mock_events(self) -> List[Dict[str, Any]]:
        return self._profile()["events"]


MOCK_PROFILES: Dict[str, Dict[str, Any]] = {
    "prod": {
        "cluster": "prod-cn-shanghai",
        "context": "prod-cn-shanghai",
        "server": "https://k8s.prod.internal:6443",
        "version": "v1.29.4",
        "nodes": [
            {"name": "prod-master", "roles": ["control-plane"], "cpu": 4, "mem_gi": 8, "gpu": 0, "cpu_req": 1.35, "mem_req_gi": 2.4, "gpu_req": 0, "pods": 12, "ip": "10.0.0.10"},
            {"name": "prod-worker-1", "roles": ["worker"], "cpu": 16, "mem_gi": 64, "gpu": 2, "cpu_req": 9.5, "mem_req_gi": 28.0, "gpu_req": 2, "pods": 18, "ip": "10.0.0.21"},
            {"name": "prod-worker-2", "roles": ["worker"], "cpu": 16, "mem_gi": 64, "gpu": 2, "cpu_req": 6.2, "mem_req_gi": 21.5, "gpu_req": 1, "pods": 14, "ip": "10.0.0.22"},
        ],
        "namespaces": [("default", "40d"), ("kube-system", "40d"), ("monitoring", "22d"), ("production", "15d")],
        "pods": [
            ("kube-system", "coredns-abc12", "prod-master", "Running", "1/1", 0, 0.1, 70, 0, "ReplicaSet/coredns"),
            ("kube-system", "kube-proxy-w1", "prod-worker-1", "Running", "1/1", 0, 0.05, 32, 0, "DaemonSet/kube-proxy"),
            ("monitoring", "prometheus-0", "prod-worker-2", "Running", "1/1", 1, 1.0, 4096, 0, "StatefulSet/prometheus"),
            ("production", "inference-api-aaa11", "prod-worker-1", "Running", "1/1", 0, 2.0, 4096, 1, "ReplicaSet/inference-api"),
            ("production", "inference-api-bbb22", "prod-worker-1", "Running", "1/1", 2, 2.0, 4096, 1, "ReplicaSet/inference-api"),
            ("production", "training-job-7f2a", "prod-worker-2", "Running", "1/1", 0, 4.0, 16384, 1, "Job/training-job"),
            ("production", "web-frontend-c1", "prod-worker-2", "Running", "1/1", 0, 0.25, 256, 0, "ReplicaSet/web-frontend"),
            ("production", "web-frontend-c2", "prod-worker-1", "Pending", "0/1", 0, 0.25, 256, 0, "ReplicaSet/web-frontend"),
            ("default", "crash-loop-demo", "prod-worker-1", "CrashLoopBackOff", "0/1", 12, 0.1, 64, 0, None),
        ],
        "workloads": {
            "deployments": [
                {"kind": "Deployment", "name": "coredns", "namespace": "kube-system", "desired": 2, "ready": 2, "updated": 2, "available": 2, "age": "40d"},
                {"kind": "Deployment", "name": "inference-api", "namespace": "production", "desired": 2, "ready": 2, "updated": 2, "available": 2, "age": "6d"},
                {"kind": "Deployment", "name": "web-frontend", "namespace": "production", "desired": 2, "ready": 1, "updated": 2, "available": 1, "age": "4d"},
            ],
            "statefulsets": [
                {"kind": "StatefulSet", "name": "prometheus", "namespace": "monitoring", "desired": 1, "ready": 1, "updated": 1, "available": 1, "age": "22d"},
            ],
            "daemonsets": [
                {"kind": "DaemonSet", "name": "kube-proxy", "namespace": "kube-system", "desired": 3, "ready": 3, "updated": 3, "available": 3, "age": "40d"},
                {"kind": "DaemonSet", "name": "nvidia-device-plugin", "namespace": "kube-system", "desired": 2, "ready": 2, "updated": 2, "available": 2, "age": "18d"},
            ],
        },
        "services": [
            {"name": "kubernetes", "namespace": "default", "type": "ClusterIP", "cluster_ip": "10.96.0.1", "external_ip": None, "ports": "443/TCP", "age": "40d"},
            {"name": "inference-api", "namespace": "production", "type": "ClusterIP", "cluster_ip": "10.96.30.10", "external_ip": None, "ports": "8080/TCP", "age": "6d"},
            {"name": "web-frontend", "namespace": "production", "type": "LoadBalancer", "cluster_ip": "10.96.30.11", "external_ip": "203.0.113.40", "ports": "80/TCP", "age": "4d"},
        ],
        "events": [
            {"type": "Warning", "reason": "BackOff", "message": "Back-off restarting failed container crash-loop-demo", "namespace": "default", "object": "Pod/crash-loop-demo", "count": 12, "age": "2m", "timestamp": "2026-08-18T11:10:00Z"},
            {"type": "Warning", "reason": "FailedScheduling", "message": "0/3 nodes are available: 1 Insufficient cpu", "namespace": "production", "object": "Pod/web-frontend-c2", "count": 4, "age": "8m", "timestamp": "2026-08-18T11:04:00Z"},
            {"type": "Normal", "reason": "Scheduled", "message": "Successfully assigned production/training-job-7f2a to prod-worker-2", "namespace": "production", "object": "Pod/training-job-7f2a", "count": 1, "age": "3h", "timestamp": "2026-08-18T08:12:00Z"},
        ],
    },
    "staging": {
        "cluster": "staging-cn-shanghai",
        "context": "staging-cn-shanghai",
        "server": "https://k8s.staging.internal:6443",
        "version": "v1.28.9",
        "nodes": [
            {"name": "stg-master", "roles": ["control-plane"], "cpu": 4, "mem_gi": 8, "gpu": 0, "cpu_req": 0.9, "mem_req_gi": 1.8, "gpu_req": 0, "pods": 8, "ip": "10.1.0.10"},
            {"name": "stg-worker-1", "roles": ["worker"], "cpu": 8, "mem_gi": 32, "gpu": 0, "cpu_req": 3.4, "mem_req_gi": 10.0, "gpu_req": 0, "pods": 11, "ip": "10.1.0.21"},
        ],
        "namespaces": [("default", "30d"), ("kube-system", "30d"), ("staging", "12d")],
        "pods": [
            ("kube-system", "coredns-stg-1", "stg-master", "Running", "1/1", 0, 0.1, 70, 0, "ReplicaSet/coredns"),
            ("kube-system", "kube-proxy-stg", "stg-worker-1", "Running", "1/1", 0, 0.05, 32, 0, "DaemonSet/kube-proxy"),
            ("staging", "api-stg-1", "stg-worker-1", "Running", "1/1", 0, 0.5, 512, 0, "ReplicaSet/api"),
            ("staging", "api-stg-2", "stg-worker-1", "Running", "1/1", 1, 0.5, 512, 0, "ReplicaSet/api"),
            ("staging", "worker-stg-1", "stg-worker-1", "Running", "1/1", 0, 1.0, 1024, 0, "ReplicaSet/worker"),
            ("default", "echo-stg", "stg-worker-1", "Running", "1/1", 0, 0.1, 64, 0, "ReplicaSet/echo"),
        ],
        "workloads": {
            "deployments": [
                {"kind": "Deployment", "name": "coredns", "namespace": "kube-system", "desired": 1, "ready": 1, "updated": 1, "available": 1, "age": "30d"},
                {"kind": "Deployment", "name": "api", "namespace": "staging", "desired": 2, "ready": 2, "updated": 2, "available": 2, "age": "12d"},
                {"kind": "Deployment", "name": "worker", "namespace": "staging", "desired": 1, "ready": 1, "updated": 1, "available": 1, "age": "12d"},
            ],
            "statefulsets": [],
            "daemonsets": [
                {"kind": "DaemonSet", "name": "kube-proxy", "namespace": "kube-system", "desired": 2, "ready": 2, "updated": 2, "available": 2, "age": "30d"},
            ],
        },
        "services": [
            {"name": "kubernetes", "namespace": "default", "type": "ClusterIP", "cluster_ip": "10.96.0.1", "external_ip": None, "ports": "443/TCP", "age": "30d"},
            {"name": "api", "namespace": "staging", "type": "ClusterIP", "cluster_ip": "10.96.20.10", "external_ip": None, "ports": "8080/TCP", "age": "12d"},
        ],
        "events": [
            {"type": "Normal", "reason": "SuccessfulCreate", "message": "Created pod: api-stg-2", "namespace": "staging", "object": "ReplicaSet/api", "count": 1, "age": "1d", "timestamp": "2026-08-17T10:00:00Z"},
        ],
    },
    "edge": {
        "cluster": "edge-us-west",
        "context": "edge-us-west",
        "server": "https://k8s.edge.internal:6443",
        "version": "v1.27.12",
        "nodes": [
            {"name": "edge-master", "roles": ["control-plane", "worker"], "cpu": 8, "mem_gi": 16, "gpu": 0, "cpu_req": 2.1, "mem_req_gi": 5.5, "gpu_req": 0, "pods": 9, "ip": "10.8.0.10"},
            {"name": "edge-worker-1", "roles": ["worker"], "cpu": 8, "mem_gi": 16, "gpu": 1, "cpu_req": 1.2, "mem_req_gi": 3.0, "gpu_req": 0, "pods": 4, "ip": "10.8.0.21", "ready": False},
        ],
        "namespaces": [("default", "20d"), ("kube-system", "20d"), ("edge", "8d")],
        "pods": [
            ("kube-system", "coredns-edge", "edge-master", "Running", "1/1", 0, 0.1, 70, 0, "ReplicaSet/coredns"),
            ("edge", "iot-gateway-1", "edge-master", "Running", "1/1", 0, 0.5, 256, 0, "ReplicaSet/iot-gateway"),
            ("edge", "iot-gateway-2", "edge-worker-1", "Pending", "0/1", 0, 0.5, 256, 0, "ReplicaSet/iot-gateway"),
            ("edge", "model-cache", "edge-master", "Running", "1/1", 0, 1.0, 2048, 0, "Deployment/model-cache"),
        ],
        "workloads": {
            "deployments": [
                {"kind": "Deployment", "name": "iot-gateway", "namespace": "edge", "desired": 2, "ready": 1, "updated": 2, "available": 1, "age": "8d"},
                {"kind": "Deployment", "name": "model-cache", "namespace": "edge", "desired": 1, "ready": 1, "updated": 1, "available": 1, "age": "8d"},
            ],
            "statefulsets": [],
            "daemonsets": [
                {"kind": "DaemonSet", "name": "kube-proxy", "namespace": "kube-system", "desired": 2, "ready": 1, "updated": 2, "available": 1, "age": "20d"},
            ],
        },
        "services": [
            {"name": "kubernetes", "namespace": "default", "type": "ClusterIP", "cluster_ip": "10.96.0.1", "external_ip": None, "ports": "443/TCP", "age": "20d"},
            {"name": "iot-gateway", "namespace": "edge", "type": "NodePort", "cluster_ip": "10.96.40.10", "external_ip": None, "ports": "8080/TCP:32080", "age": "8d"},
        ],
        "events": [
            {"type": "Warning", "reason": "NodeNotReady", "message": "Node edge-worker-1 status is now: NodeNotReady", "namespace": "default", "object": "Node/edge-worker-1", "count": 3, "age": "12m", "timestamp": "2026-08-18T11:02:00Z"},
            {"type": "Warning", "reason": "FailedScheduling", "message": "0/2 nodes are available: 1 node(s) were unschedulable", "namespace": "edge", "object": "Pod/iot-gateway-2", "count": 6, "age": "10m", "timestamp": "2026-08-18T11:04:00Z"},
        ],
    },
}
