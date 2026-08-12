# 将 claw-agent 挂入 Argo CD — 操作记录

> 日期：2026-08-04  
> 环境：本机 minikube + Argo CD（`argocd` 命名空间）  
> 目标仓库：`http://10.65.16.39:3000/EHui/claw-agent.git`

---

## 1. 目标与结果摘要

| 项 | 结果 |
|---|---|
| Argo CD AppProject `ai-guardrails` | 已创建 |
| Application `ai-guardrails-staging` / `ai-guardrails-prod` | 已创建 |
| 仓库凭据 Secret `repo-claw-agent` | 已创建（`argocd.argoproj.io/secret-type=repository`） |
| 远程写入 `gitops-env/`（17 个文件） | 已成功（Gitea Contents API） |
| Kustomize 修复（Rollout + replicas） | **本地已修**；远程仍为旧版，需再推一次 |
| Argo CD 自动 Sync | 当前 `Unknown`（远程 kustomize 报错 + 凭据后续失效） |
| 集群侧清单（kubectl apply） | staging/prod 命名空间资源已落地 |

UI：https://localhost:8080（需 `kubectl -n argocd port-forward svc/argocd-server 8080:443`）

---

## 2. 前置状态

- minikube：Running  
- Argo CD Pods：全部 Ready  
- claw-agent：私有仓，匿名 `git-upload-pack` 返回 **401**  
- 本机可通过 Git Credential Manager（GCM）访问 Gitea（`10.65.16.39:3000`）

---

## 3. 配置仓库凭据

Argo CD 通过带特殊 label 的 Secret 识别 Git 仓库账号：

```bash
kubectl -n argocd create secret generic repo-claw-agent \
  --from-literal=type=git \
  --from-literal=url=http://10.65.16.39:3000/EHui/claw-agent.git \
  --from-literal=username='<GITEA_USER_OR_OAUTH_USER>' \
  --from-literal=password='<GITEA_PAT_OR_TOKEN>'

kubectl -n argocd label secret repo-claw-agent \
  argocd.argoproj.io/secret-type=repository --overwrite
```

本次实际使用本机 GCM 中缓存的 OAuth 令牌写入 Secret（用户名形如 `OAUTH_USER`）。  
**注意**：OAuth/JWT 会过期；生产请改用 **Gitea Personal Access Token（PAT）**，并具有 `read`（Argo CD）与 `write`（推送清单）权限。

验证：

```bash
kubectl -n argocd get secret -l argocd.argoproj.io/secret-type=repository
```

期望看到：`repo-claw-agent`。

---

## 4. Apply `gitops-env/argocd/`

```bash
kubectl apply -f gitops-env/argocd/appproject.yaml
kubectl apply -f gitops-env/argocd/app-staging.yaml
kubectl apply -f gitops-env/argocd/app-prod.yaml
```

说明：

- **未**对 `argocd/analysis-guardrail-slo.yaml` 做集群 apply（该文件是参考副本；真正的 AnalysisTemplate 由 `base/` 经 Kustomize 下发）。
- Application 指向：
  - repo：`http://10.65.16.39:3000/EHui/claw-agent.git`
  - path：`gitops-env/envs/staging` / `gitops-env/envs/prod`
  - revision：`main`

结果：

```text
appproject.argoproj.io/ai-guardrails created
application.argoproj.io/ai-guardrails-staging created
application.argoproj.io/ai-guardrails-prod created
```

---

## 5. 将本地 GitOps 清单写入 claw-agent

远程原先**没有** `gitops-env/`。完整 `git clone`/`git push` 因仓库体积与认证不稳定多次超时，最终用 **Gitea Contents API** 上传 17 个文件：

```text
SUMMARY ok=17 fail=0
gitops-env        -> HTTP 200
envs/staging      -> HTTP 200
```

上传路径前缀：`gitops-env/**`（与 Application `path` 一致）。

同时安装了精简 Rollouts CRD（本机无法稳定拉取 GitHub 上的完整 Argo Rollouts install）：

```bash
kubectl apply -f gitops-env/argocd/rollouts-crds-minimal.yaml
```

> 完整 Rollouts Controller 仍建议网络可达时安装官方 `install.yaml`；当前 CRD 足以让资源入库，但金丝雀控制器不会真正调度 Pod。

---

## 6. 同步故障排查与修复

### 6.1 初期：`git fetch` 超时

claw-agent 体积较大，repo-server 默认约 90s 超时。已调整：

```yaml
# argocd-cmd-params-cm
reposerver.git.request.timeout: "15m"
controller.repo.server.timeout.seconds: "900"
timeout.reconciliation: "300s"
```

并为 `argocd-repo-server` 设置 `ARGOCD_EXEC_TIMEOUT=15m`。

调整后能拉到含 `gitops-env` 的 revision（例如 `5ca8e371...`）。

