#!/usr/bin/env python3
"""Upload a local versioned model directory to MinIO/S3.

Example:
  python registry/scripts/upload_artifact.py \\
    --src artifacts/fraud-xgb/v1.0.0 \\
    --s3-uri s3://ai-factory/models/fraud-xgb/v1.0.0 \\
    --endpoint http://localhost:9000
"""
from __future__ import annotations

import argparse
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse

import boto3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True)
    parser.add_argument("--s3-uri", required=True)
    parser.add_argument("--endpoint", default=os.environ.get("S3_ENDPOINT_URL", "http://localhost:9000"))
    args = parser.parse_args()

    parsed = urlparse(args.s3_uri)
    bucket, prefix = parsed.netloc, parsed.path.lstrip("/")
    client = boto3.client(
        "s3",
        endpoint_url=args.endpoint,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "minio"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "minio123"),
        region_name="us-east-1",
    )
    root = Path(args.src)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        key = f"{prefix.rstrip('/')}/{path.relative_to(root).as_posix()}"
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        client.upload_file(str(path), bucket, key, ExtraArgs={"ContentType": content_type})
        print(f"uploaded s3://{bucket}/{key}")


if __name__ == "__main__":
    main()
