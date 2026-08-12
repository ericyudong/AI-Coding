"""ERP / order sync via CSV import (api mode placeholder)."""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.cms_models import ManagedContract
from app.models.performance_models import Customer, ErpOrder, ErpSyncJob


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _f(raw: str | None) -> float:
    if not raw:
        return 0.0
    try:
        return float(str(raw).replace(",", "").strip())
    except ValueError:
        return 0.0


async def _link_order(db: AsyncSession, order: ErpOrder) -> None:
    if order.contract_code:
        c = (
            await db.execute(
                select(ManagedContract).where(ManagedContract.code == order.contract_code).limit(1)
            )
        ).scalar_one_or_none()
        if c:
            order.contract_id = c.id
    if order.customer_name and not order.customer_id:
        cust = (
            await db.execute(
                select(Customer).where(Customer.name == order.customer_name).limit(1)
            )
        ).scalar_one_or_none()
        if cust:
            order.customer_id = cust.id
    if order.customer_id or order.contract_id:
        order.link_status = "linked"
    else:
        order.link_status = "pending"


async def refresh_customer_order_stats(db: AsyncSession, customer_id: int) -> None:
    cust = await db.get(Customer, customer_id)
    if not cust:
        return
    stats = (
        await db.execute(
            select(func.count(ErpOrder.id), func.coalesce(func.sum(ErpOrder.amount), 0),
                   func.coalesce(func.sum(ErpOrder.qty), 0))
            .where(ErpOrder.customer_id == customer_id)
        )
    ).one()
    cust.order_count = int(stats[0] or 0)
    cust.total_sales = float(stats[1] or 0)
    cust.total_qty = float(stats[2] or 0)


async def import_orders_csv(
    db: AsyncSession,
    content: bytes,
    *,
    filename: str,
    user_id: int | None,
) -> dict:
    settings = get_settings()
    if settings.erp_sync_mode not in ("manual_import", "api"):
        raise ValueError(f"不支持的 erp_sync_mode: {settings.erp_sync_mode}")

    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV 无表头")

    def col(*names: str) -> str | None:
        lower = {h.lower().strip(): h for h in (reader.fieldnames or [])}
        for n in names:
            if n.lower() in lower:
                return lower[n.lower()]
        return None

    c_ext = col("external_id", "id", "订单ID")
    c_no = col("order_no", "order_number", "订单号")
    c_cust = col("customer_name", "customer", "客户名称", "客户")
    c_code = col("contract_code", "contract", "合同编号")
    c_prod = col("product_name", "product", "产品", "商品")
    c_qty = col("qty", "quantity", "数量")
    c_price = col("unit_price", "price", "单价")
    c_amt = col("amount", "total", "金额")
    c_od = col("order_date", "date", "下单日期")
    c_dd = col("delivery_date", "delivery", "交付日期")
    c_st = col("status", "状态")

    count = 0
    linked = 0
    errors: list[str] = []
    touched_customers: set[int] = set()

    for i, row in enumerate(reader, start=2):
        try:
            order_no = (row.get(c_no) or "").strip() if c_no else ""
            external_id = ((row.get(c_ext) or "").strip() if c_ext else "") or order_no or f"row-{i}"
            if not external_id:
                errors.append(f"第{i}行缺少订单标识")
                continue
            existing = (
                await db.execute(select(ErpOrder).where(ErpOrder.external_id == external_id))
            ).scalar_one_or_none()
            payload = {
                "order_no": order_no or external_id,
                "customer_name": (row.get(c_cust) or "").strip() if c_cust else "",
                "contract_code": (row.get(c_code) or "").strip() if c_code else "",
                "product_name": (row.get(c_prod) or "").strip() if c_prod else "",
                "qty": _f(row.get(c_qty) if c_qty else None),
                "unit_price": _f(row.get(c_price) if c_price else None),
                "amount": _f(row.get(c_amt) if c_amt else None),
                "order_date": _parse_date(row.get(c_od) if c_od else None),
                "delivery_date": _parse_date(row.get(c_dd) if c_dd else None),
                "status": ((row.get(c_st) or "open").strip() if c_st else "open"),
                "source": "csv",
                "raw_json": json.dumps(row, ensure_ascii=False),
            }
            if payload["amount"] <= 0 and payload["qty"] and payload["unit_price"]:
                payload["amount"] = payload["qty"] * payload["unit_price"]
            if existing:
                for k, v in payload.items():
                    setattr(existing, k, v)
                order = existing
            else:
                order = ErpOrder(external_id=external_id, **payload)
                db.add(order)
            await db.flush()
            await _link_order(db, order)
            if order.link_status == "linked":
                linked += 1
            if order.customer_id:
                touched_customers.add(order.customer_id)
            count += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"第{i}行: {exc}")

    for cid in touched_customers:
        await refresh_customer_order_stats(db, cid)

    job = ErpSyncJob(
        filename=filename,
        status="done" if not errors or count else "failed",
        row_count=count,
        linked_count=linked,
        error_log="\n".join(errors[:50]),
        created_by=user_id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return {
        "job_id": job.id,
        "row_count": count,
        "linked_count": linked,
        "errors": errors[:20],
        "status": job.status,
    }


async def list_orders(
    db: AsyncSession,
    *,
    customer_id: int | None = None,
    link_status: str | None = None,
    limit: int = 100,
) -> list[dict]:
    q = select(ErpOrder).order_by(ErpOrder.created_at.desc()).limit(limit)
    if customer_id:
        q = q.where(ErpOrder.customer_id == customer_id)
    if link_status:
        q = q.where(ErpOrder.link_status == link_status)
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "id": o.id,
            "external_id": o.external_id,
            "order_no": o.order_no,
            "customer_id": o.customer_id,
            "contract_id": o.contract_id,
            "contract_code": o.contract_code,
            "customer_name": o.customer_name,
            "product_name": o.product_name,
            "qty": o.qty,
            "unit_price": o.unit_price,
            "amount": o.amount,
            "order_date": o.order_date.isoformat() if o.order_date else None,
            "delivery_date": o.delivery_date.isoformat() if o.delivery_date else None,
            "status": o.status,
            "link_status": o.link_status,
            "source": o.source,
        }
        for o in rows
    ]


