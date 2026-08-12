"""Performance AI and partner aggregation services."""
from __future__ import annotations

import json
import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.roles import can_access_all_data
from app.models.cms_models import ManagedContract
from app.models.models import User
from app.models.performance_models import (
    Customer,
    CustomerRelation,
    PerformanceAdjustment,
    PerformanceNode,
    PerformancePlan,
    Supplier,
)
from app.schemas.prd_schemas import (
    CustomerOut,
    PerformanceNodeOut,
    PerformanceOverview,
    PerformancePlanOut,
    SupplierOut,
)


def _owner_ids(node: PerformanceNode) -> list[int]:
    try:
        data = json.loads(node.owner_ids_json or "[]")
        return [int(x) for x in data]
    except Exception:
        return []


def node_to_out(node: PerformanceNode) -> PerformanceNodeOut:
    return PerformanceNodeOut(
        id=node.id,
        title=node.title,
        node_type=node.node_type,
        due_date=node.due_date,
        duration_days=node.duration_days,
        status=node.status,
        confirm_status=node.confirm_status,
        owner_ids=_owner_ids(node),
        primary_owner_id=node.primary_owner_id,
        notes=node.notes or "",
    )


async def list_suppliers(db: AsyncSession, user: User) -> list[SupplierOut]:
    q = select(Supplier).order_by(Supplier.total_amount.desc())
    if not can_access_all_data(user.role) and user.department_id:
        q = q.where(Supplier.department_id == user.department_id)
    rows = (await db.execute(q)).scalars().all()
    return [SupplierOut.model_validate(r) for r in rows]


async def list_customers(db: AsyncSession, user: User, *, merged: bool = False) -> list[CustomerOut]:
    q = select(Customer).order_by(Customer.total_sales.desc())
    if not can_access_all_data(user.role) and user.department_id:
        q = q.where(Customer.department_id == user.department_id)
    rows = (await db.execute(q)).scalars().all()
    out: list[CustomerOut] = []
    for c in rows:
        item = CustomerOut.model_validate(c)
        rels = (
            await db.execute(select(CustomerRelation).where(CustomerRelation.customer_id == c.id))
        ).scalars().all()
        related = []
        for rel in rels:
            other = await db.get(Customer, rel.related_customer_id)
            if other:
                related.append(
                    {
                        "id": other.id,
                        "name": other.name,
                        "relation_type": rel.relation_type,
                        "equity_ratio": rel.equity_ratio,
                        "total_sales": other.total_sales,
                        "contract_count": other.contract_count,
                    }
                )
                if merged:
                    item.total_sales += other.total_sales * (rel.equity_ratio or 1.0)
                    item.contract_count += other.contract_count
                    item.order_count += other.order_count
        item.related = related
        out.append(item)
    if merged:
        out.sort(key=lambda x: x.total_sales, reverse=True)
    return out


async def add_customer_relation(
    db: AsyncSession,
    customer_id: int,
    related_customer_id: int,
    relation_type: str = "custom",
    equity_ratio: float = 1.0,
) -> CustomerRelation:
    rel = CustomerRelation(
        customer_id=customer_id,
        related_customer_id=related_customer_id,
        relation_type=relation_type,
        equity_ratio=equity_ratio,
    )
    db.add(rel)
    await db.commit()
    await db.refresh(rel)
    return rel


_DATE_PATTERNS = [
    (r"(?:合同生效|生效日期|签订日期)[^\d]{0,8}(\d{4}[-年./]\d{1,2}[-月./]\d{1,2})", "base", "合同生效"),
    (r"(?:首付款|预付款|支付.*?%|付款)[^\d]{0,20}(\d{4}[-年./]\d{1,2}[-月./]\d{1,2})", "payment", "付款节点"),
    (r"(?:交付|交货)[^\d]{0,12}(\d{4}[-年./]\d{1,2}[-月./]\d{1,2})", "delivery", "交付节点"),
    (r"(?:验收)[^\d]{0,12}(\d{4}[-年./]\d{1,2}[-月./]\d{1,2})", "acceptance", "验收节点"),
    (r"(?:到期|终止|届满)[^\d]{0,8}(\d{4}[-年./]\d{1,2}[-月./]\d{1,2})", "deadline", "到期节点"),
]