### 6.2 随后：Kustomize 构建失败（当前阻塞点）

错误：

```text
Error: resource with name ai-guardrails does not match a config with the following GVK
[Deployment StatefulSet ReplicaSet ReplicationController]
```

原因：`envs/*/kustomization.yaml` 使用了 `replicas:` 转换器，**只支持原生工作负载**，不支持 `Rollout`（`argoproj.io`）。

本地已修复为对 Rollout 做 JSON6902 patch（并去掉 deprecated `commonLabels`）：

- `gitops-env/base/kustomization.yaml`
- `gitops-env/envs/staging/kustomization.yaml`
- `gitops-env/envs/prod/kustomization.yaml`

本地验证：

```bash
kubectl kustomize gitops-env/envs/staging   # OK
kubectl kustomize gitops-env/envs/prod      # OK
```

**远程 claw-agent 在修复推送前仍是旧文件**；之后 GCM OAuth 失效（API 返回 `user does not exist [name: OAUTH_USER]`），未能完成第二次推送。

### 6.3 集群侧临时落地（证明清单可用）

```bash
kubectl create namespace ai-guardrails-staging
kubectl create namespace ai-guardrails-prod
kubectl kustomize gitops-env/envs/staging | kubectl apply -f -
kubectl kustomize gitops-env/envs/prod    | kubectl apply -f -
```

已创建：`Rollout` / `Service`×3 / `ConfigMap/guardrail-policy` / `AnalysisTemplate`。

---

## 7. 你需要完成的收尾（约 5 分钟）

### A. 用 PAT 更新 Argo CD 仓库凭据

在 Gitea 创建 PAT 后：

```bash
kubectl -n argocd delete secret repo-claw-agent --ignore-not-found
kubectl -n argocd create secret generic repo-claw-agent \
  --from-literal=type=git \
  --from-literal=url=http://10.65.16.39:3000/EHui/claw-agent.git \
  --from-literal=username='<你的Gitea用户名>' \
  --from-literal=password='<PAT>'
kubectl -n argocd label secret repo-claw-agent \
  argocd.argoproj.io/secret-type=repository --overwrite
```

### B. 把本地修复推到 claw-agent

```bash
# 在可写克隆中覆盖这 3 个文件后推送
gitops-env/base/kustomization.yaml
gitops-env/envs/staging/kustomization.yaml
gitops-env/envs/prod/kustomization.yaml
```

### C. 硬刷新 Application

```bash
kubectl -n argocd annotate application ai-guardrails-staging \
  argocd.argoproj.io/refresh=hard --overwrite
kubectl -n argocd annotate application ai-guardrails-prod \
  argocd.argoproj.io/refresh=hard --overwrite

kubectl -n argocd get applications -o wide
# 期望 SYNC=Synced
```

### D.（可选）安装完整 Argo Rollouts Controller

网络可达 GitHub 时：

```bash
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml
```

---

## 8. 关键对象一览

| 对象 | 命名空间 | 说明 |
|---|---|---|
| Secret `repo-claw-agent` | argocd | claw-agent Git 凭据 |
| AppProject `ai-guardrails` | argocd | 源仓与目标 NS 边界 |
| Application `ai-guardrails-staging` | argocd | path=`gitops-env/envs/staging` |
| Application `ai-guardrails-prod` | argocd | path=`gitops-env/envs/prod`，`selfHeal: true` |
| CRD `rollouts.argoproj.io` 等 | cluster | 精简 CRD |
| NS `ai-guardrails-staging` / `prod` | — | 工作负载命名空间 |

额外：曾用 API 创建过轻量仓 `yudong/ai-guardrails-gitops`（备用）；主路径仍以 **EHui/claw-agent** 为准。若不需要可自行删除。

---

## 9. 命令速查

```bash
# 状态
kubectl -n argocd get applications -o wide
kubectl -n argocd get secret -l argocd.argoproj.io/secret-type=repository
kubectl get rollout,svc,cm -n ai-guardrails-staging
kubectl get rollout,svc,cm -n ai-guardrails-prod

# UI
kubectl -n argocd port-forward svc/argocd-server 8080:443
# https://localhost:8080  admin / (初始密码见 argocd-initial-admin-secret)

# 应用日志
kubectl -n argocd logs deploy/argocd-repo-server --tail=50
```

---

## 10. 结论

- **已完成**：凭据 Secret、AppProject、Applications apply；`gitops-env` 首次写入 claw-agent；Rollouts CRD；本地 kustomize 修复；集群侧 staging/prod 资源已用本地清单 apply。  
- **待你完成**：用稳定 **PAT** 刷新 Secret，并将 3 个修复后的 `kustomization.yaml` 推到 claw-agent，然后 hard refresh，Argo CD 即可进入 `Synced`。
