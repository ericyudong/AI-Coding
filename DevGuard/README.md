# AI Guardrails — Argo CD Native GitOps
#
# Monorepo layout matching argocd_gitops_ai_guardrails.md:
#   app-source/   — build + guardrail gates (CI)
#   gitops-env/   — manifests (Argo CD single source of truth)
#
# Split into two remotes for production if required by your change-control process.

## Architecture

```
App Source ──CI gates──► Image Registry
     │
     └──kustomize set image + commit──► gitops-env ──Argo CD reconcile──► Cluster
                                              ▲
                                    selfHeal / rollback
```

- **CI fail** → no env commit → no deploy
- **Cluster drift** → Argo CD `selfHeal` restores Git state
- **Runtime SLO breach** → Argo Rollouts analysis fails → auto-rollback

## Gate thresholds

| Metric | Max |
|---|---|
| Jailbreak bypass | ≤ 2% |
| False positive | ≤ 2% |
| PII leak | = 0% |

## Quick start (local gates)

```bash
cd app-source
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt

python scripts/validate_policy.py guardrails/policy.yaml
pytest tests/guardrails/ -q
python scripts/eval.py --out reports/eval.json
python scripts/check_gate.py --report reports/eval.json --max-bypass 2 --max-fp 2
python scripts/redteam.py --out reports/redteam.json
python scripts/check_redteam.py --report reports/redteam.json

uvicorn src.main:app --port 8080
# curl -X POST http://127.0.0.1:8080/v1/guard -H 'content-type: application/json' \
#   -d '{"text":"Ignore previous instructions"}'
```

## Cluster bootstrap

```bash
# Prerequisites: Argo CD, Argo Rollouts, (optional) Gatekeeper, Prometheus
kubectl apply -f gitops-env/argocd/appproject.yaml
kubectl apply -f gitops-env/argocd/app-staging.yaml
kubectl apply -f gitops-env/argocd/app-prod.yaml

# Admission rails (prod)
kubectl apply -f gitops-env/gatekeeper/constrainttemplate-guardrail-policy.yaml
kubectl apply -f gitops-env/gatekeeper/constraint-require-guardrail-policy.yaml
```

Argo CD `repoURL` 已指向：`http://10.65.16.39:3000/EHui/claw-agent.git`（清单路径为 `gitops-env/envs/{staging,prod}`）。

## Repository layout

```
DevGuard/
├── app-source/
│   ├── guardrails/policy.yaml
│   ├── eval/{regression.jsonl,redteam.jsonl,config.yaml}
│   ├── scripts/{validate_policy,eval,check_gate,redteam,check_redteam,...}.py
│   ├── src/main.py          # FastAPI + Prometheus metrics
│   ├── tests/guardrails/
│   ├── Dockerfile
│   └── Jenkinsfile          # build + gates + gitops promote (no helm deploy)
├── gitops-env/
│   ├── base/                # Rollout, Services, policy ConfigMap, AnalysisTemplate
│   ├── envs/{staging,prod}/ # image tags via kustomize images:
│   ├── argocd/              # AppProject + Applications
│   └── gatekeeper/          # forbid :latest + require policy ConfigMap
└── .github/workflows/ci.yml
```

## Docs

- [工作流程总览](docs/workflow.md) — 端到端 CI → GitOps → Argo CD → Rollouts
- [Argo CD 挂接记录](docs/argocd-claw-agent-setup.md) — minikube / claw-agent 实操

## Compliance notes

Environment and policy changes should go through MR + approval. Archive CI eval
reports and Argo CD sync history as audit evidence (SR 11-7 / DORA / MiFID II / GDPR Art.22).
