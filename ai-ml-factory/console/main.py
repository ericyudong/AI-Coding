"""
AI/ML Factory Console — FastAPI control plane for the production scaffold.

Surfaces local artifacts, KServe manifests, training jobs, and architecture.
Does not replace Kubeflow/KServe; it operates the repo and local smoke path.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from catalog import console

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND = os.path.join(ROOT, "frontend")

app = FastAPI(
    title="AI/ML Factory Console",
    description="Control plane UI API for Kubeflow → Registry → KServe → GPU",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TrainRequest(BaseModel):
    name: str = "fraud-xgb"
    framework: str = Field(default="xgboost", pattern="^(xgboost|pytorch)$")
    version: Optional[str] = None
    n_samples: int = 1000


class PredictRequest(BaseModel):
    prompt: Optional[str] = None
    instances: Optional[list] = None
    messages: Optional[Any] = None


class PipelineSpecBody(BaseModel):
    spec: Dict[str, Any]


class PipelineCompileBody(BaseModel):
    spec_id: Optional[str] = None
    spec: Optional[Dict[str, Any]] = None


@app.get("/api/overview")
async def overview():
    return console.overview()


@app.get("/api/pipelines/components")
async def pipeline_components():
    return console.list_pipeline_components()


@app.get("/api/pipelines/specs")
async def pipeline_specs():
    return console.list_pipeline_specs()


@app.get("/api/pipelines/specs/{spec_id}")
async def get_pipeline_spec(spec_id: str):
    try:
        return console.get_pipeline_spec(spec_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="spec not found") from exc


@app.put("/api/pipelines/specs/{spec_id}")
async def put_pipeline_spec(spec_id: str, body: PipelineSpecBody):
    try:
        return console.save_pipeline_spec(spec_id, body.spec)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/pipelines/validate")
async def validate_pipeline(body: PipelineSpecBody):
    return console.validate_pipeline_spec(body.spec)


@app.post("/api/pipelines/compile")
async def compile_pipeline(body: PipelineCompileBody):
    try:
        result = console.compile_pipeline_spec(spec=body.spec, spec_id=body.spec_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="spec not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface kfp errors to UI
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("validation") or result)
    return result


@app.get("/api/architecture")
async def architecture():
    return console.architecture()


@app.get("/api/artifacts")
async def artifacts():
    return console.list_artifacts()


@app.get("/api/services")
async def services():
    return console.list_services()


@app.get("/api/manifests")
async def manifests():
    return console.list_manifests()


@app.get("/api/cluster")
async def cluster():
    return console.cluster_probe()


@app.get("/api/jobs")
async def jobs():
    return sorted(console.jobs.values(), key=lambda j: j["created_at"], reverse=True)


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    try:
        return console.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc


@app.post("/api/train")
async def train(request: TrainRequest):
    return console.start_train(
        name=request.name,
        framework=request.framework,
        version=request.version,
        n_samples=request.n_samples,
    )


@app.post("/api/services/{service_id}/predict")
async def predict(service_id: str, request: PredictRequest):
    try:
        return console.predict(
            service_id,
            {
                "prompt": request.prompt,
                "instances": request.instances,
                "messages": request.messages,
            },
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="InferenceService not found") from exc


@app.get("/")
async def index():
    path = os.path.join(FRONTEND, "index.html")
    if os.path.isfile(path):
        return FileResponse(path, headers={"Cache-Control": "no-store"})
    return {"message": "AI/ML Factory Console", "docs": "/docs"}


@app.get("/architecture.png")
async def architecture_png():
    path = os.path.join(ROOT, "architecture.png")
    if os.path.isfile(path):
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="missing architecture.png")


if os.path.isdir(FRONTEND):
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8006)
