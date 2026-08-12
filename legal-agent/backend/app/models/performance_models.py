"""Performance AI / partner models (supplier, customer, performance)."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, default="")
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(256), index=True)
    credit_code: Mapped[str] = mapped_column(String(64), default="")
    contact: Mapped[str] = mapped_column(String(128), default="")
    industry: Mapped[str] = mapped_column(String(64), default="")
    risk_level: Mapped[str] = mapped_column(String(16), default="low")
    contract_count: Mapped[int] = mapped_column(Integer, default=0)
    total_amount: Mapped[float] = mapped_column(Float, default=0)
    first_coop_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_coop_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delay_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(256), index=True)
    credit_code: Mapped[str] = mapped_column(String(64), default="")
    contact: Mapped[str] = mapped_column(String(128), default="")
    industry: Mapped[str] = mapped_column(String(64), default="")
    risk_level: Mapped[str] = mapped_column(String(16), default="low")
    contract_count: Mapped[int] = mapped_column(Integer, default=0)
    order_count: Mapped[int] = mapped_column(Integer, default=0)
    total_sales: Mapped[float] = mapped_column(Float, default=0)
    total_qty: Mapped[float] = mapped_column(Float, default=0)
    first_coop_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_coop_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_delay_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    relations: Mapped[list["CustomerRelation"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
        foreign_keys="CustomerRelation.customer_id",
    )


class CustomerRelation(Base):
    __tablename__ = "customer_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    related_customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    relation_type: Mapped[str] = mapped_column(String(32), default="custom")  # parent/child/sibling/branch/custom
    equity_ratio: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    customer: Mapped["Customer"] = relationship(
        back_populates="relations",
        foreign_keys=[customer_id],
    )


class PerformancePlan(Base):
    __tablename__ = "performance_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("managed_contracts.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft/active/completed
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    nodes: Mapped[list["PerformanceNode"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="PerformanceNode.due_date"
    )


class PerformanceNode(Base):
    __tablename__ = "performance_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("performance_plans.id"), index=True)
    title: Mapped[str] = mapped_column(String(256))
    node_type: Mapped[str] = mapped_column(String(32), default="general")  # base/payment/delivery/acceptance/deadline
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/in_progress/done/delayed/defaulted
    confirm_status: Mapped[str] = mapped_column(String(32), default="unconfirmed")  # unconfirmed/confirmed
    owner_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    primary_owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    plan: Mapped["PerformancePlan"] = relationship(back_populates="nodes")


class PerformanceAdjustment(Base):
    __tablename__ = "performance_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("performance_nodes.id"), index=True)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    evidence_path: Mapped[str] = mapped_column(String(1024), default="")
    evidence_note: Mapped[str] = mapped_column(Text, default="")
    evidence_filename: Mapped[str] = mapped_column(String(256), default="")
    new_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    new_owner_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/approved/rejected
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PerformanceAlert(Base):
    __tablename__ = "performance_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("performance_nodes.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    alert_type: Mapped[str] = mapped_column(String(32), default="upcoming")  # upcoming/due/overdue
    message: Mapped[str] = mapped_column(Text, default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    email_status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/sent/skipped/failed
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TagTaxonomy(Base):
    """Admin-managed contract tag tree: L1 / L2 / L3."""

    __tablename__ = "tag_taxonomy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[int] = mapped_column(Integer, index=True)  # 1|2|3
    code: Mapped[str] = mapped_column(String(64), default="", index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("tag_taxonomy.id"), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ErpOrder(Base):
    """Orders synced from ERP CSV/API for customer/contract linkage."""

    __tablename__ = "erp_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    order_no: Mapped[str] = mapped_column(String(128), index=True, default="")
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("managed_contracts.id"), nullable=True, index=True)
    contract_code: Mapped[str] = mapped_column(String(128), default="")
    customer_name: Mapped[str] = mapped_column(String(256), default="")
    product_name: Mapped[str] = mapped_column(String(256), default="")
    qty: Mapped[float] = mapped_column(Float, default=0)
    unit_price: Mapped[float] = mapped_column(Float, default=0)
    amount: Mapped[float] = mapped_column(Float, default=0)
    order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open")
    link_status: Mapped[str] = mapped_column(String(32), default="pending")  # linked|pending|manual
    source: Mapped[str] = mapped_column(String(32), default="csv")  # csv|erp
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ErpSyncJob(Base):
    __tablename__ = "erp_sync_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(32), default="done")  # done|failed
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    linked_count: Mapped[int] = mapped_column(Integer, default=0)
    error_log: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