def _parse_date(raw: str) -> date | None:
    s = raw.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-").replace(".", "-")
    parts = [p for p in s.split("-") if p]
    if len(parts) < 3:
        return None
    try:
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        return None


async def extract_performance_plan(db: AsyncSession, contract: ManagedContract) -> PerformancePlan:
    existing = (
        await db.execute(select(PerformancePlan).where(PerformancePlan.contract_id == contract.id))
    ).scalar_one_or_none()
    if existing:
        return existing

    plan = PerformancePlan(contract_id=contract.id, status="draft")
    db.add(plan)
    await db.flush()

    text = contract.content_text or ""
    found: list[tuple[str, str, date]] = []
    for pattern, ntype, title in _DATE_PATTERNS:
        for m in re.finditer(pattern, text):
            d = _parse_date(m.group(1))
            if d:
                found.append((title, ntype, d))

    if not found and contract.sign_date:
        found.append(("合同生效", "base", contract.sign_date))
    if contract.expire_date:
        found.append(("合同到期", "deadline", contract.expire_date))
    if contract.effective_date and not any(x[1] == "base" for x in found):
        found.append(("合同生效", "base", contract.effective_date))

    # Deduplicate by type+date
    seen: set[tuple[str, date]] = set()
    prev: date | None = None
    for title, ntype, d in sorted(found, key=lambda x: x[2]):
        key = (ntype, d)
        if key in seen:
            continue
        seen.add(key)
        duration = (d - prev).days if prev else None
        node = PerformanceNode(
            plan_id=plan.id,
            title=title,
            node_type=ntype,
            due_date=d,
            duration_days=duration,
            status="pending",
            confirm_status="unconfirmed",
            owner_ids_json="[]",
        )
        db.add(node)
        prev = d

    await db.commit()
    result = await db.execute(
        select(PerformancePlan)
        .where(PerformancePlan.id == plan.id)
        .options(selectinload(PerformancePlan.nodes))
    )
    return result.scalar_one()


async def get_plan_for_contract(db: AsyncSession, contract_id: int) -> PerformancePlan | None:
    result = await db.execute(
        select(PerformancePlan)
        .where(PerformancePlan.contract_id == contract_id)
        .options(selectinload(PerformancePlan.nodes))
    )
    return result.scalar_one_or_none()


async def confirm_plan(db: AsyncSession, plan: PerformancePlan) -> PerformancePlan:
    for node in plan.nodes:
        if node.confirm_status != "confirmed":
            node.confirm_status = "confirmed"
        if node.status == "pending" and _owner_ids(node):
            node.status = "in_progress"
    plan.status = "active"
    from datetime import datetime, timezone

    plan.confirmed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(plan)
    return plan


async def update_node(db: AsyncSession, node: PerformanceNode, payload) -> PerformanceNode:
    if payload.title is not None:
        node.title = payload.title
    if payload.due_date is not None:
        node.due_date = payload.due_date
    if payload.duration_days is not None:
        node.duration_days = payload.duration_days
    if payload.owner_ids is not None:
        node.owner_ids_json = json.dumps(payload.owner_ids)
    if payload.primary_owner_id is not None:
        node.primary_owner_id = payload.primary_owner_id
    if payload.confirm_status is not None:
        node.confirm_status = payload.confirm_status
    if payload.status is not None:
        node.status = payload.status
    if payload.notes is not None:
        node.notes = payload.notes
    await db.commit()
    await db.refresh(node)
    return node