async def link_order(
    db: AsyncSession,
    order_id: int,
    *,
    customer_id: int | None = None,
    contract_id: int | None = None,
) -> dict:
    order = await db.get(ErpOrder, order_id)
    if not order:
        raise ValueError("订单不存在")
    if customer_id is not None:
        order.customer_id = customer_id or None
    if contract_id is not None:
        order.contract_id = contract_id or None
        if contract_id:
            c = await db.get(ManagedContract, contract_id)
            if c:
                order.contract_code = c.code
    order.link_status = "manual" if (order.customer_id or order.contract_id) else "pending"
    if order.customer_id or order.contract_id:
        if order.link_status != "manual":
            order.link_status = "linked"
        else:
            order.link_status = "manual"
    await db.commit()
    if order.customer_id:
        await refresh_customer_order_stats(db, order.customer_id)
        await db.commit()
    items = await list_orders(db, limit=1)
    # return refreshed
    refreshed = (await list_orders(db, limit=500))
    for it in refreshed:
        if it["id"] == order_id:
            return it
    return items[0] if items else {}


async def list_sync_jobs(db: AsyncSession, limit: int = 20) -> list[dict]:
    rows = (
        await db.execute(select(ErpSyncJob).order_by(ErpSyncJob.created_at.desc()).limit(limit))
    ).scalars().all()
    return [
        {
            "id": j.id,
            "filename": j.filename,
            "status": j.status,
            "row_count": j.row_count,
            "linked_count": j.linked_count,
            "error_log": j.error_log,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in rows
    ]


async def pull_orders_from_api(db: AsyncSession, user_id: int | None = None) -> dict:
    """Placeholder for real-time ERP API sync (erp_sync_mode=api)."""
    settings = get_settings()
    if settings.erp_sync_mode != "api":
        raise ValueError("当前为 manual_import 模式，请使用 CSV 导入；或设置 ERP_SYNC_MODE=api")
    if not settings.erp_api_base_url:
        raise ValueError("ERP_API_BASE_URL 未配置")
    # α：预留接口，避免假成功
    raise ValueError("ERP API 适配器尚未对接，请先使用 CSV 导入")
