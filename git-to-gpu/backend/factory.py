"""
Git → CI/CD → Kubeflow → Model Registry → KServe → Runtime → NVIDIA GPU

演示控制面：把模型当作版本化制品（versioned artifact），而不是容器。
本地进程内模拟各层状态，无需真实 Kubeflow / KServe / GPU。
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
STATE_FILE = os.path.join(DATA_DIR, "platform.json")

LAYERS = [
    {
        "id": "git",
        "name": "Git",
        "role": "Version Control",
        "color": "#F05032",
        "summary": "版本控制、模型代码与流水线定义的单一事实来源",
        "contributes": ["代码版本", "可复现提交", "PR / 审查门禁"],
    },
    {
        "id": "cicd",
        "name": "CI/CD",
        "role": "Pipeline Automation",
        "color": "#326CE5",
        "summary": "自动化测试、打包与可复现部署工作流",
        "contributes": ["单元 / 集成测试", "镜像与制品构建", "门禁与发布"],
    },
    {
        "id": "kubeflow",
        "name": "Kubeflow Pipelines",
        "role": "ML Orchestration",
        "color": "#326CE5",
        "summary": "编排数据处理、分布式训练、实验与模型评估",
        "contributes": [
            "Data Processing",
            "Feature Engineering",
            "Model Training",
            "Model Validation",
            "Metrics & Scores",
            "Performance Check",
        ],
        "branches": {
            "training": ["Data Processing", "Feature Engineering", "Model Training"],
            "evaluation": ["Model Validation", "Metrics & Scores", "Performance Check"],
        },
    },
    {
        "id": "registry",
        "name": "Model Registry",
        "role": "Versioned Artifacts",
        "color": "#7C3AED",
        "summary": "以版本化制品存储模型与元数据（S3/MinIO 或 OCI）",
        "contributes": ["模型版本", "元数据与 lineage", "跨环境迁移"],
        "storage": [
            {"id": "s3", "name": "S3 / MinIO", "kind": "Object Storage"},
            {"id": "oci", "name": "OCI Registry", "kind": "OCI Registry"},
        ],
    },
    {
        "id": "kserve",
        "name": "KServe",
        "role": "Kubernetes-native Serving",
        "color": "#EC4899",
        "summary": "K8s 原生模型服务：自动扩缩、灰度发布与推理端点",
        "contributes": ["InferenceService", "Autoscaling", "Canary / Rollout", "统一端点"],
    },
    {
        "id": "runtime",
        "name": "Inference Runtime",
        "role": "Serving Engines",
        "color": "#8B5CF6",
        "summary": "按工作负载选择运行时，模型制品与运行时解耦",
        "runtimes": [
            {
                "id": "xgboost",
                "name": "XGBoost",
                "engine": "MLServer Runtime",
                "tagline": "Fast & Scalable",
                "workload": "Classical ML",
            },
            {
                "id": "triton",
                "name": "Triton",
                "engine": "Multi-Framework",
                "tagline": "High Performance",
                "workload": "Deep Learning",
            },
            {
                "id": "vllm",
                "name": "vLLM",
                "engine": "LLM Inference",
                "tagline": "Efficient & Scalable",
                "workload": "Large Language Models",
            },
        ],
    },
    {
        "id": "gpu",
        "name": "NVIDIA GPU",
        "role": "Accelerator Infrastructure",
        "color": "#76B900",
        "summary": "通过 CUDA 驱动加速器；可按代际升级硬件",
        "cuda_stack": ["CUDA Cores", "Tensor Cores", "HBM", "NVLink"],
        "gpus": [
            {
                "id": "a100",
                "name": "A100",
                "memory": "40GB / 80GB HBM2",
                "tagline": "High Throughput",
                "color": "#76B900",
            },
            {
                "id": "h100",
                "name": "H100",
                "memory": "80GB HBM3",
                "tagline": "Maximum Performance",
                "color": "#326CE5",
            },
            {
                "id": "h200",
                "name": "H200",
                "memory": "141GB HBM3e",
                "tagline": "Next-Gen Performance",
                "color": "#7C3AED",
            },
        ],
    },
]

PRINCIPLE = {
    "title": "Don't treat the model as a container. Treat the model as a versioned artifact.",
    "enables": [
        "在一个 OpenShift / Kubeflow 集群上训练",
        "独立存储模型制品与元数据",
        "跨环境迁移（dev → staging → prod）",
        "通过 KServe 部署，无需重训",
        "按需切换推理运行时（XGBoost / Triton / vLLM）",
        "针对不同 NVIDIA GPU 代际优化",
    ],
    "next": [
        "GPU observability",
        "Cost attribution",
        "Multi-tenancy",
        "Model performance SLOs",
        "FinOps",
    ],
}

DEMO_MODELS = [
    {
        "name": "fraud-xgb",
        "framework": "xgboost",
        "runtime": "xgboost",
        "gpu": None,
        "metrics": {"auc": 0.941, "f1": 0.89},
    },
    {
        "name": "vision-resnet",
        "framework": "pytorch",
        "runtime": "triton",
        "gpu": "a100",
        "metrics": {"top1": 0.782, "latency_ms": 12.4},
    },
    {
        "name": "assist-llm",
        "framework": "transformers",
        "runtime": "vllm",
        "gpu": "h100",
        "metrics": {"perplexity": 8.2, "tokens_per_s": 1840},
    },
]

STAGE_ORDER = [
    "git",
    "cicd",
    "kubeflow_train",
    "kubeflow_eval",
    "registry",
    "kserve",
    "runtime",
    "gpu",
    "ready",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Platform:
    def __init__(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        self.artifacts: Dict[str, Dict[str, Any]] = {}
        self.services: Dict[str, Dict[str, Any]] = {}
        self.runs: Dict[str, Dict[str, Any]] = {}
        self.stats = {"commits": 0, "pipeline_runs": 0, "artifacts": 0, "inferences": 0}
        self._lock = threading.Lock()
        self._load_or_seed()

    def _load_or_seed(self) -> None:
        if os.path.isfile(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                for item in payload.get("artifacts", []):
                    self.artifacts[item["id"]] = item
                for item in payload.get("services", []):
                    self.services[item["id"]] = item
                self.stats = payload.get("stats") or self.stats
                if self.artifacts:
                    return
            except Exception:
                pass
        self.seed_demo()

    def _save(self) -> None:
        with open(STATE_FILE, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "artifacts": list(self.artifacts.values()),
                    "services": list(self.services.values()),
                    "stats": self.stats,
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )

    def architecture(self) -> Dict[str, Any]:
        return {
            "title": "From Git Commit to NVIDIA GPU",
            "subtitle": "What a Production AI/ML Platform Actually Looks Like",
            "flow": "Git → CI/CD → Kubeflow → Model Registry → KServe → Inference Runtime → NVIDIA GPU",
            "layers": LAYERS,
            "principle": PRINCIPLE,
            "stats": {**self.stats, "services": len(self.services), "runs": len(self.runs)},
        }

    def seed_demo(self) -> List[Dict[str, Any]]:
        created = []
        for spec in DEMO_MODELS:
            art = self._make_artifact(
                name=spec["name"],
                framework=spec["framework"],
                runtime=spec["runtime"],
                gpu=spec["gpu"],
                metrics=spec["metrics"],
                storage="s3" if spec["runtime"] != "vllm" else "oci",
                status="registered",
            )
            svc = self._make_service(art, runtime=spec["runtime"], gpu=spec["gpu"] or "a100")
            created.append({"artifact": art, "service": svc})
        self.stats["commits"] = max(self.stats["commits"], 12)
        self.stats["pipeline_runs"] = max(self.stats["pipeline_runs"], 3)
        self.stats["artifacts"] = len(self.artifacts)
        self._save()
        return created

    def _make_artifact(
        self,
        name: str,
        framework: str,
        runtime: str,
        gpu: Optional[str],
        metrics: Dict[str, Any],
        storage: str = "s3",
        status: str = "registered",
        commit: Optional[str] = None,
    ) -> Dict[str, Any]:
        version = f"v{len([a for a in self.artifacts.values() if a['name'] == name]) + 1}.0.0"
        art_id = uuid.uuid4().hex[:10]
        commit = commit or uuid.uuid4().hex[:7]
        uri = (
            f"s3://ai-factory/models/{name}/{version}/model.bin"
            if storage == "s3"
            else f"oci://registry.local/models/{name}:{version}"
        )
        artifact = {
            "id": art_id,
            "name": name,
            "version": version,
            "kind": "ModelArtifact",
            "framework": framework,
            "preferred_runtime": runtime,
            "preferred_gpu": gpu,
            "storage": storage,
            "uri": uri,
            "commit": commit,
            "metrics": metrics,
            "status": status,
            "lineage": {
                "git": f"main@{commit}",
                "pipeline": f"kf-run-{art_id[:6]}",
                "trained_on": "kubeflow-cluster",
                "evaluated": True,
            },
            "created_at": _now(),
            "note": "Versioned artifact — not a container image",
        }
        self.artifacts[art_id] = artifact
        self.stats["artifacts"] = len(self.artifacts)
        return artifact

    def _make_service(
        self,
        artifact: Dict[str, Any],
        runtime: Optional[str] = None,
        gpu: Optional[str] = None,
    ) -> Dict[str, Any]:
        runtime = runtime or artifact["preferred_runtime"]
        gpu = gpu or artifact.get("preferred_gpu") or ("h100" if runtime == "vllm" else "a100")
        svc_id = uuid.uuid4().hex[:10]
        service = {
            "id": svc_id,
            "name": f"{artifact['name']}-isvc",
            "kind": "InferenceService",
            "artifact_id": artifact["id"],
            "artifact_uri": artifact["uri"],
            "artifact_version": artifact["version"],
            "runtime": runtime,
            "gpu": gpu if runtime != "xgboost" else None,
            "endpoint": f"http://{artifact['name']}.kserve.svc/v1/models/{artifact['name']}:predict",
            "status": "Ready",
            "replicas": 1 if runtime == "xgboost" else 2,
            "created_at": _now(),
        }
        self.services[svc_id] = service
        return service

    def list_artifacts(self) -> List[Dict[str, Any]]:
        return sorted(self.artifacts.values(), key=lambda x: x["created_at"], reverse=True)

    def list_services(self) -> List[Dict[str, Any]]:
        rows = []
        for svc in self.services.values():
            art = self.artifacts.get(svc["artifact_id"])
            rows.append({**svc, "artifact_name": (art or {}).get("name"), "framework": (art or {}).get("framework")})
        return sorted(rows, key=lambda x: x["created_at"], reverse=True)

    def list_runs(self) -> List[Dict[str, Any]]:
        return sorted(self.runs.values(), key=lambda x: x["created_at"], reverse=True)

    def start_run(
        self,
        name: str = "assist-llm",
        runtime: str = "vllm",
        gpu: str = "h100",
        storage: str = "oci",
        framework: str = "transformers",
    ) -> Dict[str, Any]:
        run_id = uuid.uuid4().hex[:10]
        commit = uuid.uuid4().hex[:7]
        run = {
            "id": run_id,
            "name": name,
            "runtime": runtime,
            "gpu": gpu,
            "storage": storage,
            "framework": framework,
            "commit": commit,
            "status": "running",
            "stage": "git",
            "stages": {s: {"status": "pending", "message": ""} for s in STAGE_ORDER},
            "artifact_id": None,
            "service_id": None,
            "logs": [],
            "created_at": _now(),
            "updated_at": _now(),
        }
        self.runs[run_id] = run
        self.stats["commits"] += 1
        self.stats["pipeline_runs"] += 1
        thread = threading.Thread(target=self._execute_run, args=(run_id,), daemon=True)
        thread.start()
        return run

    def _log(self, run: Dict[str, Any], message: str) -> None:
        run["logs"].append({"t": _now(), "msg": message})
        run["updated_at"] = _now()

    def _set_stage(self, run: Dict[str, Any], stage: str, status: str, message: str) -> None:
        run["stage"] = stage
        run["stages"][stage] = {"status": status, "message": message}
        self._log(run, f"[{stage}] {message}")

    def _execute_run(self, run_id: str) -> None:
        run = self.runs[run_id]
        try:
            steps = [
                ("git", "检出提交 main@{commit}，锁定流水线定义"),
                ("cicd", "CI 门禁通过：lint / unit / package"),
                ("kubeflow_train", "Kubeflow：Data Processing → Feature Engineering → Model Training"),
                ("kubeflow_eval", "Kubeflow：Validation → Metrics → Performance Check"),
                ("registry", "注册版本化制品到 {storage}（非容器镜像）"),
                ("kserve", "创建 InferenceService，引用制品 URI"),
                ("runtime", "绑定推理运行时 {runtime}"),
                ("gpu", "调度到 NVIDIA {gpu}（CUDA Cores → Tensor Cores → HBM → NVLink）"),
                ("ready", "端点 Ready，可承接推理流量"),
            ]
            for stage, template in steps:
                self._set_stage(run, stage, "running", "进行中…")
                time.sleep(0.55)
                msg = template.format(
                    commit=run["commit"],
                    storage=run["storage"].upper(),
                    runtime=run["runtime"],
                    gpu=(run["gpu"] or "CPU").upper(),
                )
                self._set_stage(run, stage, "done", msg)

                if stage == "registry":
                    metrics = {
                        "vllm": {"perplexity": 7.9, "tokens_per_s": 1920},
                        "triton": {"top1": 0.79, "latency_ms": 11.2},
                        "xgboost": {"auc": 0.95, "f1": 0.91},
                    }.get(run["runtime"], {"score": 0.9})
                    art = self._make_artifact(
                        name=run["name"],
                        framework=run["framework"],
                        runtime=run["runtime"],
                        gpu=run["gpu"],
                        metrics=metrics,
                        storage=run["storage"],
                        commit=run["commit"],
                    )
                    run["artifact_id"] = art["id"]
                if stage == "kserve":
                    art = self.artifacts[run["artifact_id"]]
                    svc = self._make_service(art, runtime=run["runtime"], gpu=run["gpu"])
                    run["service_id"] = svc["id"]

            run["status"] = "succeeded"
            self._log(run, "流水线完成：模型作为版本化制品已上线")
            self._save()
        except Exception as exc:
            run["status"] = "failed"
            self._set_stage(run, run.get("stage") or "git", "failed", str(exc))

    def get_run(self, run_id: str) -> Dict[str, Any]:
        if run_id not in self.runs:
            raise KeyError(run_id)
        run = self.runs[run_id]
        art = self.artifacts.get(run.get("artifact_id") or "")
        svc = self.services.get(run.get("service_id") or "")
        return {**run, "artifact": art, "service": svc}

    def deploy_artifact(self, artifact_id: str, runtime: Optional[str] = None, gpu: Optional[str] = None) -> Dict[str, Any]:
        if artifact_id not in self.artifacts:
            raise KeyError(artifact_id)
        art = self.artifacts[artifact_id]
        return self._make_service(art, runtime=runtime, gpu=gpu)

    def migrate_artifact(self, artifact_id: str, target_storage: str) -> Dict[str, Any]:
        if artifact_id not in self.artifacts:
            raise KeyError(artifact_id)
        if target_storage not in ("s3", "oci"):
            raise ValueError("target_storage 必须是 s3 或 oci")
        art = self.artifacts[artifact_id]
        name, version = art["name"], art["version"]
        if target_storage == "s3":
            art["uri"] = f"s3://ai-factory/models/{name}/{version}/model.bin"
        else:
            art["uri"] = f"oci://registry.local/models/{name}:{version}"
        art["storage"] = target_storage
        art["migrated_at"] = _now()
        self._save()
        return art

    def infer(self, service_id: str, prompt: str = "hello") -> Dict[str, Any]:
        if service_id not in self.services:
            raise KeyError(service_id)
        svc = self.services[service_id]
        art = self.artifacts.get(svc["artifact_id"]) or {}
        self.stats["inferences"] += 1
        runtime = svc["runtime"]
        if runtime == "vllm":
            content = f"[vLLM @ {svc.get('gpu')}] 基于制品 {art.get('uri')} 生成：{prompt[:120]}"
        elif runtime == "triton":
            content = f"[Triton @ {svc.get('gpu')}] 多框架推理完成，输入长度={len(prompt)}"
        else:
            content = f"[XGBoost/MLServer] 经典 ML 预测 score=0.87，输入={prompt[:80]}"
        return {
            "service_id": service_id,
            "runtime": runtime,
            "gpu": svc.get("gpu"),
            "artifact_uri": svc["artifact_uri"],
            "artifact_version": svc["artifact_version"],
            "output": content,
            "latency_ms": 8.2 if runtime == "xgboost" else (14.5 if runtime == "triton" else 42.0),
            "principle": "Serving references the versioned artifact URI — not a baked-in container model.",
        }

    def overview(self) -> Dict[str, Any]:
        return {
            **self.architecture(),
            "artifacts": self.list_artifacts(),
            "services": self.list_services(),
            "runs": self.list_runs()[:8],
        }


platform = Platform()
