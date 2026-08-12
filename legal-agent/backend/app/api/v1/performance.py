"""Performance AI API routes."""
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.roles import FEATURE_CUSTOMER, FEATURE_PERFORMANCE, FEATURE_SUPPLIER
from app.models.cms_models import ManagedContract
from app.models.models import User
from app.models.performance_models import PerformanceNode
from app.schemas.prd_schemas import (
    CustomerOut,
    CustomerRelationRequest,
    OrderLinkRequest,
    PerformanceAdjustmentRequest,
    PerformanceNodeUpdate,
    PerformanceOverview,
    PerformancePlanOut,
    SupplierOut,
)
from app.services import order_service, performance_service as svc
from app.services.admin_service import require_feature

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/overview", response_model=PerformanceOverview)
async def get_overview(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        require_feature(user, FEATURE_PERFORMANCE)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return await svc.overview(db, user)


@router.get("/suppliers", response_model=list[SupplierOut])
async def get_suppliers(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        require_feature(user, FEATURE_SUPPLIER)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    await svc.sync_partners_from_contracts(db, user)
    return await svc.list_suppliers(db, user)


@router.get("/customers", response_model=list[CustomerOut])
async def get_customers(
    merged: bool = Query(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_CUSTOMER)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    await svc.sync_partners_from_contracts(db, user)
    return await svc.list_customers(db, user, merged=merged)


@router.post("/customers/{customer_id}/relations")
async def create_relation(
    customer_id: int,
    body: CustomerRelationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_CUSTOMER)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    rel = await svc.add_customer_relation(
        db, customer_id, body.related_customer_id, body.relation_type, body.equity_ratio
    )
    return {"id": rel.id, "ok": True}


@router.post("/contracts/{contract_id}/extract", response_model=PerformancePlanOut)
async def extract_plan(
    contract_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_PERFORMANCE)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    contract = await db.get(ManagedContract, contract_id)
    if not contract or contract.user_id != user.id:
        # Allow cross-dept roles to extract any
        from app.core.roles import can_access_all_data

        if not contract or (contract.user_id != user.id and not can_access_all_data(user.role)):
            raise HTTPException(status_code=404, detail="合同不存在")
    plan = await svc.extract_performance_plan(db, contract)
    return await svc.plan_to_out(db, plan)


@router.get("/contracts/{contract_id}/plan", response_model=PerformancePlanOut)
async def get_plan(
    contract_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_PERFORMANCE)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    plan = await svc.get_plan_for_contract(db, contract_id)
    if not plan:
        contract = await db.get(ManagedContract, contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="合同不存在")
        plan = await svc.extract_performance_plan(db, contract)
    return await svc.plan_to_out(db, plan)


@router.post("/plans/{plan_id}/confirm", response_model=PerformancePlanOut)
async def confirm_plan(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_PERFORMANCE)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.performance_models import PerformancePlan

    result = await db.execute(
        select(PerformancePlan).where(PerformancePlan.id == plan_id).options(selectinload(PerformancePlan.nodes))
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="履约计划不存在")
    await svc.confirm_plan(db, plan)
    return await svc.plan_to_out(db, plan)


@router.patch("/nodes/{node_id}")
async def patch_node(
    node_id: int,
    body: PerformanceNodeUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_PERFORMANCE)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    node = await db.get(PerformanceNode, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="履约节点不存在")
    updated = await svc.update_node(db, node, body)
    return svc.node_to_out(updated)


@router.post("/nodes/{node_id}/adjust")
async def submit_adjustment(
    node_id: int,
    body: PerformanceAdjustmentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_PERFORMANCE)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        adj = await svc.submit_adjustment(db, node_id, user, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": adj.id, "status": adj.status}


@router.post("/nodes/{node_id}/evidence")
async def upload_evidence(
    node_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_PERFORMANCE)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    node = await db.get(PerformanceNode, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="履约节点不存在")
    from app.core.config import get_settings
    from app.services import object_storage

    settings = get_settings()
    content = await file.read()
    if len(content) > settings.performance_evidence_max_bytes:
        raise HTTPException(status_code=400, detail="证据文件超过大小限制")
    name = file.filename or "evidence.bin"
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    if ext and ext not in {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx", ".xlsx"}:
        raise HTTPException(status_code=400, detail="仅支持 pdf/png/jpg/doc/docx/xlsx")
    meta = object_storage.put_bytes(
        "performance_evidence", content, filename=name, user_id=user.id
    )
    return {
        "evidence_path": meta["path"],
        "evidence_filename": meta["filename"],
        "size": meta["size"],
    }


@router.get("/adjustments/{adjustment_id}/evidence")
async def download_evidence(
    adjustment_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_PERFORMANCE)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    from fastapi.responses import FileResponse
    from app.models.performance_models import PerformanceAdjustment
    from app.services import object_storage

    adj = await db.get(PerformanceAdjustment, adjustment_id)
    if not adj or not adj.evidence_path:
        raise HTTPException(status_code=404, detail="证据文件不存在")
    path = object_storage.resolve_path(adj.evidence_path)
    if not path:
        raise HTTPException(status_code=404, detail="证据文件已丢失")
    return FileResponse(
        path,
        filename=adj.evidence_filename or path.name,
        media_type="application/octet-stream",
    )


@router.post("/adjustments/{adjustment_id}/review")
async def review_adjustment(
    adjustment_id: int,
    approve: bool = Query(True),
    note: str = "",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_PERFORMANCE)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    from app.core.roles import CROSS_DEPT_ROLES

    if user.role not in CROSS_DEPT_ROLES and user.role != "system_admin":
        raise HTTPException(status_code=403, detail="仅法务/管理/财务可审批")
    try:
        adj = await svc.review_adjustment(db, adjustment_id, user, approve=approve, note=note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": adj.id, "status": adj.status}


@router.get("/adjustments/pending")
async def list_pending_adjustments(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_PERFORMANCE)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    from app.core.roles import CROSS_DEPT_ROLES

    if user.role not in CROSS_DEPT_ROLES and user.role != "system_admin":
        raise HTTPException(status_code=403, detail="仅法务/管理/财务可查看待审批")
    return await svc.list_pending_adjustments(db)


@router.get("/alerts")
async def list_alerts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_PERFORMANCE)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    # Refresh overdue + upcoming alerts on read
    await svc.refresh_alerts(db, user)
    return await svc.list_alerts(db, user)


@router.post("/alerts/{alert_id}/read")
async def mark_alert_read(
    alert_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ok = await svc.mark_alert_read(db, alert_id, user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="预警不存在")
    return {"ok": True}


@router.post("/alerts/dispatch")
async def dispatch_alerts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually refresh alerts and dispatch emails."""
    try:
        require_feature(user, FEATURE_PERFORMANCE)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    created = await svc.refresh_alerts(db, user)
    mail = await svc.dispatch_alert_emails(db)
    return {"created": created, "email": mail}


@router.post("/orders/import")
async def import_orders(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_CUSTOMER)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    content = await file.read()
    try:
        result = await order_service.import_orders_csv(
            db, content, filename=file.filename or "orders.csv", user_id=user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.get("/orders")
async def list_orders(
    customer_id: int | None = None,
    link_status: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_CUSTOMER)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return await order_service.list_orders(db, customer_id=customer_id, link_status=link_status)


@router.get("/orders/sync-jobs")
async def list_order_sync_jobs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_CUSTOMER)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return await order_service.list_sync_jobs(db)


@router.patch("/orders/{order_id}/link")
async def link_order(
    order_id: int,
    body: OrderLinkRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        require_feature(user, FEATURE_CUSTOMER)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        return await order_service.link_order(
            db, order_id, customer_id=body.customer_id, contract_id=body.contract_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
