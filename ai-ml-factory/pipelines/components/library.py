"""Reusable Kubeflow Pipeline components (Scheme B component library)."""

from kfp import dsl
from kfp.dsl import Dataset, Input, Metrics, Model, Output


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["pandas==2.2.2", "scikit-learn==1.5.1", "xgboost==2.1.1", "joblib==1.4.2"],
)
def prepare_data(dataset: Output[Dataset], n_samples: int = 5000):
    """Data processing + feature engineering."""
    from pathlib import Path

    import pandas as pd
    from sklearn.datasets import make_classification

    x, y = make_classification(
        n_samples=n_samples,
        n_features=20,
        n_informative=12,
        n_redundant=4,
        random_state=42,
    )
    frame = pd.DataFrame(x, columns=[f"f{i}" for i in range(x.shape[1])])
    frame["label"] = y
    path = Path(dataset.path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path)
    dataset.metadata = {"rows": n_samples, "features": 20, "task": "binary_classification"}


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "pandas==2.2.2",
        "scikit-learn==1.5.1",
        "xgboost==2.1.1",
        "joblib==1.4.2",
        "pyarrow==16.1.0",
    ],
)
def train_model(dataset: Input[Dataset], model: Output[Model], max_depth: int = 6, n_estimators: int = 120):
    """Classical XGBoost training step."""
    import json
    from pathlib import Path

    import joblib
    import pandas as pd
    import xgboost as xgb
    from sklearn.model_selection import train_test_split

    frame = pd.read_parquet(dataset.path)
    x = frame.drop(columns=["label"])
    y = frame["label"]
    x_train, _, y_train, _ = train_test_split(x, y, test_size=0.2, random_state=42)
    clf = xgb.XGBClassifier(
        max_depth=max_depth,
        n_estimators=n_estimators,
        learning_rate=0.08,
        subsample=0.9,
        eval_metric="logloss",
        n_jobs=4,
    )
    clf.fit(x_train, y_train)
    out = Path(model.path)
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, out)
    model.metadata = {
        "framework": "xgboost",
        "format": "joblib",
        "max_depth": max_depth,
        "n_estimators": n_estimators,
    }
    (out.parent / "metadata.json").write_text(json.dumps(model.metadata, indent=2))


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "pandas==2.2.2",
        "scikit-learn==1.5.1",
        "xgboost==2.1.1",
        "joblib==1.4.2",
        "pyarrow==16.1.0",
    ],
)
def evaluate_model(
    dataset: Input[Dataset],
    model: Input[Model],
    metrics: Output[Metrics],
    min_auc: float = 0.90,
):
    """Model validation + metrics gate."""
    import json
    from pathlib import Path

    import joblib
    import pandas as pd
    from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
    from sklearn.model_selection import train_test_split

    frame = pd.read_parquet(dataset.path)
    x = frame.drop(columns=["label"])
    y = frame["label"]
    _, x_test, _, y_test = train_test_split(x, y, test_size=0.2, random_state=42)
    clf = joblib.load(model.path)
    proba = clf.predict_proba(x_test)[:, 1]
    pred = (proba >= 0.5).astype(int)
    auc = float(roc_auc_score(y_test, proba))
    f1 = float(f1_score(y_test, pred))
    acc = float(accuracy_score(y_test, pred))
    metrics.log_metric("auc", auc)
    metrics.log_metric("f1", f1)
    metrics.log_metric("accuracy", acc)
    report = {"auc": auc, "f1": f1, "accuracy": acc, "gate_min_auc": min_auc, "passed": auc >= min_auc}
    Path(metrics.path).write_text(json.dumps(report, indent=2))
    if auc < min_auc:
        raise RuntimeError(f"evaluation gate failed: auc={auc:.4f} < {min_auc}")


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["boto3==1.34.144", "mlflow==2.14.3"],
)
def register_artifact(
    model: Input[Model],
    metrics: Input[Metrics],
    model_name: str,
    model_version: str,
    s3_uri: str,
    mlflow_tracking_uri: str = "http://mlflow.ml-registry.svc.cluster.local:5000",
):
    """Publish versioned artifact to object storage + MLflow Model Registry."""
    import json
    import os
    from pathlib import Path
    from urllib.parse import urlparse

    import boto3
    import mlflow
    from mlflow.tracking import MlflowClient

    report = json.loads(Path(metrics.path).read_text())
    if not report.get("passed"):
        raise RuntimeError("refusing to register failed evaluation")

    parsed = urlparse(s3_uri)
    if parsed.scheme not in ("s3", "s3a"):
        raise ValueError(f"expected s3:// URI, got {s3_uri}")
    bucket = parsed.netloc
    prefix = parsed.path.lstrip("/")
    endpoint = os.environ.get("MLFLOW_S3_ENDPOINT_URL") or os.environ.get("S3_ENDPOINT_URL")
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "minio"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "minio123"),
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )
    key = f"{prefix.rstrip('/')}/{model_name}/{model_version}/model.joblib"
    client.upload_file(model.path, bucket, key)
    meta_key = f"{prefix.rstrip('/')}/{model_name}/{model_version}/metrics.json"
    client.put_object(Bucket=bucket, Key=meta_key, Body=json.dumps(report, indent=2).encode())
    artifact_uri = f"s3://{bucket}/{key}"

    mlflow.set_tracking_uri(mlflow_tracking_uri)
    mlflow.set_experiment(model_name)
    with mlflow.start_run(run_name=f"{model_name}-{model_version}") as run:
        mlflow.log_metrics({k: float(v) for k, v in report.items() if isinstance(v, (int, float))})
        mlflow.log_param("artifact_uri", artifact_uri)
        mlflow.log_param("framework", "xgboost")
        mlflow.log_artifact(model.path, artifact_path="model")
        model_uri = f"runs:/{run.info.run_id}/model"
        result = mlflow.register_model(model_uri, model_name)
        client_ml = MlflowClient()
        client_ml.transition_model_version_stage(
            name=model_name,
            version=result.version,
            stage="Staging",
            archive_existing_versions=False,
        )
    Path("/tmp/artifact-uri.txt").write_text(artifact_uri)
    print(json.dumps({"artifact_uri": artifact_uri, "mlflow_version": result.version}, indent=2))
