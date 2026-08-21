# AI/ML Factory — 模块技术实现与代码对照

本文档按架构流水线逐层说明：**技术实现要点**、**对应代码 / 清单**、以及模块之间如何衔接。

```
Git → CI/CD → Kubeflow → Model Registry → KServe → Inference Runtime → NVIDIA GPU
```

核心原则贯穿每一层：

> **Don't treat the model as a container. Treat the model as a versioned artifact.**

---

## 0. 总览：目录 → 架构层

| 架构层 | 主要目录 / 文件 | 运行时角色 |
|--------|-----------------|------------|
| Git + CI/CD | `.github/workflows/`、`cicd/tekton/` | 门禁、编译 Pipeline、校验 Kustomize |
| Kubeflow | `pipelines/`、`training/` | 数据处理、训练、评估门禁、注册 |
| Model Registry | `registry/`、`manifests/minio/`、`manifests/mlflow/`、`artifacts/` | 版本化制品存储与元数据 |
| KServe | `serving/*/inferenceservice.yaml` | Kubernetes 原生推理服务 |
| Inference Runtime | XGBoost / Triton / vLLM 清单与 model repo | 执行引擎 |
| NVIDIA GPU | `manifests/gpu/`、overlays 的 `nodeSelector` | 加速器调度与配额 |
| GitOps | `gitops/argocd/`、`manifests/overlays/` | 环境差异与持续交付 |
| 控制台 | `console/`、`frontend/` | 本地操作面（:8006） |
| 测试 | `tests/` | 原则与训练冒烟 |

部署步骤见 [deploy.md](./deploy.md)。制品目录约定见 [../registry/ARTIFACT_LAYOUT.md](../registry/ARTIFACT_LAYOUT.md)。

---

## 1. Git + CI/CD

### 技术实现

- **Git**：训练代码、Pipeline DSL、Serving 清单与 overlays 同仓版本化；变更可审计、可回滚。
- **GitHub Actions**：PR/推送时跑单元测试、本地训练冒烟、编译 KFP YAML、`kustomize build` 校验各环境。
- **Tekton**：集群内 CI Pipeline（clone → pytest/train → build image → compile KFP），与仓库 [k8sdevops](../../k8sdevops/) 的 Tekton 任务风格对齐。

CI 不把模型权重 bake 进镜像；镜像只承载训练/流水线 worker。

### 对应代码

