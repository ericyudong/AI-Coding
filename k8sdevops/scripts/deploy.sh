#!/usr/bin/env bash
# 一键部署脚本（Linux/macOS）
set -euo pipefail

echo "==> 部署 Tekton 资源..."
kubectl apply -f tekton/namespace.yaml
kubectl apply -f tekton/rbac.yaml
kubectl apply -f tekton/tasks/
kubectl apply -f tekton/pipeline.yaml

if [ -f tekton/secrets.yaml ]; then
  kubectl apply -f tekton/secrets.yaml
else
  echo "WARN: tekton/secrets.yaml 不存在，请先复制 secrets.example.yaml 并填入凭据"
fi

echo "==> 部署 Argo CD 资源..."
kubectl apply -f argocd/project.yaml
kubectl apply -f argocd/application.yaml

echo "==> 完成！"
echo "手动触发 CI: kubectl create -f tekton/pipelinerun-example.yaml"
echo "查看 Pipeline: tkn pipelinerun list -n tekton-pipelines"
