"""Component catalog metadata (no kfp import — safe for console validate/UI)."""
from __future__ import annotations

from typing import Any, Dict, List

CATALOG: List[Dict[str, Any]] = [
    {
        "id": "prepare_data",
        "label": "准备数据",
        "description": "生成/处理特征数据集",
        "params": [
            {"name": "n_samples", "type": "int", "default": 5000, "label": "样本数"},
        ],
        "inputs": [],
        "outputs": [{"name": "dataset", "type": "Dataset"}],
    },
    {
        "id": "train_model",
        "label": "训练模型",
        "description": "XGBoost 训练，产出 Model 制品",
        "params": [
            {"name": "max_depth", "type": "int", "default": 6, "label": "max_depth"},
            {"name": "n_estimators", "type": "int", "default": 120, "label": "n_estimators"},
        ],
        "inputs": [{"name": "dataset", "type": "Dataset"}],
        "outputs": [{"name": "model", "type": "Model"}],
    },
    {
        "id": "evaluate_model",
        "label": "评估门禁",
        "description": "AUC 门禁；失败则阻断注册",
        "params": [
            {"name": "min_auc", "type": "float", "default": 0.90, "label": "最低 AUC"},
        ],
        "inputs": [
            {"name": "dataset", "type": "Dataset"},
            {"name": "model", "type": "Model"},
        ],
        "outputs": [{"name": "metrics", "type": "Metrics"}],
        "gate": True,
    },
    {
        "id": "register_artifact",
        "label": "注册制品",
        "description": "上传 MinIO/S3 + MLflow Registry",
        "params": [
            {"name": "model_name", "type": "str", "default": "fraud-xgb", "label": "模型名"},
            {"name": "model_version", "type": "str", "default": "v1.0.0", "label": "版本"},
            {"name": "s3_uri", "type": "str", "default": "s3://ai-factory/models", "label": "S3 URI"},
            {
                "name": "mlflow_tracking_uri",
                "type": "str",
                "default": "http://mlflow.ml-registry.svc.cluster.local:5000",
                "label": "MLflow URI",
            },
        ],
        "inputs": [
            {"name": "model", "type": "Model"},
            {"name": "metrics", "type": "Metrics"},
        ],
        "outputs": [],
        "requires_gate": True,
    },
]

CATALOG_BY_ID: Dict[str, Dict[str, Any]] = {c["id"]: c for c in CATALOG}