| 文件 | 作用 |
|------|------|
| [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | GitHub Actions：pytest、train smoke、KFP compile、kustomize |
| [`cicd/tekton/pipeline.yaml`](../cicd/tekton/pipeline.yaml) | Tekton Pipeline：`unit-train-smoke`、`build-image`、`compile-kfp` |
| [`training/Dockerfile`](../training/Dockerfile) | 训练/流水线 worker 镜像（CPU 基座） |

### 衔接

CI 通过后 → 可提交 Kubeflow Pipeline / 由 Argo CD 同步 overlays；制品仍由训练步骤写入 Registry，而不是 CI 镜像层。

---

## 2. Kubeflow Pipelines（训练编排）— 方案 B

### 在系统中的位置

可编辑 **Pipeline Spec（YAML DAG）** + **组件库** → `from_spec` 编译为 KFP IR → 上传 Kubeflow 执行。

```text
UI / specs/*.yaml  →  validate  →  from_spec.build  →  compiled/*.yaml  →  KFP
```

组件链（默认 `fraud-default`）：

```text
prepare_data → train_model → evaluate_model → register_artifact
```

- **拓扑 / 超参 / 开关**：改 `pipelines/specs/*.yaml`（或控制台「Pipeline 编辑」），再编译。
- **组件实现（Python 逻辑）**：改 `pipelines/components/library.py`（Git 提交后重新编译）。

### 关键文件

| 路径 | 作用 |
|---|---|
| [`pipelines/specs/fraud-default.yaml`](../pipelines/specs/fraud-default.yaml) | 默认可编辑 DAG（与原硬编码流水线等价） |
| [`pipelines/specs/train-only.yaml`](../pipelines/specs/train-only.yaml) | 示例：关闭 register |
| [`pipelines/components/catalog.py`](../pipelines/components/catalog.py) | 组件元数据（校验 / UI，不依赖 kfp） |
| [`pipelines/components/library.py`](../pipelines/components/library.py) | `@dsl.component` 实现 |
| [`pipelines/compiler/validate.py`](../pipelines/compiler/validate.py) | 无环、引用、门禁规则 |
| [`pipelines/compiler/from_spec.py`](../pipelines/compiler/from_spec.py) | Spec → KFP IR |
| [`pipelines/compiled/`](../pipelines/compiled/) | 编译产物 |
| [`pipelines/train_register_pipeline.py`](../pipelines/train_register_pipeline.py) | CLI 入口：编译默认 spec |
| [`training/xgboost/train.py`](../training/xgboost/train.py) | 本地 / Console 训练入口（非 KFP） |
| [`console/`](../console/) | `GET/PUT /api/pipelines/specs`、`POST …/validate|compile` |

### CLI

```bash
python -m pipelines.compiler --list
python -m pipelines.compiler fraud-default
# → pipelines/compiled/ai-ml-factory-train-register.yaml
```

### 门禁规则

- `register_artifact` 启用时必须启用 `evaluate_model`（除非 `allow_skip_evaluate: true`，仅非生产）。
- `evaluate_model` 内 AUC < `min_auc` 会失败，注册步骤拒绝 `passed=false`。

### 本地对照

| 文件 | 作用 |
|---|---|
| [`console/catalog.py`](../console/catalog.py) `start_train()` | 控制台触发本地训练子进程（「训练 / Kubeflow」页） |
| [`training/xgboost/train.py`](../training/xgboost/train.py) | 本地/CI 经典 ML；无 libomp 时回退 HistGBDT |
| [`training/pytorch/train.py`](../training/pytorch/train.py) | 导出 TorchScript，供 Triton |
| [`training/Dockerfile`](../training/Dockerfile) | 容器化训练入口 |

评估通过 → `register_artifact` 写入 `s3://ai-factory/models/<name>/<version>/` 与 MLflow；失败则不写 Registry。

---

## 3. Model Registry（版本化制品）

### 技术实现

- **MinIO**：S3 兼容对象存储，bucket `ai-factory`。  
- **MLflow**：Tracking + Model Registry，artifact root 指向 `s3://ai-factory/mlflow`。  
- **OCI（可选）**：`serving/vllm` 中的 oras sync Job，把 `oci://…/model:semver` 拉到 PVC。  
- **布局约定**：`s3://ai-factory/models/<name>/<semver>/` 含权重 + `metrics.json` + 可选 `MLmodel`。

明确禁止：把权重塞进 Serving 镜像层。

### 对应代码

| 文件 | 作用 |
|------|------|
| [`manifests/minio/minio.yaml`](../manifests/minio/minio.yaml) | MinIO Deployment/Service/Secret + bootstrap bucket Job |
| [`manifests/mlflow/mlflow.yaml`](../manifests/mlflow/mlflow.yaml) | MLflow server，SQLite backend + S3 artifact root |
| [`registry/scripts/upload_artifact.py`](../registry/scripts/upload_artifact.py) | 本地目录同步到 MinIO/S3 |
| [`registry/ARTIFACT_LAYOUT.md`](../registry/ARTIFACT_LAYOUT.md) | 制品目录规范 |
| [`pipelines/components/library.py`](../pipelines/components/library.py) `register_artifact` | Pipeline 内上传 + `mlflow.register_model` |
| [`artifacts/`](../artifacts/) | 本地 Registry 镜像目录（控制台扫描） |
| [`console/catalog.py`](../console/catalog.py) `list_artifacts()` | 扫描 `artifacts/**` 暴露给 UI |

### 衔接

Registry URI → 写入 KServe `storageUri` 或 PVC；Serving 只引用版本，不持有训练逻辑。

---

## 4. KServe（Kubernetes 原生 Serving）

### 技术实现

- CRD：`serving.kserve.io/v1beta1` **InferenceService**  
- 模式：`RawDeployment`（便于与 GPU Operator / 自定义容器共存）  
- 扩缩：`minReplicas` / `maxReplicas`；Triton 示例带 concurrency 缩放字段  
- 凭据：S3 ServiceAccount 注解 + Secret（MinIO endpoint）  
- 原则：`storageUri` 或 PVC 指向**具体版本路径**

### 对应代码

| 文件 | 作用 |
|------|------|
| [`serving/xgboost/inferenceservice.yaml`](../serving/xgboost/inferenceservice.yaml) | 经典 ML ISVC + `storageUri` + S3 SA |
| [`serving/triton/inferenceservice.yaml`](../serving/triton/inferenceservice.yaml) | Triton ISVC + GPU requests + A100 nodeSelector |
| [`serving/vllm/inferenceservice.yaml`](../serving/vllm/inferenceservice.yaml) | vLLM 自定义容器 + PVC + OCI sync Job |
| [`manifests/base/kustomization.yaml`](../manifests/base/kustomization.yaml) | 聚合 namespaces、registry、gpu、三条 ISVC |
| [`console/catalog.py`](../console/catalog.py) `list_services()` / `predict()` | 解析 ISVC YAML；本地试推理 |
| [`frontend/index.html`](../frontend/index.html) KServe Tab | 展示服务并调用 `/api/services/{id}/predict` |

### 衔接

同一制品可换 Runtime 清单（换 YAML，不重训）；环境差异由 overlays 改副本与 GPU 代际。

---

## 5. Inference Runtimes

### 技术实现

| Runtime | 适用负载 | 制品形态 | 技术要点 |
|---------|----------|----------|----------|
| **XGBoost / MLServer** | 经典表格 ML | `model.joblib` + metrics | KServe `modelFormat: xgboost`，无 GPU |
| **NVIDIA Triton** | 多框架 DL | TorchScript / ONNX 等 + `config.pbtxt` | `modelFormat: triton`，GPU×1，A100 |
| **vLLM** | LLM | 权重目录 / OCI | OpenAI 兼容 HTTP；H100/H200；`--gpu-memory-utilization` |

### 对应代码

| 文件 | 作用 |
|------|------|
| [`serving/xgboost/inferenceservice.yaml`](../serving/xgboost/inferenceservice.yaml) | XGBoost 路径 |
| [`serving/triton/inferenceservice.yaml`](../serving/triton/inferenceservice.yaml) | Triton 路径 |
| [`serving/triton/model-repository/resnet/config.pbtxt`](../serving/triton/model-repository/resnet/config.pbtxt) | Triton 模型配置 |
| [`serving/triton/model-repository/resnet/1/`](../serving/triton/model-repository/resnet/1/) | 放置 `model.pt`（由 pytorch 训练导出） |
| [`serving/vllm/inferenceservice.yaml`](../serving/vllm/inferenceservice.yaml) | vLLM 镜像、参数、PVC、oras Job |
| [`training/pytorch/train.py`](../training/pytorch/train.py) | 导出 Triton 可用的 TorchScript |

### 衔接

Runtime 只消费 Registry 中的版本；CUDA 栈与卡型由 GPU 层 nodeSelector / Operator 提供。

---

## 6. NVIDIA GPU 基础设施

### 技术实现

- **RuntimeClass** `nvidia`：容器使用 NVIDIA container runtime。  
- **nodeSelector**：`nvidia.com/gpu.product` 区分 A100 / H100 / H200。  
- **tolerations**：`nvidia.com/gpu` NoSchedule。  
- **ResourceQuota**：命名空间级 GPU 上限，便于多租户 / FinOps。  
- **Capacity profile ConfigMap**：文档化 CUDA Cores → Tensor Cores → HBM → NVLink。  
- 生产集群需另行安装 **NVIDIA GPU Operator**（本仓库不捆绑 Operator）。

### 对应代码

| 文件 | 作用 |
|------|------|
| [`manifests/gpu/runtimeclass.yaml`](../manifests/gpu/runtimeclass.yaml) | RuntimeClass、GPU profile、ResourceQuota |
| [`manifests/overlays/dev/kustomization.yaml`](../manifests/overlays/dev/kustomization.yaml) | vLLM → A100，`minReplicas=0` |
| [`manifests/overlays/staging/kustomization.yaml`](../manifests/overlays/staging/kustomization.yaml) | vLLM → H100；XGBoost 扩副本 |
| [`manifests/overlays/prod/kustomization.yaml`](../manifests/overlays/prod/kustomization.yaml) | vLLM → H200；提高 GPU quota |
| Triton / vLLM ISVC | `resources.limits.nvidia.com/gpu` + nodeSelector |

### 衔接

换代际 = 改 overlay / selector，**不改模型制品**；监控与成本见下一节。

---

## 7. GitOps 与环境 overlays

### 技术实现

- **Kustomize**：base 定义完整栈；dev/staging/prod patch 副本、GPU 产品、quota。  
- **Argo CD**：`AppProject` + staging 自动同步、prod 手动同步策略。

### 对应代码

| 文件 | 作用 |
|------|------|
| [`manifests/base/namespaces.yaml`](../manifests/base/namespaces.yaml) | `ai-factory` / `ml-registry` / `kserve-demo` |
| [`manifests/base/kustomization.yaml`](../manifests/base/kustomization.yaml) | 资源聚合 |
| [`manifests/overlays/{dev,staging,prod}/`](../manifests/overlays/) | 环境差异 |
| [`gitops/argocd/applications.yaml`](../gitops/argocd/applications.yaml) | Argo CD Application / AppProject |

### 衔接

Git 合并 → Argo CD 同步目标 overlay → 集群上的 MinIO/MLflow/KServe/GPU 配置与清单一致。

---

## 8. 可观测性与 FinOps（演进层）

### 技术实现

当前为**占位 + 约定**，对应文中「下一步演进」：

- ServiceMonitor 抓取 vLLM `/metrics`  
- ConfigMap 记录 DCGM / OpenCost / SLO 方向（p95、tokens/s、$/1k tokens）  
- InferenceService labels：`ai-factory.model` / `ai-factory.runtime` 便于按模型归因

### 对应代码

| 文件 | 作用 |
|------|------|
| [`manifests/monitoring/servicemonitor.yaml`](../manifests/monitoring/servicemonitor.yaml) | Prometheus Operator ServiceMonitor + FinOps 说明 |
| ISVC `metadata.labels` | 模型 / runtime 标签 |
| [`manifests/gpu/runtimeclass.yaml`](../manifests/gpu/runtimeclass.yaml) ResourceQuota | GPU 容量上限 |

---

## 9. 控制台（Console UI + API）

### 技术实现

- **FastAPI** 控制面：扫描本地制品与 Serving YAML，触发训练，模拟/本地推理。  
- **前端**：架构 / 训练 / Registry / KServe / 清单五个 Tab。  
- **可选**：`kubectl get inferenceservices -n kserve-demo` 探测真实集群。  
- 控制台**不替代** Kubeflow/KServe；是仓库与本地 smoke 的操作面。

### 对应代码

| 文件 | 作用 |
|------|------|
| [`console/main.py`](../console/main.py) | FastAPI 路由，端口 **8006** |
| [`console/catalog.py`](../console/catalog.py) | 制品扫描、ISVC 解析、训练 Job、predict、cluster probe |
| [`frontend/index.html`](../frontend/index.html) | 控制台 UI |
| [`architecture.png`](../architecture.png) | 架构参考图（UI 顶部展示） |

### 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/overview` | 架构 + 制品 + 服务 + 任务 + 集群探测 |
| POST | `/api/train` | 启动本地训练 Job |
| GET | `/api/jobs/{id}` | 训练日志 / 状态 |
| GET | `/api/artifacts` | 版本化制品列表 |
| GET | `/api/services` | InferenceService 清单视图 |
| POST | `/api/services/{id}/predict` | 试推理 |
| GET | `/api/manifests` | 清单路径分组 |

启动：`python console/main.py` → http://localhost:8006

---

## 10. 测试

### 技术实现

- 原则测试：Serving 必须含 `storageUri`；README 强调 versioned artifact。  
- 训练测试：写出 `model.joblib`、`metrics.json`、`MLmodel`。

### 对应代码

| 文件 | 作用 |
|------|------|
| [`tests/test_principle.py`](../tests/test_principle.py) | 制品原则与 storageUri 断言 |
| [`tests/test_train_xgboost.py`](../tests/test_train_xgboost.py) | 训练冒烟 |
| [`tests/conftest.py`](../tests/conftest.py) | 将项目根加入 `sys.path` |

---

## 11. 端到端数据流（模块协作）

```text
[开发者] git push
    │
    ▼
[CI] .github / Tekton
    │  pytest + train smoke + kustomize + compile KFP
    ▼
[Kubeflow] pipelines/specs + pipelines/compiler/from_spec.py
    │  prepare → train → evaluate(gate) → register
    ▼
[Registry] MinIO s3://ai-factory/models/<name>/<ver>/
         + MLflow Model Registry
    │
    ▼
[GitOps] Argo CD sync manifests/overlays/<env>
    │
    ▼
[KServe] InferenceService (storageUri / PVC)
    │
    ├── XGBoost runtime  (CPU)
    ├── Triton runtime   (A100…)
    └── vLLM runtime     (H100 / H200)
            │
            ▼
      [NVIDIA GPU Operator + RuntimeClass]
```

本地捷径（无集群）：

```text
console「训练」→ training/*.py → artifacts/
console「KServe」→ catalog.predict() → 读 joblib / 模拟 Triton·vLLM
```

---

## 12. 与姊妹项目的边界

| 项目 | 关系 |
|------|------|
| [git-to-gpu](../../git-to-gpu/) | 同架构的**叙事演示**（进程内状态机）；本仓库是**可部署工程 + 控制台** |
| [k8sdevops](../../k8sdevops/) | 通用 Tekton + Argo CD；本仓库 CI/GitOps 可与其对齐 |
| [ai-cluster-gateway](../../ai-cluster-gateway/) | 多集群推理路由；可把本仓库 KServe 端点作为后端 |
| [gpu-allocator](../../gpu-allocator/) | 卡级分配 UI；本仓库侧重 Serving 侧 GPU 声明与配额 |

---

## 13. 快速索引（按文件找职责）

| 想了解… | 先看 |
|---------|------|
| KFP 如何门禁注册 | `pipelines/components/library.py` → `evaluate_model` / `register_artifact` |
| 制品目录长什么样 | `registry/ARTIFACT_LAYOUT.md`、`artifacts/` |
| KServe 如何引用制品 | `serving/*/inferenceservice.yaml` 的 `storageUri` |
| 如何换 GPU 代际 | `manifests/overlays/*/kustomization.yaml` |
| 控制台怎么扫清单 | `console/catalog.py` |
| 如何上集群 | `docs/deploy.md` |
| CI 校验什么 | `.github/workflows/ci.yml` |
