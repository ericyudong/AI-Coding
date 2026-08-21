"""
CNCF Open Cluster Management (OCM) Hub 控制台后端。

Hub-Spoke：ManagedCluster 双向握手、ManifestWork pull、Placement 决策。
已接受集群可通过模拟 cluster-proxy 读取 inventory。
"""
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from cluster_manager import manager
from k8s_service import DEFAULT_KUBECONFIG, list_kube_contexts
from ocm_hub import hub

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="OCM Multi-Cluster Hub",
    description="基于 CNCF Open Cluster Management 的 Hub-Spoke 多集群控制面",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))


class JoinRequest(BaseModel):
    name: str = ""
    kubeconfig_path: str = DEFAULT_KUBECONFIG
    context: Optional[str] = None
    environment: str = "production"
    region: str = ""
    labels: Optional[Dict[str, str]] = None
    auto_accept: bool = False


class ImportRequest(BaseModel):
    kubeconfig_path: str = DEFAULT_KUBECONFIG
    environment: str = "production"
    region: str = ""
    auto_accept: bool = False


class UpdateClusterRequest(BaseModel):
    environment: Optional[str] = None
    region: Optional[str] = None
    context: Optional[str] = None
    labels: Optional[Dict[str, str]] = None


class ManifestWorkRequest(BaseModel):
    name: str
    cluster: str
    manifests: List[Dict[str, Any]] = Field(default_factory=list)


class PlacementRequest(BaseModel):
    name: str
    match_labels: Optional[Dict[str, str]] = None
    claim_equals: Optional[Dict[str, str]] = None
    cluster_set: str = "default"


def _cluster_or_404(cluster_id: str):
    try:
        return manager.service(cluster_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ManagedCluster 不存在") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/hub")
async def hub_info():
    return hub.info()


@app.get("/api/fleet")
async def fleet_overview():
    return manager.fleet_overview()


@app.get("/api/managedclusters")
async def list_managed_clusters():
    return manager.list_clusters()


@app.get("/api/clusters")
async def list_clusters():
    return manager.list_clusters()


