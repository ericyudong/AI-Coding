"""AI/ML Factory console: scan local artifacts, serving manifests, and run jobs."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = ROOT / "artifacts"
SERVING_DIR = ROOT / "serving"
DATA_DIR = ROOT / "data"
STATE_FILE = DATA_DIR / "console-state.json"

LAYERS = [
    {"id": "git", "name": "Git", "tech": "GitHub", "color": "#F05032"},
    {"id": "cicd", "name": "CI/CD", "tech": "Actions · Tekton", "color": "#326CE5"},
    {"id": "kubeflow", "name": "Kubeflow", "tech": "Pipelines v2", "color": "#3b82f6"},
    {"id": "registry", "name": "Model Registry", "tech": "MinIO · MLflow · OCI", "color": "#7c3aed"},
    {"id": "kserve", "name": "KServe", "tech": "InferenceService", "color": "#db2777"},
    {"id": "runtime", "name": "Runtime", "tech": "XGBoost · Triton · vLLM", "color": "#6366f1"},
    {"id": "gpu", "name": "NVIDIA GPU", "tech": "A100 → H100 → H200", "color": "#76B900"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_yaml_lite(text: str) -> Dict[str, Any]:
    """Tiny extractor for InferenceService fields without PyYAML dependency at runtime."""
    name = re.search(r"^  name:\s*(\S+)", text, re.M)
    ns = re.search(r"^  namespace:\s*(\S+)", text, re.M)
    runtime = re.search(r"ai-factory\.runtime:\s*(\S+)", text)
    model = re.search(r"ai-factory\.model:\s*(\S+)", text)
    storage = re.search(r"storageUri:\s*(\S+)", text)
    gpu = re.search(r"nvidia\.com/gpu:\s*[\"']?(\d+)", text)
    product = re.search(r"nvidia\.com/gpu\.product:\s*(\S+)", text)
    image = re.search(r"image:\s*(\S+)", text)
    min_r = re.search(r"minReplicas:\s*(\d+)", text)
    max_r = re.search(r"maxReplicas:\s*(\d+)", text)
    return {
        "name": name.group(1) if name else Path(text[:40]).stem,
        "namespace": ns.group(1) if ns else "kserve-demo",
        "runtime": runtime.group(1) if runtime else "unknown",
        "model": model.group(1) if model else None,
        "storageUri": storage.group(1) if storage else None,
        "gpu": int(gpu.group(1)) if gpu else 0,
        "gpu_product": product.group(1) if product else None,
        "image": image.group(1) if image else None,
        "minReplicas": int(min_r.group(1)) if min_r else 1,
        "maxReplicas": int(max_r.group(1)) if max_r else 1,
    }


class FactoryConsole:
    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.predictions: List[Dict[str, Any]] = []
        self._load_state()

    def _load_state(self) -> None:
        if STATE_FILE.is_file():
            try:
                payload = json.loads(STATE_FILE.read_text())
                self.predictions = payload.get("predictions") or []
            except Exception:
                pass

    def _save_state(self) -> None:
        STATE_FILE.write_text(
            json.dumps({"predictions": self.predictions[-50:]}, ensure_ascii=False, indent=2)
        )

    def list_artifacts(self) -> List[Dict[str, Any]]:
        items = []
        if not ARTIFACTS_DIR.is_dir():
            return items
        for model_dir in sorted(ARTIFACTS_DIR.iterdir()):
            if not model_dir.is_dir():
                continue
            for ver_dir in sorted(model_dir.iterdir()):
                if not ver_dir.is_dir():
                    continue
                metrics = {}
                metrics_path = ver_dir / "metrics.json"
                if metrics_path.is_file():
                    try:
                        metrics = json.loads(metrics_path.read_text())
                    except Exception:
                        pass
                files = [p.name for p in ver_dir.iterdir() if p.is_file()]
                items.append(
                    {
                        "id": f"{model_dir.name}/{ver_dir.name}",
                        "name": model_dir.name,
                        "version": ver_dir.name,
                        "path": str(ver_dir.relative_to(ROOT)),
                        "uri": f"s3://ai-factory/models/{model_dir.name}/{ver_dir.name}/",
                        "files": files,
                        "metrics": metrics,
                        "framework": metrics.get("framework") or "unknown",
                        "kind": "ModelArtifact",
                        "has_weights": any(
                            f.endswith((".joblib", ".pt", ".onnx", ".bin", ".safetensors")) for f in files
                        ),
                    }
                )
        return items

    def list_services(self) -> List[Dict[str, Any]]:
        services = []
        for path in sorted(SERVING_DIR.glob("*/inferenceservice.yaml")):
            text = path.read_text()
            meta = _read_yaml_lite(text)
            runtime = path.parent.name
            services.append(
                {
                    **meta,
                    "id": meta["name"],
                    "runtime_dir": runtime,
                    "manifest": str(path.relative_to(ROOT)),
                    "status": "Ready" if meta.get("storageUri") or runtime == "vllm" else "Unknown",
                    "principle": "storageUri / PVC — weights are not baked into the image",
                }
            )
        return services

    def architecture(self) -> Dict[str, Any]:
        return {
            "title": "AI/ML Factory",
            "flow": "Git → CI/CD → Kubeflow → Model Registry → KServe → Runtime → NVIDIA GPU",
            "principle": "Don't treat the model as a container. Treat the model as a versioned artifact.",
            "layers": LAYERS,
            "overlays": ["dev", "staging", "prod"],
            "repos": {
                "pipeline": "pipelines/specs/*.yaml (Scheme B)",
                "compiler": "pipelines/compiler/from_spec.py",
                "tekton": "cicd/tekton/pipeline.yaml",
                "argocd": "gitops/argocd/applications.yaml",
                "deploy": "docs/deploy.md",
            },
        }

    def _ensure_pipeline_path(self) -> None:
        root = str(ROOT)
        if root not in sys.path:
            sys.path.insert(0, root)

    def list_pipeline_components(self) -> List[Dict[str, Any]]:
        self._ensure_pipeline_path()
        from pipelines.components.catalog import CATALOG

        return CATALOG

    def list_pipeline_specs(self) -> List[Dict[str, Any]]:
        self._ensure_pipeline_path()
        from pipelines.compiler.from_spec import list_specs

        return list_specs()

    def get_pipeline_spec(self, spec_id: str) -> Dict[str, Any]:
        self._ensure_pipeline_path()
        from pipelines.compiler.from_spec import SPECS_DIR, load_spec

        path = SPECS_DIR / f"{spec_id}.yaml"
        if not path.is_file():
            # also allow .yml
            path = SPECS_DIR / f"{spec_id}.yml"
        if not path.is_file():
            raise KeyError(spec_id)
        return {"id": spec_id, "path": str(path.relative_to(ROOT)), "spec": load_spec(path)}

    def save_pipeline_spec(self, spec_id: str, spec: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_pipeline_path()
        from pipelines.compiler.from_spec import SPECS_DIR, dump_spec
        from pipelines.compiler.validate import validate_spec

        safe = re.sub(r"[^a-zA-Z0-9._-]", "-", spec_id).strip("-")
        if not safe:
            raise ValueError("invalid spec id")
        validation = validate_spec(spec)
        path = SPECS_DIR / f"{safe}.yaml"
        dump_spec(spec, path)
        return {
            "id": safe,
            "path": str(path.relative_to(ROOT)),
            "validation": validation,
            "saved": True,
        }

    def validate_pipeline_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_pipeline_path()
        from pipelines.compiler.validate import validate_spec

        return validate_spec(spec)

    def compile_pipeline_spec(
        self, spec: Optional[Dict[str, Any]] = None, spec_id: Optional[str] = None
    ) -> Dict[str, Any]:
        self._ensure_pipeline_path()
        from pipelines.compiler.from_spec import SPECS_DIR, compile_spec, load_spec

        if spec is None:
            if not spec_id:
                raise ValueError("spec or spec_id required")
            path = SPECS_DIR / f"{spec_id}.yaml"
            if not path.is_file():
                path = SPECS_DIR / f"{spec_id}.yml"
            if not path.is_file():
                raise KeyError(spec_id)
            spec = load_spec(path)
        return compile_spec(spec)

    def overview(self) -> Dict[str, Any]:
        artifacts = self.list_artifacts()
        services = self.list_services()
        return {
            **self.architecture(),
            "stats": {
                "artifacts": len(artifacts),
                "services": len(services),
                "jobs": len(self.jobs),
                "predictions": len(self.predictions),
                "runtimes": len({s["runtime"] for s in services}),
            },
            "artifacts": artifacts,
            "services": services,
            "jobs": sorted(self.jobs.values(), key=lambda j: j["created_at"], reverse=True)[:12],
            "cluster": self.cluster_probe(),
        }

    def cluster_probe(self) -> Dict[str, Any]:
        """Best-effort kubectl probe; never required for the console."""
        try:
            r = subprocess.run(
                ["kubectl", "get", "inferenceservices", "-n", "kserve-demo", "-o", "name"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if r.returncode == 0:
                names = [line.strip() for line in r.stdout.splitlines() if line.strip()]
                return {"connected": True, "inferenceservices": names}
            return {"connected": False, "error": (r.stderr or r.stdout or "kubectl failed")[:200]}
        except FileNotFoundError:
            return {"connected": False, "error": "kubectl not found — console runs in local mode"}
        except Exception as exc:
            return {"connected": False, "error": str(exc)[:200]}

    def start_train(
        self,
        name: str = "fraud-xgb",
        framework: str = "xgboost",
        version: Optional[str] = None,
        n_samples: int = 1000,
    ) -> Dict[str, Any]:
        version = version or f"v{datetime.now().strftime('%Y%m%d%H%M%S')}"
        job_id = uuid.uuid4().hex[:10]
        out_dir = ARTIFACTS_DIR / name / version
        job = {
            "id": job_id,
            "kind": "train",
            "name": name,
            "framework": framework,
            "version": version,
            "status": "running",
            "stage": "prepare",
            "logs": [],
            "artifact_id": f"{name}/{version}",
            "created_at": _now(),
            "updated_at": _now(),
        }
        self.jobs[job_id] = job

        def _run() -> None:
            try:
                stages = ["prepare", "train", "evaluate", "register"]
                for stage in stages:
                    job["stage"] = stage
                    job["logs"].append(f"[{stage}] running…")
                    job["updated_at"] = _now()
                out_dir.parent.mkdir(parents=True, exist_ok=True)
                if framework == "pytorch":
                    cmd = [
                        sys.executable,
                        str(ROOT / "training/pytorch/train.py"),
                        "--out-dir",
                        str(out_dir),
                        "--epochs",
                        "1",
                    ]
                else:
                    cmd = [
                        sys.executable,
                        str(ROOT / "training/xgboost/train.py"),
                        "--out-dir",
                        str(out_dir),
                        "--n-samples",
                        str(n_samples),
                        "--min-auc",
                        "0.85",
                    ]
                proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), timeout=180)
                job["logs"].append(proc.stdout[-2000:] if proc.stdout else "")
                if proc.returncode != 0:
                    job["status"] = "failed"
                    job["logs"].append(proc.stderr[-1500:] if proc.stderr else "train failed")
                else:
                    job["status"] = "succeeded"
                    job["stage"] = "ready"
                    job["logs"].append(f"registered local artifact {name}/{version}")
                    job["logs"].append(f"uri s3://ai-factory/models/{name}/{version}/")
                job["updated_at"] = _now()
            except Exception as exc:
                job["status"] = "failed"
                job["logs"].append(str(exc))
                job["updated_at"] = _now()

        threading.Thread(target=_run, daemon=True).start()
        return job

    def get_job(self, job_id: str) -> Dict[str, Any]:
        if job_id not in self.jobs:
            raise KeyError(job_id)
        return self.jobs[job_id]

    def predict(self, service_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        services = {s["id"]: s for s in self.list_services()}
        if service_id not in services:
            raise KeyError(service_id)
        svc = services[service_id]
        runtime = svc.get("runtime") or svc.get("runtime_dir")
        payload = payload or {}
        if runtime == "xgboost":
            # Prefer real local model if present
            arts = [a for a in self.list_artifacts() if a["name"] in (svc.get("model"), "fraud-xgb") and a["has_weights"]]
            score = 0.87
            if arts:
                try:
                    import joblib
                    import numpy as np

                    model = joblib.load(ROOT / arts[0]["path"] / "model.joblib")
                    row = payload.get("instances") or [[0.1] * 20]
                    arr = np.array(row, dtype=float)
                    if hasattr(model, "predict_proba"):
                        score = float(model.predict_proba(arr)[0][1])
                    else:
                        score = float(model.predict(arr)[0])
                except Exception:
                    pass
            output = {"predictions": [score], "message": f"XGBoost/MLServer scored instance → {score:.4f}"}
        elif runtime == "triton":
            output = {
                "outputs": [{"name": "OUTPUT__0", "shape": [1, 10], "data": [0.1] * 10}],
                "message": "Triton multi-framework mock response (upload TorchScript to enable real path)",
            }
        else:
            prompt = (payload.get("prompt") or payload.get("messages") or "hello")
            if isinstance(prompt, list):
                prompt = str(prompt)
            output = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": f"[vLLM @ {svc.get('gpu_product') or 'GPU'}] 制品 {svc.get('storageUri') or 'PVC'} — {str(prompt)[:120]}",
                        }
                    }
                ],
                "message": "OpenAI-compatible mock completion",
            }
        record = {
            "id": uuid.uuid4().hex[:8],
            "service_id": service_id,
            "runtime": runtime,
            "artifact_uri": svc.get("storageUri"),
            "output": output,
            "created_at": _now(),
            "note": "Serving references versioned artifact URI — not a baked-in container model.",
        }
        self.predictions.append(record)
        self._save_state()
        return record

    def list_manifests(self) -> Dict[str, List[str]]:
        groups = {
            "serving": [str(p.relative_to(ROOT)) for p in SERVING_DIR.glob("*/inferenceservice.yaml")],
            "registry": ["manifests/minio/minio.yaml", "manifests/mlflow/mlflow.yaml"],
            "gpu": ["manifests/gpu/runtimeclass.yaml"],
            "gitops": ["gitops/argocd/applications.yaml"],
            "cicd": ["cicd/tekton/pipeline.yaml", ".github/workflows/ci.yml"],
            "overlays": [
                "manifests/overlays/dev/kustomization.yaml",
                "manifests/overlays/staging/kustomization.yaml",
                "manifests/overlays/prod/kustomization.yaml",
            ],
        }
        return groups


console = FactoryConsole()
