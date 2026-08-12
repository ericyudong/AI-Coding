"""Contract Management System (CMS) models."""
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ManagedContract(Base):
    __tablename__ = "managed_contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256), index=True)
    contract_type: Mapped[str] = mapped_column(String(32), index=True)
    party_a: Mapped[str] = mapped_column(String(256), default="")
    party_b: Mapped[str] = mapped_column(String(256), default="", index=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(16), default="CNY")
    sign_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expire_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True, default="active")
    owner: Mapped[str] = mapped_column(String(64), default="")
    department_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    risk_level: Mapped[str] = mapped_column(String(16), default="low")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    tag_level1: Mapped[str] = mapped_column(String(64), default="")
    tag_level2: Mapped[str] = mapped_column(String(64), default="")
    ai_summary: Mapped[str] = mapped_column(Text, default="")
    summary_locked: Mapped[bool] = mapped_column(default=False)
    content_text: Mapped[str] = mapped_column(Text, default="")
    key_clauses_json: Mapped[str] = mapped_column(Text, default="[]")
    parse_status: Mapped[str] = mapped_column(String(32), default="done")
    index_status: Mapped[str] = mapped_column(String(32), default="pending")
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    versions: Mapped[list["ContractVersion"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan", order_by="ContractVersion.id"
    )


class ContractVersion(Base):
    __tablename__ = "contract_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("managed_contracts.id"), index=True)
    version: Mapped[str] = mapped_column(String(16))
    label: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text, default="")
    is_current: Mapped[bool] = mapped_column(default=False)
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    contract: Mapped["ManagedContract"] = relationship(back_populates="versions")


class ContractChunk(Base):
    __tablename__ = "contract_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("managed_contracts.id"), index=True)
    version_id: Mapped[int | None] = mapped_column(ForeignKey("contract_versions.id"), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    section_title: Mapped[str] = mapped_column(String(256), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    start_offset: Mapped[int] = mapped_column(Integer, default=0)
    vector_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ContractImportTask(Base):
    __tablename__ = "contract_import_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    file_path: Mapped[str] = mapped_column(String(1024), default="")
    status: Mapped[str] = mapped_column(String(32), default="queued")  # queued/processing/completed/failed
    progress: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    content_text: Mapped[str] = mapped_column(Text, default="")
    parse_warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    extracted_json: Mapped[str] = mapped_column(Text, default="{}")
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
