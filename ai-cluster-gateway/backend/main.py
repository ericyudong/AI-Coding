"""
AI Cluster Gateway

OpenAI 兼容推理入口 + 多集群模型部署控制面。
"""
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from catalog import catalog
from clusters import clusters, hub, list_kube_contexts
from deployer import deploy_model, recommend_cluster, seed_demo_models, undeploy_cluster_models, undeploy_model
from inference import chat_completions
from router import RouteError, list_public_models

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

APP_DIR = os.path.dirname(__file__)
FRONTEND_DIR = os.path.abspath(os.path.join(APP_DIR, "..", "frontend"))
API_KEY = os.environ.get("GATEWAY_API_KEY", "")

app = FastAPI(
    title="AI Cluster Gateway",
    description="OCM Hub 上的 OpenAI 兼容推理入口：ManagedCluster 放置 + ManifestWork 部署",
    version="2.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

seed_demo_models()


class RegisterClusterRequest(BaseModel):
    name: str = ""
    kubeconfig_path: str
    context: Optional[str] = None
    environment: str = "production"
    region: str = ""
    gpu_total: int = 0
    auto_accept: bool = False


class UpdateClusterRequest(BaseModel):
    name: Optional[str] = None
    environment: Optional[str] = None
    region: Optional[str] = None
    gpu_total: Optional[int] = None


class ImportClustersRequest(BaseModel):
    kubeconfig_path: str
    environment: str = "production"
    region: str = ""
    auto_accept: bool = False


class DeployRequest(BaseModel):
    alias: str
    model_id: str
    cluster_id: str
    replicas: int = 1
    gpu: int = 1
    runtime: str = "vllm"
    image: Optional[str] = None
    weight: int = 100
    add_to_route: Optional[str] = None


class RouteRequest(BaseModel):
    name: str
    strategy: str = "weighted"
    backends: List[Dict[str, Any]]


class ChatRequest(BaseModel):
    model: str = "default"
    messages: List[Dict[str, Any]]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


def _check_key(authorization: Optional[str]) -> None:
    if not API_KEY:
        return
    token = (authorization or "").replace("Bearer ", "").strip()
    if token != API_KEY:
        raise HTTPException(status_code=401, detail="无效的 API Key")


def _enrich_clusters():
    rows = []
    for item in clusters.list():
        used = catalog.gpu_used(item["id"])
        rows.append({**item, "gpu_used": used, "gpu_free": max(0, int(item.get("gpu_total") or 0) - used)})
    return rows


@app.get("/api/hub")
async def hub_info():
    return hub.info()


@app.get("/api/overview")
async def overview():
    deps = catalog.list_deployments()
    return {
        "hub": hub.info(),
        "clusters": _enrich_clusters(),
        "deployments": deps,
        "routes": list(catalog.routes.values()),
        "manifestWorks": hub.list_manifest_works(),
        "placements": hub.list_placements(),
        "stats": catalog.snapshot(),
        "models": list_public_models(),
    }


@app.get("/api/clusters")
async def list_clusters():
    return _enrich_clusters()


@app.get("/api/clusters/{cluster_id}")
async def get_cluster(cluster_id: str):
    try:
        item = clusters.get(cluster_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="集群不存在") from exc
    used = catalog.gpu_used(cluster_id)
    return {
        **item,
        "gpu_used": used,
        "gpu_free": max(0, int(item.get("gpu_total") or 0) - used),
        "deployments": catalog.list_deployments(cluster_id),
    }


@app.post("/api/clusters")
async def register_cluster(request: RegisterClusterRequest):
    try:
        return clusters.join(
            name=request.name,
            kubeconfig_path=request.kubeconfig_path,
            context=request.context,
            environment=request.environment,
            region=request.region,
            gpu_total=request.gpu_total,
            auto_accept=request.auto_accept,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/clusters/import")
async def import_clusters(request: ImportClustersRequest):
    try:
        created = clusters.import_kubeconfig(
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


@app.post("/api/clusters/upload")
async def upload_cluster(
    file: UploadFile = File(...),
    name: str = Form(""),
    context: Optional[str] = Form(None),
    environment: str = Form("production"),
    region: str = Form(""),
    import_all: bool = Form(False),
    gpu_total: int = Form(0),
    auto_accept: bool = Form(False),
):
    content = (await file.read()).decode("utf-8")
    if not content.strip():
        raise HTTPException(status_code=400, detail="kubeconfig 文件为空")
    try:
        created = clusters.register_from_content(
            content=content,
            name=name,
            context=context,
            environment=environment,
            region=region,
            import_all=import_all,
            gpu_total=gpu_total,
            auto_accept=auto_accept,
        )
        return {"count": len(created), "clusters": created}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/managedclusters/{name}/accept")
async def accept_cluster(name: str):
    try:
        item = clusters.accept(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ManagedCluster 不存在") from exc
    used = catalog.gpu_used(name)
    return {**item, "gpu_used": used, "gpu_free": max(0, int(item.get("gpu_total") or 0) - used)}


@app.post("/api/managedclusters/{name}/deny")
async def deny_cluster(name: str):
    try:
        removed = undeploy_cluster_models(name)
        item = clusters.deny(name)
        return {"ok": True, "cluster": item, "undeployed": len(removed)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="ManagedCluster 不存在") from exc


@app.get("/api/manifestworks")
async def list_works(cluster: Optional[str] = None):
    return hub.list_manifest_works(cluster)


@app.get("/api/placements")
async def list_placements():
    return hub.list_placements()


@app.post("/api/clusters/demo")
async def load_demo_clusters():
    created = clusters.seed_demo()
    if created and not catalog.deployments:
        seed_demo_models()
    return {"count": len(created), "clusters": _enrich_clusters()}


@app.patch("/api/clusters/{cluster_id}")
async def update_cluster(cluster_id: str, request: UpdateClusterRequest):
    try:
        return clusters.update(cluster_id, **request.model_dump(exclude_unset=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="集群不存在") from exc


@app.delete("/api/clusters/{cluster_id}")
async def delete_cluster(cluster_id: str):
    try:
        removed = undeploy_cluster_models(cluster_id)
        record = clusters.delete(cluster_id)
        return {"ok": True, "cluster": record, "undeployed": len(removed)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="集群不存在") from exc


@app.post("/api/clusters/{cluster_id}/refresh")
async def refresh_cluster(cluster_id: str):
    try:
        clusters.refresh(cluster_id)
        item = clusters.get(cluster_id)
        used = catalog.gpu_used(cluster_id)
        return {**item, "gpu_used": used, "gpu_free": max(0, int(item.get("gpu_total") or 0) - used)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="集群不存在") from exc


@app.get("/api/contexts")
async def list_contexts(kubeconfig_path: str):
    try:
        return list_kube_contexts(kubeconfig_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/placement")
async def placement(gpu: int = 1):
    return recommend_cluster(gpu)


@app.get("/api/models")
async def list_models_admin():
    return catalog.list_deployments()


@app.post("/api/models/deploy")
async def deploy(request: DeployRequest):
    try:
        return deploy_model(
            alias=request.alias,
            model_id=request.model_id,
            cluster_id=request.cluster_id,
            replicas=request.replicas,
            gpu=request.gpu,
            runtime=request.runtime,
            image=request.image,
            weight=request.weight,
            add_to_route=request.add_to_route,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="集群不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/models/{deployment_id}")
async def undeploy(deployment_id: str):
    try:
        return undeploy_model(deployment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="部署不存在") from exc


@app.get("/api/routes")
async def list_routes():
    return list(catalog.routes.values())


@app.put("/api/routes")
async def put_route(request: RouteRequest):
    return catalog.upsert_route(request.name, request.strategy, request.backends)


@app.get("/api/stats")
async def stats():
    return catalog.snapshot()


@app.get("/v1/models")
async def openai_models(authorization: Optional[str] = Header(None)):
    _check_key(authorization)
    return {"object": "list", "data": list_public_models()}


@app.post("/v1/chat/completions")
async def openai_chat(request: Request, body: ChatRequest, authorization: Optional[str] = Header(None)):
    _check_key(authorization)
    if body.stream:
        raise HTTPException(status_code=400, detail="当前版本不支持 stream=true")
    payload = body.model_dump(exclude_none=True)
    cluster_id = request.headers.get("x-cluster-id")
    region = request.headers.get("x-region")
    try:
        return await chat_completions(payload, cluster_id=cluster_id, region=region)
    except RouteError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"后端推理失败: {exc}") from exc


@app.get("/")
async def index():
    path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.isfile(path):
        return FileResponse(path, headers={"Cache-Control": "no-store"})
    return {"message": "AI Cluster Gateway", "docs": "/docs"}


if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8004)
