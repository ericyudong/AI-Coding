"""Audit logs, tag/summary history, and analytics events."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ContractAuditLog(Base):
    __tablename__ = "contract_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("managed_contracts.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)  # tag_update / summary_update / reparse
    before_json: Mapped[str] = mapped_column(Text, default="{}")
    after_json: Mapped[str] = mapped_column(Text, default="{}")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    event_name: Mapped[str] = mapped_column(String(64), index=True)
    props_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


async def write_audit(
    db: AsyncSession,
    *,
    contract_id: int,
    user_id: int,
    action: str,
    before: dict,
    after: dict,
    note: str = "",
) -> ContractAuditLog:
    row = ContractAuditLog(
        contract_id=contract_id,
        user_id=user_id,
        action=action,
        before_json=json.dumps(before, ensure_ascii=False, default=str),
        after_json=json.dumps(after, ensure_ascii=False, default=str),
        note=note,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_audits(db: AsyncSession, contract_id: int, limit: int = 50) -> list[ContractAuditLog]:
    result = await db.execute(
        select(ContractAuditLog)
        .where(ContractAuditLog.contract_id == contract_id)
        .order_by(ContractAuditLog.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def track_event(
    db: AsyncSession,
    *,
    event_name: str,
    user_id: int | None = None,
    props: dict | None = None,
) -> None:
    db.add(
        AnalyticsEvent(
            user_id=user_id,
            event_name=event_name,
            props_json=json.dumps(props or {}, ensure_ascii=False, default=str),
        )
    )
    await db.commit()
