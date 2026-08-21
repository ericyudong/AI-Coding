from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_serving_uses_storage_uri_not_baked_weights():
    xgb = (ROOT / "serving/xgboost/inferenceservice.yaml").read_text()
    assert "storageUri:" in xgb
    assert "s3://ai-factory/models/" in xgb


def test_readme_states_artifact_principle():
    readme = (ROOT / "README.md").read_text()
    assert "versioned artifact" in readme.lower() or "版本化制品" in readme
