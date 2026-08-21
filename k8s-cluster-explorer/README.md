# OCM Multi-Cluster Hub

基于 [CNCF Open Cluster Management](https://open-cluster-management.io/) 的 **Hub–Spoke** 多集群控制面演示。

不再把「Hub 持有各集群 kubeconfig 并主动 push」作为核心模型，而是对齐 OCM：

- **Hub**：ClusterManager，保存 `ManagedCluster` / `ManifestWork` / `Placement`
- **Klusterlet**：在 spoke 上 **pull** 注册结果与 Work（本仓库用进程内 agent 模拟）
- **双向 opt-in**：join 只创建未接受的 ManagedCluster；Hub 设置 `spec.hubAcceptsClient` 后才 Joined / Available
- **kubeconfig** 仅用于 `clusteradm join` 式引导，以及演示里模拟 **cluster-proxy** 做只读 inventory

首次启动会加载 3 个已接受的演示集群（生产 / 预发 / 边缘），外加一个待批准的 `kind-dev`，用于展示握手。

## 系统架构

```
┌─────────────┐  CSR / join   ┌──────────────────┐  Accept   ┌─────────────────┐
│  Klusterlet │ ─────────────►│  OCM Hub         │ ─────────►│ ManagedCluster  │
│  (spoke)    │  pull Work    │  registration    │  ns/<name>│ ClusterClaims   │
└─────────────┘ ◄──────────── │  work / placement│           └─────────────────┘
                              └──────────────────┘
```

- **后端**: FastAPI + 进程内 OCM 控制器；已接受集群用独立 `ApiClient` 采集 inventory
- **前端**: 纯 HTML / CSS / JavaScript（无需构建）
- **状态**: `data/ocm-hub.json`（与 `ai-cluster-gateway` 共享同一份 Hub；上传的 kubeconfig 仍在 `data/kubeconfigs/`）

## 项目结构

```
k8s-cluster-explorer/
├── backend/
│   ├── main.py              # OCM Hub API（兼容旧 /api/clusters）
│   ├── ocm_hub.py           # ManagedCluster / ManifestWork / Placement
│   ├── cluster_manager.py   # 握手后的 inventory 连接
│   ├── k8s_service.py       # 单集群资源采集（cluster-proxy 模拟）
│   └── requirements.txt
├── frontend/
│   └── index.html           # Hub / Klusterlet 控制台
├── data/                    # 运行时 Hub 状态（自动生成）
└── README.md
```

## 快速开始

```bash
cd k8s-cluster-explorer
pip install -r requirements.txt
python backend/main.py
```

浏览器打开 [http://localhost:8003](http://localhost:8003)

- API 文档: http://localhost:8003/docs

## 功能特性

- **Join / Accept / Deny**：OCM 双向握手，待批准集群不能下发 Work、不能读 inventory
- **ManifestWork**：写入 Hub 上该集群的 namespace，由 work-agent pull 并标记 Applied
- **Placement**：`labelSelector` + `claimSelector`，自动生成 PlacementDecision
- **ClusterClaim / Condition**：`HubAcceptedManagedCluster`、`ManagedClusterJoined`、`ManagedClusterAvailable`
- **Fleet 资源汇总**：已接受集群的节点、Pod、CPU / 内存 / GPU
- **演示模式**：预置 3 个 Available 集群 + 1 个 pending join，无需真实 API Server

生产 OCM 中 Hub **不保存** spoke kubeconfig。本演示若用真实集群，kubeconfig 只用于 join bootstrap 与只读采集。

## API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/hub | Hub 信息与对象计数 |
| GET | /api/fleet | Hub + 已注册集群汇总 |
| GET/POST | /api/managedclusters | 列表 / join |
| POST | /api/managedclusters/join | clusteradm join（默认不自动接受） |
| POST | /api/managedclusters/{name}/accept | 设置 hubAcceptsClient=true |
| POST | /api/managedclusters/{name}/deny | 拒绝接入 |
| POST | /api/managedclusters/import | 按 kubeconfig context 批量 join |
| POST | /api/managedclusters/upload | 上传 kubeconfig 并 join |
| POST | /api/managedclusters/demo | 加载演示 Hub |
| GET | /api/manifestworks | ManifestWork 列表 |
| POST | /api/manifestworks | 创建并 reconcile |
| POST | /api/manifestworks/{cluster}/{name}/reconcile | 模拟 work-agent pull |
| GET | /api/placements | Placement + PlacementDecision |
| POST | /api/placements | 按 selector 选集群 |
| GET | /api/clusters/{id}/nodes 等 | 已接受集群 inventory（兼容旧路径） |

Join 示例（等待 Hub 批准）：

```bash
curl -X POST http://localhost:8003/api/managedclusters/join \
  -H "Content-Type: application/json" \
  -d '{
    "name": "prod-shanghai",
    "kubeconfig_path": "~/.kube/config",
    "context": "prod-cn-shanghai",
    "environment": "production",
    "region": "cn-shanghai"
  }'

curl -X POST http://localhost:8003/api/managedclusters/prod-shanghai/accept
```

下发 ManifestWork：

```bash
curl -X POST http://localhost:8003/api/manifestworks \
  -H "Content-Type: application/json" \
  -d '{
    "cluster": "prod-cn-shanghai",
    "name": "demo-config",
    "manifests": [{"apiVersion":"v1","kind":"ConfigMap","metadata":{"name":"from-hub","namespace":"default"}}]
  }'
```

## 权限说明

若用真实 kubeconfig 做 join / inventory，对应身份至少需要对以下资源有 **list/get** 权限：

- `nodes`, `namespaces`, `pods`, `events`, `services`
- `deployments`, `statefulsets`, `daemonsets`

只读账号即可。真实集群连不上时会标记为 **offline**，不会用模拟数据冒充。

这是 **OCM API 语义的本地控制面**，不会在集群里安装 `cluster-manager` / `klusterlet` Operator。若要对接真实 OCM，请使用 [clusteradm](https://open-cluster-management.io/docs/getting-started/installation/start-the-journey/)。

## 依赖

- Python 3.9+
- FastAPI / Uvicorn / Pydantic
- kubernetes
- 可选：可访问的 Kubernetes API Server
