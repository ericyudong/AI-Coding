# Deploy guide

## Prerequisites

- Kubernetes 1.27+
- [Kubeflow Pipelines](https://www.kubeflow.org/docs/components/pipelines/) 2.x
- [KServe](https://kserve.github.io/website/) 0.12+
- NVIDIA GPU Operator (for Triton / vLLM)
- Optional: Argo CD, Tekton, Prometheus Operator

## 1. Registry plane

```bash
kubectl apply -f manifests/base/namespaces.yaml
kubectl apply -f manifests/minio/minio.yaml
kubectl apply -f manifests/mlflow/mlflow.yaml
```

Port-forward MinIO / MLflow:

```bash
kubectl -n ml-registry port-forward svc/minio 9000:9000 9001:9001
kubectl -n ml-registry port-forward svc/mlflow 5000:5000
```

## 2. Train & register (local smoke)

```bash
pip install -r requirements.txt
python training/xgboost/train.py --out-dir artifacts/fraud-xgb/v1.0.0
python registry/scripts/upload_artifact.py \
  --src artifacts/fraud-xgb/v1.0.0 \
  --s3-uri s3://ai-factory/models/fraud-xgb/v1.0.0 \
  --endpoint http://localhost:9000
```

## 3. Submit Kubeflow Pipeline

```bash
python -m pipelines.compiler fraud-default
# Upload pipelines/compiled/ai-ml-factory-train-register.yaml via KFP UI or:
# kfp pipeline create -p ai-ml-factory-train-register -f pipelines/compiled/ai-ml-factory-train-register.yaml
```

## 4. Serve with KServe

```bash
kubectl apply -k manifests/overlays/staging
kubectl -n kserve-demo get inferenceservices
```

Predict (XGBoost):

```bash
curl -X POST http://fraud-xgb.kserve-demo.svc/v1/models/fraud-xgb:predict \
  -H "Content-Type: application/json" \
  -d '{"instances":[[0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0]]}'
```

## 5. GitOps

```bash
kubectl apply -f gitops/argocd/applications.yaml
```
