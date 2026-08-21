# Artifact layout

Models are **versioned directories**, never anonymous layers inside a serving image.

```
s3://ai-factory/models/<name>/<semver>/
  model.joblib | model.pt | …
  metrics.json
  MLmodel          # optional MLflow flavor metadata

s3://ai-factory/mlflow/   # MLflow tracking artifacts
```

OCI alternative:

```
oci://registry.example.com/models/<name>:<semver>
```

KServe `storageUri` / PVC sync Jobs must point at a concrete version.
