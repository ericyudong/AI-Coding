"""运营看板、团队编制与投入产出接口（对应设计文档第九章、第十一章）。

口径约定（与设计文档一致）：成本只保存**相对结构比例**，不落绝对金额。
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select

from app.api.v1.common import crud_router, ok, serialize
from app.core.deps import CurrentUser, DbSession, audit, require
from app.models.ops import CostStructure, KpiSnapshot, RevenuePath, StrategicDecision, TeamRole
from app.services import ops_service

router = APIRouter(tags=["11 运营看板"])

router.include_router(crud_router(
    model=TeamRole, prefix="/ops/team-roles", tag="团队编制", resource_type="team_role",
    permission_read="ops:read", permission_write="ops:write",
    search_fields=("code", "role_name", "skills", "responsibility", "note"),
    filter_fields=("cluster", "stage", "is_mandatory"),
    order_by="sort_order", summary_template="更新团队编制 {row.code} {row.role_name}",
))

router.include_router(crud_router(
    model=CostStructure, prefix="/ops/costs", tag="成本结构", resource_type="cost_structure",
    permission_read="ops:read", permission_write="ops:write",
    search_fields=("code", "category", "note"),
    filter_fields=("elasticity", "phase"),
    order_by="sort_order", summary_template="更新成本项 {row.category}",
))

router.include_router(crud_router(
    model=RevenuePath, prefix="/ops/revenue-paths", tag="收入路径", resource_type="revenue_path",
    permission_read="ops:read", permission_write="ops:write",
    search_fields=("code", "name", "prerequisite", "note"),
    filter_fields=("phase", "path_type", "status"),
    order_by="id", summary_template="更新收入路径 {row.name}",
))

router.include_router(crud_router(
    model=KpiSnapshot, prefix="/ops/kpi-snapshots", tag="KPI 快照", resource_type="kpi_snapshot",
    permission_read="ops:read", permission_write=None,
    search_fields=("snapshot_date",),
    filter_fields=("snapshot_date",),
    order_by="snapshot_date",
))

router.include_router(crud_router(
    model=StrategicDecision, prefix="/ops/decisions", tag="立项决策", resource_type="strategic_decision",
    permission_read="ops:read", permission_write="ops:write",
    search_fields=("code", "title", "content", "rationale", "owner_name"),
    filter_fields=("decision_type", "status"),
    json_fields=("action_items_json",), order_by="sort_order",
    summary_template="更新立项决策 {row.code} {row.title}",
))


@router.get("/ops/dashboard", summary="立项决策看板（决策者关心的 8 个数字）")
def dashboard(db: DbSession, user: dict = Depends(require("ops:read"))) -> dict:
    return ok(ops_service.dashboard(db))


@router.get("/ops/team-plan", summary="团队编制计划（首期 17—25 人，建议 18 人起步）")
def team_plan(db: DbSession, user: dict = Depends(require("ops:read"))) -> dict:
    return ok(ops_service.team_plan(db))


@router.get("/ops/cost-structure", summary="成本结构（相对比例）")
def cost_structure(db: DbSession, user: dict = Depends(require("ops:read"))) -> dict:
    return ok(ops_service.cost_structure(db))


@router.get("/ops/revenue-plan", summary="收入路径规划（分阶段现金流设计）")
def revenue_plan(db: DbSession, user: dict = Depends(require("ops:read"))) -> dict:
    return ok(ops_service.revenue_paths(db))


@router.get("/ops/decision-board", summary="立项决策事项与首期动作")
def decision_board(db: DbSession, user: dict = Depends(require("ops:read"))) -> dict:
    items = ops_service.strategic_decisions(db)
    return ok({
        "items": items,
        "total": len(items),
        "note": (
            "立项请求 = 批准「双轨制路径 + 三项前置动作」。"
            "本页把「需要委员拍板的事」与「批准后 90 天内可验证的产出」写在一起。"
        ),
    })


@router.post("/ops/kpi-snapshots", summary="生成当期 KPI 快照")
def snapshot(db: DbSession, payload: dict = Body(default={}),
             user: dict = Depends(require("ops:write"))) -> dict:
    row = ops_service.snapshot_kpi(db, snapshot_date=str(payload.get("snapshot_date") or ""))
    audit(db, user, action="snapshot_kpi", resource_type="kpi_snapshot", resource_id=row.id,
          summary=f"生成 KPI 快照 {row.snapshot_date}（AUROC {row.model_auroc:.4f}）")
    db.commit()
    return ok(row.to_dict())


@router.patch("/ops/decisions/{decision_id}/status", summary="更新立项决策状态")
def update_decision(decision_id: int, db: DbSession, payload: dict = Body(...),
                    user: dict = Depends(require("ops:write"))) -> dict:
    row = db.get(StrategicDecision, decision_id)
    if row is None:
        raise HTTPException(status_code=404, detail="决策事项不存在")
    status_value = str(payload.get("status") or "")
    if status_value and status_value not in ("proposed", "approved", "rejected", "deferred"):
        raise HTTPException(status_code=422, detail="status 仅支持 proposed/approved/rejected/deferred")
    changed = row.update_from(payload, allowed=("status", "content", "owner_name", "decided_at",
                                                "rationale", "action_items_json"))
    db.flush()
    audit(db, user, action="update_decision", resource_type="strategic_decision", resource_id=row.id,
          summary=f"更新立项决策 {row.code} 状态为 {row.status}：{', '.join(changed) or '无变化'}",
          payload={"changed": changed}, risk_level="attention" if status_value == "approved" else "normal")
    db.commit()
    return ok(serialize(row, ("action_items_json",)))