async def overview(db: AsyncSession, user: User) -> PerformanceOverview:
    plans = (await db.execute(select(PerformancePlan).options(selectinload(PerformancePlan.nodes)))).scalars().all()
    today = date.today()
    upcoming = 0
    overdue = 0
    pending_confirm = 0
    active = 0
    todos: list[dict] = []

    for plan in plans:
        if plan.status == "active":
            active += 1
        contract = await db.get(ManagedContract, plan.contract_id)
        contract_name = contract.name if contract else f"合同#{plan.contract_id}"
        for node in plan.nodes:
            if node.confirm_status != "confirmed":
                pending_confirm += 1
            owners = _owner_ids(node)
            is_mine = user.id in owners or node.primary_owner_id == user.id
            can_see = can_access_all_data(user.role) or is_mine
            if not can_see:
                continue
            if node.due_date and node.status not in ("done", "defaulted"):
                days = (node.due_date - today).days
                if days < 0:
                    if node.status != "defaulted":
                        node.status = "defaulted"
                    overdue += 1
                elif days <= 7:
                    upcoming += 1
                if is_mine or can_access_all_data(user.role):
                    todos.append(
                        {
                            "node_id": node.id,
                            "plan_id": plan.id,
                            "contract_id": plan.contract_id,
                            "contract_name": contract_name,
                            "title": node.title,
                            "due_date": node.due_date.isoformat() if node.due_date else None,
                            "days_left": days if node.due_date else None,
                            "status": node.status,
                            "owners": owners,
                        }
                    )

    await db.commit()
    todos.sort(key=lambda x: x.get("days_left") if x.get("days_left") is not None else 9999)
    return PerformanceOverview(
        total_plans=len(plans),
        active_plans=active,
        pending_confirm=pending_confirm,
        upcoming_alerts=upcoming,
        overdue_nodes=overdue,
        my_todos=todos[:20],
    )


async def plan_to_out(db: AsyncSession, plan: PerformancePlan) -> PerformancePlanOut:
    contract = await db.get(ManagedContract, plan.contract_id)
    return PerformancePlanOut(
        id=plan.id,
        contract_id=plan.contract_id,
        contract_name=contract.name if contract else "",
        status=plan.status,
        nodes=[node_to_out(n) for n in plan.nodes],
        confirmed_at=plan.confirmed_at,
    )


async def sync_partners_from_contracts(db: AsyncSession, user: User) -> None:
    """Aggregate suppliers/customers from managed contracts party fields."""
    contracts = (
        await db.execute(select(ManagedContract).where(ManagedContract.user_id == user.id))
    ).scalars().all()
    for c in contracts:
        party_b = (c.party_b or "").strip()
        if not party_b:
            continue
        ctype = (c.contract_type or "").lower()
        is_purchase = any(k in ctype for k in ("采购", "purchase", "供应"))
        if is_purchase:
            existing = (
                await db.execute(select(Supplier).where(Supplier.name == party_b))
            ).scalar_one_or_none()
            if not existing:
                db.add(
                    Supplier(
                        user_id=user.id,
                        department_id=user.department_id,
                        name=party_b,
                        contract_count=1,
                        total_amount=c.amount or 0,
                        first_coop_date=c.sign_date,
                        last_coop_date=c.sign_date,
                    )
                )
            else:
                existing.contract_count = (existing.contract_count or 0) + 1
                existing.total_amount = (existing.total_amount or 0) + (c.amount or 0)
                if c.sign_date:
                    existing.last_coop_date = c.sign_date
        else:
            existing = (
                await db.execute(select(Customer).where(Customer.name == party_b))
            ).scalar_one_or_none()
            if not existing:
                db.add(
                    Customer(
                        user_id=user.id,
                        department_id=user.department_id,
                        name=party_b,
                        contract_count=1,
                        total_sales=c.amount or 0,
                        first_coop_date=c.sign_date,
                        last_coop_date=c.sign_date,
                    )
                )
            else:
                existing.contract_count = (existing.contract_count or 0) + 1
                existing.total_sales = (existing.total_sales or 0) + (c.amount or 0)
                if c.sign_date:
                    existing.last_coop_date = c.sign_date
    await db.commit()


