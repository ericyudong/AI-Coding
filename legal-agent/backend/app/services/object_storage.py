"""Local object storage (filesystem OSS-compatible layout)."""
from __future__ import annotations

import uuid
from pathlib import Path

from app.core.config import data_root


def _bucket(name: str) -> Path:
    root = data_root() / "objects" / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def put_bytes(bucket: str, content: bytes, *, filename: str = "", user_id: int | None = None) -> dict:
    """Store bytes and return relative object key + metadata."""
    ext = Path(filename).suffix.lower() if filename else ""
    key_parts = []
    if user_id is not None:
        key_parts.append(str(user_id))
    key_parts.append(f"{uuid.uuid4().hex}{ext}")
    rel_key = "/".join(key_parts)
    dest = _bucket(bucket) / rel_key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return {
        "bucket": bucket,
        "key": rel_key,
        "path": f"{bucket}/{rel_key}",
        "filename": filename or dest.name,
        "size": len(content),
    }


def resolve_path(object_path: str) -> Path | None:
    """Resolve `bucket/key` to absolute path if exists."""
    if not object_path or ".." in object_path:
        return None
    full = data_root() / "objects" / object_path
    if full.is_file():
        return full
    return None


def delete_object(object_path: str) -> bool:
    p = resolve_path(object_path)
    if not p:
        return False
    p.unlink(missing_ok=True)
    return True
