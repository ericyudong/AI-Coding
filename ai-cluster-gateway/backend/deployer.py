"""Deploy / undeploy inference runtimes onto a chosen ManagedCluster via ManifestWork."""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from catalog import catalog
from clusters import clusters, hub

logger = logging.getLogger(__name__)

NAMESPACE = "inference"
DEFAULT_IMAGES = {
    "vllm": "vllm/vllm-openai:latest",
    "tgi": "ghcr.io/huggingface/text-generation-inference:latest",
}


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    return (text or "model")[:40]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def recommend_cluster(gpu: int) -> Dict[str, Any]:
    hub.reload_if_changed()
    placement = hub.placements.get("gpu-inference")
    decided = {d["clusterName"] for d in hub.evaluate_placement(placement)} if placement else set()
    ranked = []
    for cluster in clusters.list():
        if not cluster.get("hubAcceptsClient"):
            continue
        used = catalog.gpu_used(cluster["id"])
        free = max(0, int(cluster.get("gpu_total") or 0) - used)
        in_placement = (not decided) or cluster["id"] in decided
        ranked.append(
            {
                **cluster,
                "gpu_used": used,
                "gpu_free": free,
                "fits": in_placement and free >= gpu,
                "placement": "gpu-inference" if cluster["id"] in decided else None,
            }
        )
    ranked.sort(key=lambda x: (-int(x["fits"]), -x["gpu_free"]))
    return {
        "gpu": gpu,
        "placement": "gpu-inference",
        "kind": "Placement",
        "clusters": ranked,
    }


def deploy_model(
    alias: str,
    model_id: str,
    cluster_id: str,
    replicas: int = 1,
    gpu: int = 1,
    runtime: str = "vllm",
    image: Optional[str] = None,
    weight: int = 100,
    add_to_route: Optional[str] = None,
) -> Dict[str, Any]:
    cluster = clusters.get(cluster_id)
    if not cluster.get("hubAcceptsClient"):
        raise ValueError(f"ManagedCluster {cluster['name']} 尚未被 Hub 接受，不能下发 ManifestWork")
    used = catalog.gpu_used(cluster_id)
    need = max(1, gpu) * max(1, replicas)
    free = int(cluster.get("gpu_total") or 0) - used
    if need > free:
        raise ValueError(f"集群 {cluster['name']} GPU 不足：需要 {need}，剩余 {free}")

    deployment_id = uuid.uuid4().hex[:10]
    slug = _slug(alias)
    image = image or DEFAULT_IMAGES.get(runtime, DEFAULT_IMAGES["vllm"])
    record = {
        "id": deployment_id,
        "alias": alias,
        "model_id": model_id,
        "cluster_id": cluster_id,
        "cluster_name": cluster["name"],
        "region": cluster.get("region"),
        "environment": cluster.get("environment"),
        "runtime": runtime,
        "image": image,
        "replicas": replicas,
        "gpu": gpu,
        "namespace": NAMESPACE,
        "k8s_name": f"inf-{slug}-{deployment_id[:4]}",
        "status": "deploying",
        "endpoint": None,
        "weight": weight,
        "manifest_work": None,
        "created_at": _now(),
    }

    if cluster.get("source") == "demo":
        record["status"] = "running"
        record["endpoint"] = f"mock://{cluster_id}/{deployment_id}"
    else:
        _apply_k8s(cluster_id, record)

    _bind_manifest_work(record)
    catalog.put_deployment(record)
    route_name = add_to_route or alias
    route = catalog.routes.get(route_name)
    backend = {"deployment_id": deployment_id, "weight": weight}
    if route:
        route["backends"].append(backend)
        catalog.upsert_route(route_name, route.get("strategy") or "weighted", route["backends"])
    else:
        catalog.upsert_route(route_name, "weighted", [backend])
    return record


def undeploy_model(deployment_id: str) -> Dict[str, Any]:
    record = catalog.deployments.get(deployment_id)
    if not record:
        raise KeyError(deployment_id)
    cluster = clusters.get(record["cluster_id"])
    if cluster.get("source") != "demo":
        _delete_k8s(record["cluster_id"], record)
    work_name = record.get("manifest_work")
    if work_name:
        try:
            hub.delete_manifest_work(record["cluster_id"], work_name)
        except KeyError:
            pass
    return catalog.delete_deployment(deployment_id)


def undeploy_cluster_models(cluster_id: str) -> List[Dict[str, Any]]:
    removed = []
    for item in list(catalog.list_deployments(cluster_id)):
        removed.append(undeploy_model(item["id"]))
    return removed