async def submit_adjustment(db: AsyncSession, node_id: int, user: User, body) -> PerformanceAdjustment:
    from app.models.performance_models import PerformanceAdjustment
    import json as _json

    node = await db.get(PerformanceNode, node_id)
    if not node:
        raise ValueError("履约节点不存在")
    if not (body.reason or "").strip():
        raise ValueError("请填写调整原因")
    evidence_path = (getattr(body, "evidence_path", None) or "").strip()
    evidence_note = (getattr(body, "evidence_note", None) or "").strip()
    evidence_filename = (getattr(body, "evidence_filename", None) or "").strip()
    if not evidence_path and not evidence_note:
        raise ValueError("请上传证据文件或填写证据说明")
    adj = PerformanceAdjustment(
        node_id=node_id,
        applicant_id=user.id,
        reason=body.reason,
        evidence_path=evidence_path,
        evidence_note=evidence_note,
        evidence_filename=evidence_filename,
        new_due_date=body.new_due_date,
        new_owner_ids_json=_json.dumps(body.new_owner_ids or []),
        status="pending",
    )
    db.add(adj)
    await db.commit()
    await db.refresh(adj)
    return adj


async def review_adjustment(
    db: AsyncSession, adjustment_id: int, reviewer: User, *, approve: bool, note: str = ""
):
    from datetime import datetime, timezone
    import json as _json
    from app.models.performance_models import PerformanceAdjustment

    adj = await db.get(PerformanceAdjustment, adjustment_id)
    if not adj:
        raise ValueError("调整申请不存在")
    if adj.status != "pending":
        raise ValueError("该申请已处理")
    adj.reviewer_id = reviewer.id
    adj.review_note = note
    adj.reviewed_at = datetime.now(timezone.utc)
    if approve:
        adj.status = "approved"
        node = await db.get(PerformanceNode, adj.node_id)
        if node:
            if adj.new_due_date:
                node.due_date = adj.new_due_date
            owners = _json.loads(adj.new_owner_ids_json or "[]")
            if owners:
                node.owner_ids_json = _json.dumps(owners)
                node.primary_owner_id = owners[0]
            if node.status == "defaulted":
                node.status = "in_progress"
    else:
        adj.status = "rejected"
    await db.commit()
    await db.refresh(adj)
    return adj


async def refresh_alerts(db: AsyncSession, user: User | None = None) -> int:
    """Create upcoming/overdue alerts. Returns count of newly created alerts."""
    from app.core.config import get_settings
    from app.models.performance_models import PerformanceAlert, PerformancePlan

    settings = get_settings()
    days = getattr(settings, "performance_alert_days", 7) or 7
    today = date.today()
    plans = (
        await db.execute(
            select(PerformancePlan)
            .where(PerformancePlan.status == "active")
            .options(selectinload(PerformancePlan.nodes))
        )
    ).scalars().all()

    created = 0
    fallback_uid = user.id if user else None
    for plan in plans:
        for node in plan.nodes:
            if node.confirm_status != "confirmed" or not node.due_date:
                continue
            if node.status in ("done",):
                continue
            owners = _owner_ids(node)
            if node.primary_owner_id and node.primary_owner_id not in owners:
                owners.append(node.primary_owner_id)
            delta = (node.due_date - today).days
            alert_type = None
            message = ""
            if delta < 0:
                node.status = "defaulted"
                alert_type = "overdue"
                message = f"履约节点「{node.title}」已逾期 {-delta} 天，已标记违约"
            elif delta <= days:
                alert_type = "upcoming"
                message = f"履约节点「{node.title}」将于 {delta} 天后到期（{node.due_date}）"
            if not alert_type:
                continue
            targets = owners or ([fallback_uid] if fallback_uid else [])
            for uid in targets:
                if not uid:
                    continue
                exists = (
                    await db.execute(
                        select(PerformanceAlert).where(
                            PerformanceAlert.node_id == node.id,
                            PerformanceAlert.user_id == uid,
                            PerformanceAlert.alert_type == alert_type,
                            PerformanceAlert.is_read.is_(False),
                        )
                    )
                ).scalar_one_or_none()
                if exists:
                    continue
                db.add(
                    PerformanceAlert(
                        node_id=node.id,
                        user_id=uid,
                        alert_type=alert_type,
                        message=message,
                        email_status="pending",
                    )
                )
                created += 1
    await db.commit()
    await dispatch_alert_emails(db)
    return created


