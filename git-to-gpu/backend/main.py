"""
From Git Commit to NVIDIA GPU — 生产级 AI/ML 平台演示控制台。

Git → CI/CD → Kubeflow → Model Registry → KServe → Inference Runtime → NVIDIA GPU
"""
import logging
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from factory import platform

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

APP_DIR = os.path.dirname(__file__)
FRONTEND_DIR = os.path.abspath(os.path.join(APP_DIR, "..", "frontend"))
ROOT_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))

app = FastAPI(
    title="Git to GPU AI Factory",
    description="Production AI/ML platform demo: versioned model artifacts from Git to NVIDIA GPU",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartRunRequest(BaseModel):
    name: str = "assist-llm"
    runtime: str = Field(default="vllm", pattern="^(xgboost|triton|vllm)$")
    gpu: str = Field(default="h100", pattern="^(a100|h100|h200)$")
    storage: str = Field(default="oci", pattern="^(s3|oci)$")
    framework: str = "transformers"


class DeployRequest(BaseModel):
    artifact_id: str
    runtime: Optional[str] = None
    gpu: Optional[str] = None


class MigrateRequest(BaseModel):
    target_storage: str = Field(pattern="^(s3|oci)$")


class InferRequest(BaseModel):
    prompt: str = "比较一下把模型当容器 vs 当版本化制品的差别"


@app.get("/api/overview")
async def overview():
    return platform.overview()


@app.get("/api/architecture")
async def architecture():
    return platform.architecture()


@app.get("/api/artifacts")
async def list_artifacts():
    return platform.list_artifacts()


@app.get("/api/services")
async def list_services():
    return platform.list_services()


@app.get("/api/runs")
async def list_runs():
    return platform.list_runs()


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    try:
        return platform.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="流水线运行不存在") from exc


@app.post("/api/runs")
async def start_run(request: StartRunRequest):
    return platform.start_run(
        name=request.name,
        runtime=request.runtime,
        gpu=request.gpu,
        storage=request.storage,
        framework=request.framework,
    )


@app.post("/api/artifacts/{artifact_id}/deploy")
async def deploy_artifact(artifact_id: str, request: DeployRequest):
    try:
        return platform.deploy_artifact(artifact_id, runtime=request.runtime, gpu=request.gpu)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="制品不存在") from exc


@app.post("/api/artifacts/{artifact_id}/migrate")
async def migrate_artifact(artifact_id: str, request: MigrateRequest):
    try:
        return platform.migrate_artifact(artifact_id, request.target_storage)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="制品不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/services/{service_id}/infer")
async def infer(service_id: str, request: InferRequest):
    try:
        return platform.infer(service_id, request.prompt)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="InferenceService 不存在") from exc


@app.post("/api/demo/seed")
async def seed_demo():
    created = platform.seed_demo()
    return {"count": len(created), "overview": platform.overview()}


@app.get("/")
async def index():
    path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.isfile(path):
        return FileResponse(path, headers={"Cache-Control": "no-store"})
    return {"message": "Git to GPU AI Factory", "docs": "/docs"}


@app.get("/architecture.png")
async def architecture_image():
    path = os.path.join(ROOT_DIR, "architecture.png")
    if os.path.isfile(path):
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="architecture.png not found")


if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8005)