def _apply_k8s(cluster_id: str, record: Dict[str, Any]) -> None:
    pair = clusters.k8s_apps(cluster_id)
    if pair is None:
        record["status"] = "running"
        record["endpoint"] = f"mock://{cluster_id}/{record['id']}"
        return
    apps, core = pair
    name = record["k8s_name"]
    ns = record["namespace"]
    from kubernetes.client import (
        V1Container,
        V1ContainerPort,
        V1Deployment,
        V1DeploymentSpec,
        V1LabelSelector,
        V1Namespace,
        V1ObjectMeta,
        V1PodSpec,
        V1PodTemplateSpec,
        V1ResourceRequirements,
        V1Service,
        V1ServicePort,
        V1ServiceSpec,
    )
    from kubernetes.client.rest import ApiException

    try:
        core.create_namespace(V1Namespace(metadata=V1ObjectMeta(name=ns)))
    except ApiException as exc:
        if exc.status != 409:
            raise

    labels = {"app": name, "gateway.model": record["alias"]}
    args = ["--model", record["model_id"], "--port", "8000", "--served-model-name", record["alias"]]
    if record["runtime"] == "tgi":
        args = ["--model-id", record["model_id"], "--port", "80"]
    container_port = 80 if record["runtime"] == "tgi" else 8000
    container = V1Container(
        name="runtime",
        image=record["image"],
        args=args,
        ports=[V1ContainerPort(container_port=container_port)],
        resources=V1ResourceRequirements(limits={"nvidia.com/gpu": str(record["gpu"])} if record["gpu"] else {}),
    )
    deployment = V1Deployment(
        metadata=V1ObjectMeta(name=name, namespace=ns, labels=labels),
        spec=V1DeploymentSpec(
            replicas=record["replicas"],
            selector=V1LabelSelector(match_labels={"app": name}),
            template=V1PodTemplateSpec(
                metadata=V1ObjectMeta(labels=labels),
                spec=V1PodSpec(containers=[container]),
            ),
        ),
    )
    apps.create_namespaced_deployment(ns, deployment)
    service = V1Service(
        metadata=V1ObjectMeta(name=name, namespace=ns, labels=labels),
        spec=V1ServiceSpec(
            selector={"app": name},
            ports=[V1ServicePort(port=8000, target_port=container_port)],
        ),
    )
    core.create_namespaced_service(ns, service)
    record["status"] = "running"
    record["endpoint"] = f"http://{name}.{ns}.svc.cluster.local:8000/v1"


def _delete_k8s(cluster_id: str, record: Dict[str, Any]) -> None:
    pair = clusters.k8s_apps(cluster_id)
    if pair is None:
        return
    apps, core = pair
    from kubernetes.client.rest import ApiException

    try:
        apps.delete_namespaced_deployment(record["k8s_name"], record["namespace"])
    except ApiException:
        pass
    try:
        core.delete_namespaced_service(record["k8s_name"], record["namespace"])
    except ApiException:
        pass


def _bind_manifest_work(record: Dict[str, Any]) -> None:
    name = record.get("k8s_name") or f"inf-{record['id']}"
    manifests = [
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": name, "namespace": record.get("namespace") or NAMESPACE},
            "spec": {
                "replicas": record.get("replicas") or 1,
                "selector": {"matchLabels": {"app": name}},
                "template": {
                    "metadata": {"labels": {"app": name, "gateway.model": record.get("alias")}},
                    "spec": {
                        "containers": [
                            {
                                "name": "runtime",
                                "image": record.get("image"),
                                "args": ["--model", record.get("model_id"), "--served-model-name", record.get("alias")],
                            }
                        ]
                    },
                },
            },
        },
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": name, "namespace": record.get("namespace") or NAMESPACE},
            "spec": {"selector": {"app": name}, "ports": [{"port": 8000}]},
        },
    ]
    hub.reload_if_changed()
    key = f"{record['cluster_id']}/{name}"
    if key in hub.manifest_works:
        hub.reconcile_work(record["cluster_id"], name)
    else:
        hub.create_manifest_work(record["cluster_id"], name, manifests)
    record["manifest_work"] = name


def seed_demo_models() -> None:
    if catalog.deployments:
        for item in catalog.list_deployments():
            if item.get("manifest_work"):
                continue
            try:
                if clusters.accepted(item["cluster_id"]):
                    _bind_manifest_work(item)
                    catalog.put_deployment(item)
            except Exception as exc:
                logger.warning("补齐 ManifestWork 失败 %s: %s", item.get("alias"), exc)
        return
    specs = [
        ("qwen2-72b", "Qwen/Qwen2-72B-Instruct", "prod-cn-shanghai", 1, 4, "reasoning", 100),
        ("llama3-70b", "meta-llama/Meta-Llama-3-70B-Instruct", "prod-cn-shanghai", 1, 4, "reasoning", 0),
        ("qwen2-7b", "Qwen/Qwen2-7B-Instruct", "staging-cn-shanghai", 1, 1, "default", 80),
        ("qwen2-1.5b", "Qwen/Qwen2-1.5B-Instruct", "edge-us-west", 1, 1, "fast", 100),
    ]
    created = {}
    for alias, model_id, cluster_id, replicas, gpu, route, weight in specs:
        record = deploy_model(
            alias=alias,
            model_id=model_id,
            cluster_id=cluster_id,
            replicas=replicas,
            gpu=gpu,
            runtime="vllm",
            weight=weight or 100,
            add_to_route=route,
        )
        created[alias] = record["id"]
    catalog.upsert_route(
        "default",
        "weighted",
        [
            {"deployment_id": created["qwen2-7b"], "weight": 80},
            {"deployment_id": created["qwen2-1.5b"], "weight": 20},
        ],
    )
    catalog.upsert_route(
        "reasoning",
        "failover",
        [
            {"deployment_id": created["qwen2-72b"], "weight": 100},
            {"deployment_id": created["llama3-70b"], "weight": 100},
        ],
    )
    catalog.upsert_route(
        "fast",
        "failover",
        [
            {"deployment_id": created["qwen2-1.5b"], "weight": 100},
            {"deployment_id": created["qwen2-7b"], "weight": 100},
        ],
    )