async def dispatch_alert_emails(db: AsyncSession) -> dict:
    """Send pending alert emails based on channel config."""
    from datetime import datetime, timezone

    from app.core.config import get_settings
    from app.models.performance_models import PerformanceAlert
    from app.services import email_service

    settings = get_settings()
    channels = {c.strip() for c in (settings.performance_alert_channels or "").split(",") if c.strip()}
    if "email" not in channels:
        return {"sent": 0, "skipped": 0, "failed": 0}

    pending = (
        await db.execute(
            select(PerformanceAlert)
            .where(PerformanceAlert.email_status == "pending")
            .order_by(PerformanceAlert.id)
            .limit(100)
        )
    ).scalars().all()

    sent = skipped = failed = 0
    for alert in pending:
        user = await db.get(User, alert.user_id)
        email = (user.email if user else "") or ""
        subject = f"[法务Agent预警] {alert.alert_type}"
        body = (
            f"{alert.message}\n\n"
            f"请登录法务Agent查看履约总览并处理。\n"
            f"预警ID: {alert.id}\n"
        )
        if not email:
            alert.email_status = "skipped"
            alert.email_error = "用户未配置邮箱"
            skipped += 1
            continue
        ok, err = email_service.send_mail(email, subject, body)
        if ok:
            alert.email_status = "sent"
            alert.email_sent_at = datetime.now(timezone.utc)
            alert.email_error = ""
            sent += 1
        elif err == "smtp_disabled":
            alert.email_status = "skipped"
            alert.email_error = "SMTP未启用（已记录，待开启后可重派）"
            skipped += 1
        else:
            alert.email_status = "failed"
            alert.email_error = err[:500]
            failed += 1
    await db.commit()
    return {"sent": sent, "skipped": skipped, "failed": failed}


async def list_alerts(db: AsyncSession, user: User) -> list[dict]:
    from app.models.performance_models import PerformanceAlert

    rows = (
        await db.execute(
            select(PerformanceAlert)
            .where(PerformanceAlert.user_id == user.id)
            .order_by(PerformanceAlert.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "node_id": r.node_id,
            "alert_type": r.alert_type,
            "message": r.message,
            "is_read": r.is_read,
            "email_status": getattr(r, "email_status", None) or "pending",
            "email_sent_at": r.email_sent_at.isoformat() if getattr(r, "email_sent_at", None) else None,
            "email_error": getattr(r, "email_error", "") or "",
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


async def mark_alert_read(db: AsyncSession, alert_id: int, user_id: int) -> bool:
    from app.models.performance_models import PerformanceAlert

    alert = await db.get(PerformanceAlert, alert_id)
    if not alert or alert.user_id != user_id:
        return False
    alert.is_read = True
    await db.commit()
    return True


async def list_pending_adjustments(db: AsyncSession) -> list[dict]:
    from app.models.cms_models import ManagedContract
    from app.models.performance_models import PerformanceAdjustment, PerformanceNode, PerformancePlan

    rows = (
        await db.execute(
            select(PerformanceAdjustment)
            .where(PerformanceAdjustment.status == "pending")
            .order_by(PerformanceAdjustment.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    out = []
    for adj in rows:
        node = await db.get(PerformanceNode, adj.node_id)
        plan = await db.get(PerformancePlan, node.plan_id) if node else None
        contract = await db.get(ManagedContract, plan.contract_id) if plan else None
        note = getattr(adj, "evidence_note", "") or ""
        if not note and adj.evidence_path and not adj.evidence_path.startswith("performance_evidence"):
            note = adj.evidence_path
        out.append(
            {
                "id": adj.id,
                "node_id": adj.node_id,
                "node_title": node.title if node else "",
                "contract_id": plan.contract_id if plan else None,
                "contract_name": contract.name if contract else "",
                "reason": adj.reason,
                "evidence_note": note,
                "evidence_path": adj.evidence_path if adj.evidence_path.startswith("performance_evidence") else "",
                "evidence_filename": getattr(adj, "evidence_filename", "") or "",
                "new_due_date": adj.new_due_date.isoformat() if adj.new_due_date else None,
                "applicant_id": adj.applicant_id,
                "created_at": adj.created_at.isoformat() if adj.created_at else None,
            }
        )
    return out
