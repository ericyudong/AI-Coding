"""审计哈希链。

设计文档依据：第七章「合规与注册路径」——审评关注「数据可溯源」与「算法可解释」，
本模块为每一项关键动作生成不可篡改的链式审计记录：

    record_hash = SHA256(prev_hash || canonical_json(payload))

任何一条记录被事后篡改，`verify_chain()` 都会在对应序号处断开，
从而满足追溯要求（对应接口：GET /api/v1/compliance/audit-chain/verify）。
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64


def canonical_json(payload: Any) -> str:
    """稳定序列化：键排序、无多余空白、保留中文原字符。"""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def compute_hash(prev_hash: str, payload: Any) -> str:
    raw = f"{prev_hash}|{canonical_json(payload)}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def record_audit(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: str | int | None = None,
    actor: str | None = None,
    actor_role: str | None = None,
    summary: str | None = None,
    payload: dict[str, Any] | None = None,
    risk_level: str = "normal",
) -> Any:
    """追加一条审计记录并返回 ORM 对象（不提交，由调用方统一 commit）。"""
    from app.models.compliance import AuditChainRecord  # 延迟导入避免循环依赖

    if not settings.audit_chain_enabled:
        return None

    last = db.execute(
        select(AuditChainRecord).order_by(AuditChainRecord.seq.desc()).limit(1)
    ).scalar_one_or_none()
    prev_hash = last.record_hash if last else GENESIS_HASH
    seq = (last.seq + 1) if last else 1

    body = {
        "seq": seq,
        "action": action,
        "resource_type": resource_type,
        "resource_id": None if resource_id is None else str(resource_id),
        "actor": actor,
        "actor_role": actor_role,
        "summary": summary,
        "risk_level": risk_level,
        "payload": payload or {},
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    record_hash = compute_hash(prev_hash, body)

    record = AuditChainRecord(
        seq=seq,
        action=action,
        resource_type=resource_type,
        resource_id=None if resource_id is None else str(resource_id),
        actor=actor,
        actor_role=actor_role,
        summary=summary,
        risk_level=risk_level,
        payload_json=canonical_json(payload or {}),
        body_json=canonical_json(body),
        prev_hash=prev_hash,
        record_hash=record_hash,
    )
    db.add(record)
    db.flush()
    return record


def verify_chain(db: Session, limit: int | None = None) -> dict[str, Any]:
    """逐条重算哈希，校验链的完整性。"""
    from app.models.compliance import AuditChainRecord

    stmt = select(AuditChainRecord).order_by(AuditChainRecord.seq.asc())
    if limit:
        stmt = stmt.limit(limit)
    records = list(db.execute(stmt).scalars())

    prev_hash = GENESIS_HASH
    broken: list[dict[str, Any]] = []
    for index, rec in enumerate(records):
        try:
            body = json.loads(rec.body_json)
        except Exception:
            broken.append({"seq": rec.seq, "reason": "body_json 无法解析"})
            prev_hash = rec.record_hash
            continue
        expected = compute_hash(prev_hash, body)
        if rec.prev_hash != prev_hash:
            broken.append({"seq": rec.seq, "reason": "prev_hash 与前序记录不衔接"})
        elif expected != rec.record_hash:
            broken.append({"seq": rec.seq, "reason": "record_hash 重算不一致（记录可能被篡改）"})
        prev_hash = rec.record_hash

    return {
        "total": len(records),
        "verified": len(records) - len(broken),
        "intact": not broken,
        "broken": broken,
        "head_hash": prev_hash,
        "algorithm": "SHA256(prev_hash || canonical_json(payload))",
    }


def recent_audits(db: Session, limit: int = 50, resource_type: str | None = None) -> list[dict[str, Any]]:
    from app.models.compliance import AuditChainRecord

    stmt = select(AuditChainRecord).order_by(AuditChainRecord.seq.desc()).limit(limit)
    if resource_type:
        stmt = (
            select(AuditChainRecord)
            .where(AuditChainRecord.resource_type == resource_type)
            .order_by(AuditChainRecord.seq.desc())
            .limit(limit)
        )
    rows = list(db.execute(stmt).scalars())
    return [r.to_dict() for r in rows]
