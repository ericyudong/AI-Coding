# LiteLLM AI Gateway + Guardrails

用 LiteLLM Proxy 做统一推理网关：**多模型路由** + **六层 Guardrails** + **可观测/审计**。

门禁阈值：越狱绕过 ≤ 2%、误报 ≤ 2%、PII 泄露 = 0、接地性 ≥ 0.9。

## 目录

```
├── config/
│   ├── config.yaml          # 生产：路由 + Presidio/Lakera/LlamaGuard/Bedrock
│   └── config.dev.yaml      # 本地：自定义 Rails，无需外部 SaaS
├── guardrails/
│   ├── policy.yaml          # 策略即代码
│   └── engine.py            # 确定性护栏引擎（评估门/单测）
├── custom_guardrail.py      # LiteLLM CustomGuardrail 适配
├── custom_callbacks.py      # 审计 JSONL + x-model-tier 路由
├── deployments/
│   ├── docker-compose.yml   # litellm + presidio + otel
│   └── k8s/                 # Kustomize + Argo CD
├── scripts/
│   ├── validate_policy.py
│   ├── eval_gate.py
│   └── rollback.py
├── eval/                    # 回归 / 红队样本
└── tests/guardrails/
```

## 快速开始（本地）

```bash
cp .env.example .env
# 至少填写 LITELLM_MASTER_KEY；若用 OpenAI 填 OPENAI_KEY

pip install -r requirements.txt
python scripts/validate_policy.py
python scripts/eval_gate.py
pytest tests/guardrails/ -q

# 起依赖 + 网关（开发配置）
cd deployments
docker compose up -d --build
```

业务方调用：

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"default","messages":[{"role":"user","content":"Hello"}]}'
```

或设 `OPENAI_BASE_URL=http://localhost:4000/v1`，`model` 使用路由键：`default` / `reasoning` / `fast` / `vision` / `local`。

请求头 `x-model-tier: local|fast|premium` 可由 `TierRoutingCallback` 改写模型（需把 `custom_callbacks.tier_routing_callback` 加入 `litellm_settings.callbacks`）。

## 六层 Rails → 实现

| Rail | 时机 | 实现 |
|------|------|------|
| Input | `pre_call` | Presidio PII、Lakera、`InjectionRail` |
| Dialog | `pre_call` | `DialogRail`（话题/轮次，策略在 `policy.yaml`） |
| Retrieval | 策略字段 | `policy.yaml` `rails.retrieval`（RAG 侧 wrapper 消费） |
| Tool | `pre_call` | `ToolRail` 白名单 + schema |
| Output | `post_call` | LlamaGuard / Bedrock；开发用 `OutputPiiRail` |
| Monitoring | callbacks | Langfuse / OTel / `AuditCallback` |

> 文档中的 `before_call` / `after_call` 对应 LiteLLM 的 `pre_call` / `post_call`。

## 评估门与回滚

```bash
# 回归门禁
python scripts/eval_gate.py --dataset eval/regression.jsonl
python scripts/eval_gate.py --dataset eval/redteam.jsonl --out reports/redteam.json

# 紧急降级到 local
python scripts/rollback.py --mode route --target local --config config/config.dev.yaml

# 压掉金丝雀权重
python scripts/rollback.py --mode weight --canary-weight 0

# GitOps 镜像回退
python scripts/rollback.py --mode image --tag <previous-sha>
```

## Kubernetes / Argo CD

```bash
kubectl apply -k deployments/k8s/envs/staging
kubectl apply -f deployments/k8s/argocd/appproject.yaml
kubectl apply -f deployments/k8s/argocd/app-prod.yaml
```

生产金丝雀见 `deployments/k8s/base/rollout.yaml` 与 `analysis-guardrail-slo.yaml`（误报/越狱 ≤ 2%）。

## 金融合规要点

- 敏感流量走 `local`；密钥仅环境变量 / Secret
- `policy.yaml` 变更走 MR；审计日志 `AUDIT_LOG_PATH` 长期留存
- 回滚脚本支撑 MTTR ≤ 15 min
