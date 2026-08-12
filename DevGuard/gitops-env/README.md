# gitops-env — Argo CD single source of truth

Deploy state lives only here. CI never runs `kubectl apply` / `helm upgrade`.

## Apply Argo CD apps

```bash
# repoURL: http://10.65.16.39:3000/EHui/claw-agent.git
kubectl apply -f argocd/appproject.yaml
kubectl apply -f argocd/app-staging.yaml
kubectl apply -f argocd/app-prod.yaml
```

## Promote an image (normally done by CI after gates pass)

```bash
cd envs/prod
kustomize edit set image \
  registry.internal.example.com/ai/ai-guardrails=registry.internal.example.com/ai/ai-guardrails:<SHORT_SHA>
git commit -am "promote ai-guardrails:<SHORT_SHA>"
git push
```

## Verify self-heal

```bash
kubectl -n ai-guardrails-prod scale rollout ai-guardrails --replicas=1
# With selfHeal: true, Argo CD restores replicas from Git within minutes.
```
