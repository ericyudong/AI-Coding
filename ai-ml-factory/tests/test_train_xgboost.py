from pathlib import Path

from training.xgboost import train as train_mod


def test_train_writes_versioned_artifact(tmp_path: Path, monkeypatch):
    out = tmp_path / "fraud-xgb" / "v0.0.1"
    monkeypatch.setattr(
        "sys.argv",
        ["train.py", "--out-dir", str(out), "--n-samples", "400", "--min-auc", "0.80"],
    )
    train_mod.main()
    assert (out / "model.joblib").is_file()
    assert (out / "metrics.json").is_file()
    assert "versioned-model" in (out / "MLmodel").read_text()
