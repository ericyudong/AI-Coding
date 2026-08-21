"""Standalone classical trainer used by CI and local smoke tests.

Prefers XGBoost; falls back to sklearn HistGradientBoosting when libomp is missing
(common on macOS). Kubeflow Pipeline components still use XGBoost on Linux images.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.datasets import make_classification
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import train_test_split

try:
    import xgboost as xgb

    HAS_XGB = True
except Exception:
    HAS_XGB = False
    from sklearn.ensemble import HistGradientBoostingClassifier


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="artifacts/fraud-xgb/v0.0.0-local")
    parser.add_argument("--n-samples", type=int, default=2000)
    parser.add_argument("--min-auc", type=float, default=0.90)
    args = parser.parse_args()

    x, y = make_classification(
        n_samples=args.n_samples,
        n_features=20,
        n_informative=12,
        n_redundant=4,
        random_state=42,
    )
    frame = pd.DataFrame(x, columns=[f"f{i}" for i in range(x.shape[1])])
    frame["label"] = y
    x_train, x_test, y_train, y_test = train_test_split(
        frame.drop(columns=["label"]), frame["label"], test_size=0.2, random_state=42
    )
    if HAS_XGB:
        model = xgb.XGBClassifier(max_depth=5, n_estimators=80, learning_rate=0.1, eval_metric="logloss")
        framework = "xgboost"
    else:
        model = HistGradientBoostingClassifier(max_depth=5, max_iter=80, learning_rate=0.1)
        framework = "sklearn-hist-gbdt"
    model.fit(x_train, y_train)
    proba = model.predict_proba(x_test)[:, 1]
    pred = (proba >= 0.5).astype(int)
    metrics = {
        "auc": float(roc_auc_score(y_test, proba)),
        "f1": float(f1_score(y_test, pred)),
        "framework": framework,
        "kind": "ModelArtifact",
    }
    if metrics["auc"] < args.min_auc:
        raise SystemExit(f"gate failed: auc={metrics['auc']:.4f}")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out / "model.joblib")
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (out / "MLmodel").write_text(
        "\n".join(
            [
                "flavors:",
                "  sklearn:",
                "    pickled_model: model.joblib",
                "metadata:",
                "  artifact_type: versioned-model",
                "  note: Do not treat this model as a container image",
                "",
            ]
        )
    )
    print(json.dumps({"out_dir": str(out), **metrics}, indent=2))


if __name__ == "__main__":
    main()