@app.post("/api/managedclusters/join")
@app.post("/api/clusters")
async def join_cluster(request: JoinRequest):
    try:
        return manager.join_cluster(
            name=request.name,
            kubeconfig_path=request.kubeconfig_path,
            context=request.context,
            environment=request.environment,
            region=request.region,
            labels=request.labels,
            auto_accept=request.auto_accept,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/managedclusters/import")
@app.post("/api/clusters/import")
async def import_clusters(request: ImportRequest):
    try:
        created = manager.import_kubeconfig(
            request.kubeconfig_path,
            request.environment,
            request.region,
            auto_accept=request.auto_accept,
        )
        return {"count": len(created), "clusters": created}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/managedclusters/upload")
@app.post("/api/clusters/upload")
async def upload_cluster(
    file: UploadFile = File(...),
    name: str = Form(""),
    context: Optional[str] = Form(None),
    environment: str = Form("production"),
    region: str = Form(""),
    import_all: bool = Form(False),
    auto_accept: bool = Form(False),
):
    content = (await file.read()).decode("utf-8")
    if not content.strip():
        raise HTTPException(status_code=400, detail="kubeconfig 文件为空")
    try:
        clusters = manager.add_from_upload(
            content=content,
            name=name,
            context=context,
            environment=environment,
            region=region,
            import_all=import_all,
            auto_accept=auto_accept,
        )
        return {"count": len(clusters), "clusters": clusters}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/managedclusters/demo")
@app.post("/api/clusters/demo")
async def load_demo():
    created = manager.load_demo_clusters()
    return {"count": len(created), "clusters": manager.list_clusters(), "hub": hub.info()}


def _get_cluster(cluster_name: str):
    try:
        return manager.get_cluster(cluster_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ManagedCluster 不存在") from exc


@app.get("/api/managedclusters/{name}")
async def get_managed_cluster(name: str):
    return _get_cluster(name)


@app.get("/api/clusters/{cluster_id}")
async def get_cluster(cluster_id: str):
    return _get_cluster(cluster_id)


@app.post("/api/managedclusters/{name}/accept")
async def accept_cluster(name: str):
    try:
        return manager.accept(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ManagedCluster 不存在") from exc


@app.post("/api/managedclusters/{name}/deny")
async def deny_cluster(name: str):
    try:
        return manager.deny(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ManagedCluster 不存在") from exc


def _update_cluster(cluster_name: str, request: UpdateClusterRequest):
    try:
        return manager.update_cluster(cluster_name, **request.model_dump(exclude_unset=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ManagedCluster 不存在") from exc


@app.patch("/api/managedclusters/{name}")
async def update_managed_cluster(name: str, request: UpdateClusterRequest):
    return _update_cluster(name, request)


@app.patch("/api/clusters/{cluster_id}")
async def update_cluster(cluster_id: str, request: UpdateClusterRequest):
    return _update_cluster(cluster_id, request)


def _delete_cluster(cluster_name: str):
    try:
        manager.delete_cluster(cluster_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ManagedCluster 不存在") from exc
    return {"ok": True}


@app.delete("/api/managedclusters/{name}")
async def delete_managed_cluster(name: str):
    return _delete_cluster(name)


@app.delete("/api/clusters/{cluster_id}")
async def delete_cluster(cluster_id: str):
    return _delete_cluster(cluster_id)


def _refresh_cluster(cluster_name: str):
    try:
        return manager.refresh_cluster(cluster_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ManagedCluster 不存在") from exc


@app.post("/api/managedclusters/{name}/refresh")
async def refresh_managed_cluster(name: str):
    return _refresh_cluster(name)


@app.post("/api/clusters/{cluster_id}/refresh")
async def refresh_cluster(cluster_id: str):
    return _refresh_cluster(cluster_id)


@app.get("/api/manifestworks")
async def list_manifest_works(cluster: Optional[str] = None):
    return hub.list_manifest_works(cluster)


@app.post("/api/manifestworks")
async def create_manifest_work(request: ManifestWorkRequest):
    try:
        return hub.create_manifest_work(request.cluster, request.name, request.manifests)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ManagedCluster 不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/manifestworks/{cluster}/{name}/reconcile")
async def reconcile_manifest_work(cluster: str, name: str):
    try:
        return hub.reconcile_work(cluster, name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ManifestWork 不存在") from exc


@app.delete("/api/manifestworks/{cluster}/{name}")
async def delete_manifest_work(cluster: str, name: str):
    try:
        hub.delete_manifest_work(cluster, name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ManifestWork 不存在") from exc
    return {"ok": True}


@app.get("/api/placements")
async def list_placements():
    return hub.list_placements()


@app.post("/api/placements")
async def create_placement(request: PlacementRequest):
    return hub.create_placement(
        request.name,
        match_labels=request.match_labels,
        claim_equals=request.claim_equals,
        cluster_set=request.cluster_set,
    )


@app.delete("/api/placements/{name}")
async def delete_placement(name: str):
    try:
        hub.delete_placement(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Placement 不存在") from exc
    return {"ok": True}


@app.get("/api/contexts")
async def list_contexts(kubeconfig_path: Optional[str] = None):
    try:
        return list_kube_contexts(kubeconfig_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"读取 kubeconfig 失败: {exc}") from exc


@app.get("/api/clusters/{cluster_id}/overview")
async def cluster_overview(cluster_id: str):
    return _cluster_or_404(cluster_id).get_overview()


@app.get("/api/clusters/{cluster_id}/nodes")
async def cluster_nodes(cluster_id: str):
    return _cluster_or_404(cluster_id).get_nodes()


@app.get("/api/clusters/{cluster_id}/namespaces")
async def cluster_namespaces(cluster_id: str):
    return _cluster_or_404(cluster_id).get_namespaces()


@app.get("/api/clusters/{cluster_id}/pods")
async def cluster_pods(cluster_id: str, namespace: Optional[str] = None):
    return _cluster_or_404(cluster_id).get_pods(namespace)


@app.get("/api/clusters/{cluster_id}/workloads")
async def cluster_workloads(cluster_id: str, namespace: Optional[str] = None):
    return _cluster_or_404(cluster_id).get_workloads(namespace)


@app.get("/api/clusters/{cluster_id}/services")
async def cluster_services(cluster_id: str, namespace: Optional[str] = None):
    return _cluster_or_404(cluster_id).get_services(namespace)


@app.get("/api/clusters/{cluster_id}/events")
async def cluster_events(cluster_id: str, namespace: Optional[str] = None, limit: int = 50):
    return _cluster_or_404(cluster_id).get_events(namespace, limit)


@app.get("/")
async def index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.isfile(index_path):
        return {"message": "OCM Multi-Cluster Hub API", "docs": "/docs"}
    return FileResponse(index_path, headers={"Cache-Control": "no-store"})


if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)
