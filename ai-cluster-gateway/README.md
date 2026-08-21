# AI Cluster Gateway

把客户端的 OpenAI 兼容请求**路由到不同的推理 Kubernetes 集群**，并在网关里把模型**部署到指定 ManagedCluster**。

多集群控制面与 [k8s-cluster-explorer](../k8s-cluster-explorer/README.md) **共用同一套 CNCF OCM 对象**（同一份 `ocm-hub.json`）：

- **ManagedCluster**：join / Accept 双向握手
- **ManifestWork**：模型 Deployment + Service 由 work-agent pull
- **Placement** `gpu-inference`：按 GPU ClusterClaim 选出可部署集群

与仓库中的 [AIGateway](../AIGateway/README.md)（LiteLLM + 护栏）互补：本项目管的是 **OCM 放置与流量调度**，而不是内容安全策略。

## 能力

- **数据面**: `POST /v1/chat/completions`、`GET /v1/models`
- **路由**: 模型别名、权重、failover；请求头 `X-Cluster-Id`（ManagedCluster 名）/ `X-Region` 可钉死目标
- **控制面**: Join / Accept / Deny；未接受集群不能部署、不能承接推理
- **演示模式**: 三个 Available 推理集群（prod / staging / edge）+ 待批准 `kind-dev` + 预置模型

## 架构

```
Client ──OpenAI /v1──► AI Cluster Gateway ── PlacementDecision ──► ManagedCluster
                          │
                          └─ ManifestWork (inference ns) ── pull ──► Klusterlet / spoke

共享 Hub 状态: k8s-cluster-explorer/data/ocm-hub.json
```

默认路由：

| 公开 model | 策略 | 主后端 | 备后端 |
|---|---|---|---|
| `default` | weighted | qwen2-7b @ staging-cn-shanghai | qwen2-1.5b @ edge-us-west |
| `reasoning` | failover | qwen2-72b @ prod-cn-shanghai | llama3-70b @ prod-cn-shanghai |
| `fast` | failover | qwen2-1.5b @ edge-us-west | qwen2-7b @ staging-cn-shanghai |

## 快速开始

```bash
cd ai-cluster-gateway
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python backend/main.py
```

打开 [http://localhost:8004](http://localhost:8004)

```bash
curl http://localhost:8004/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"reasoning","messages":[{"role":"user","content":"你好"}]}'
```

钉死 ManagedCluster：

```bash
curl http://localhost:8004/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Cluster-Id: staging-cn-shanghai" \
  -d '{"model":"qwen2-7b","messages":[{"role":"user","content":"ping"}]}'
```

可选环境变量：

- `GATEWAY_API_KEY`：设置后需 `Authorization: Bearer ...`
- `OCM_HUB_FILE`：覆盖共享 Hub 状态路径（默认指向 explorer 的 `data/ocm-hub.json`）

## 在网关部署模型

控制台「部署模型」页（只列出已 Accept 的集群），或：

```bash
curl -X POST http://localhost:8004/api/models/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "alias": "qwen2-7b-extra",
    "model_id": "Qwen/Qwen2-7B-Instruct",
    "cluster_id": "staging-cn-shanghai",
    "replicas": 1,
    "gpu": 1,
    "runtime": "vllm",
    "add_to_route": "default"
  }'
```

这会在该集群的 Hub namespace 创建 **ManifestWork**。演示集群立即变成 `mock://` 后端；真实集群用 kubeconfig 在 `inference` 命名空间创建 Deployment + Service。

GPU 不足或不在 Placement `gpu-inference` 决策中时，部署会被拒绝。

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /v1/chat/completions | OpenAI 聊天 |
| GET | /v1/models | 公开模型列表 |
| GET | /api/hub | 共享 OCM Hub 计数 |
| GET | /api/overview | 集群 + 部署 + Placement + Work + 统计 |
| GET | /api/clusters | ManagedCluster 列表（含 GPU 占用） |
| POST | /api/clusters | clusteradm join（默认不自动接受） |
| POST | /api/managedclusters/{name}/accept | 设置 hubAcceptsClient |
| POST | /api/managedclusters/{name}/deny | 拒绝接入 |
| GET | /api/manifestworks | 模型 / 其它 Work |
| GET | /api/placements | Placement + PlacementDecision |
| GET | /api/placement?gpu=1 | 按 gpu-inference Placement 推荐 |
| POST | /api/models/deploy | 下发 ManifestWork |

## 项目结构

```
ai-cluster-gateway/
├── backend/
│   ├── main.py        # FastAPI：控制面 + /v1
│   ├── clusters.py    # OCM ManagedCluster 适配（共享 Hub）
│   ├── catalog.py     # 部署 / 路由 / 统计
│   ├── deployer.py    # ManifestWork + K8s 清单
│   ├── router.py      # 只路由到已接受集群
│   └── inference.py   # mock 与 HTTP 转发
├── frontend/index.html
└── README.md
```
