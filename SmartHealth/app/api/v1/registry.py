"""注册申报、实施路线图与风险台账接口（对应设计文档第七、八、十章）。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select

from app.api.v1.common import crud_router, ok, serialize
from app.core.deps import CurrentUser, DbSession, audit, require
from app.models.registry import (
    ClinicalTrialSite,
    GuidelineDoc,
    RegistrationMilestone,
    RegistrationPath,
    RegistrationStage,
    RiskItem,
)
from app.services import registry_service

router = APIRouter(tags=["10 注册与路线图"])

router.include_router(crud_router(
    model=RegistrationPath, prefix="/registry/paths", tag="注册路径", resource_type="registration_path",
    permission_read="compliance:read", permission_write="compliance:write",
    search_fields=("code", "product_name", "classification_code", "intended_use", "owner_name"),
    filter_fields=("status", "path_type", "device_class"),
    order_by="id", summary_template="更新注册路径 {row.code}",
))

router.include_router(crud_router(
    model=RegistrationStage, prefix="/registry/stages", tag="注册阶段", resource_type="registration_stage",
    permission_read="compliance:read", permission_write="compliance:write",
    search_fields=("code", "name", "key_actions", "deliverables", "owner_name"),
    filter_fields=("path_id", "status"),
    order_by="sort_order", summary_template="更新注册阶段 {row.code}",
))

router.include_router(crud_router(
    model=RegistrationMilestone, prefix="/registry/milestones", tag="里程碑",
    resource_type="registration_milestone",
    permission_read="compliance:read", permission_write="compliance:write",
    search_fields=("code", "title", "phase_name", "acceptance_criteria", "deliverable", "owner_name"),
    filter_fields=("phase", "status"),
    json_fields=("evidence_refs_json",), order_by="target_month",
    summary_template="更新里程碑 {row.code} {row.title}",
))

router.include_router(crud_router(
    model=RiskItem, prefix="/registry/risks", tag="风险台账", resource_type="reg_risk",
    permission_read="compliance:read", permission_write="compliance:write",
    search_fields=("code", "title", "category", "description", "impact", "response", "owner_name"),
    filter_fields=("layer", "status", "is_frontloaded", "category"),
    order_by="risk_score", summary_template="更新风险 {row.code} {row.title}",
))

router.include_router(crud_router(
    model=ClinicalTrialSite, prefix="/registry/trial-sites", tag="临床试验中心",
    resource_type="trial_site",
    permission_read="compliance:read", permission_write="compliance:write",
    search_fields=("code", "hospital", "city", "pi_name", "note"),
    filter_fields=("site_type", "ethics_status", "contract_status", "status"),
    order_by="id", summary_template="更新试验中心 {row.hospital}",
))

router.include_router(crud_router(
    model=GuidelineDoc, prefix="/registry/guidelines", tag="法规依据库",
    resource_type="guideline_doc",
    permission_read="compliance:read", permission_write=None,
    search_fields=("code", "title", "publisher", "doc_no", "key_points", "applies_to"),
    filter_fields=("category",),
    order_by="id",
))


@router.get("/registry/timeline", summary="注册时间轴（甘特数据）")
def timeline(db: DbSession, user: dict = Depends(require("compliance:read"))) -> dict:
    return ok(registry_service.registration_timeline(db))


@router.get("/registry/milestones/overview", summary="里程碑总览（按阶段分组）")
def milestones_overview(db: DbSession, user: dict = Depends(require("compliance:read"))) -> dict:
    return ok(registry_service.milestone_overview(db))


@router.get("/registry/risks/board", summary="风险看板（2×2 矩阵 + 前置风险 + 预算提示）")
def risk_board(db: DbSession, user: dict = Depends(require("compliance:read"))) -> dict:
    return ok(registry_service.risk_board(db))


@router.get("/registry/trial-sites/overview", summary="临床试验中心总览与入组进度")
def trial_site_overview(db: DbSession, user: dict = Depends(require("compliance:read"))) -> dict:
    return ok(registry_service.trial_sites(db))


@router.patch("/registry/milestones/{milestone_id}/progress", summary="更新里程碑进度（写审计链）")
def update_milestone(milestone_id: int, db: DbSession, payload: dict = Body(...),
                     user: dict = Depends(require("compliance:write"))) -> dict:
    row = db.get(RegistrationMilestone, milestone_id)
    if row is None:
        raise HTTPException(status_code=404, detail="里程碑不存在")
    registry_service.update_milestone(db, row, payload, actor=user.get("username", ""))
    db.commit()
    return ok(serialize(row, ("evidence_refs_json",)))


@router.patch("/registry/risks/{risk_id}/status", summary="更新风险状态与评分（写审计链）")
def update_risk(risk_id: int, db: DbSession, payload: dict = Body(...),
                user: dict = Depends(require("compliance:write"))) -> dict:
    row = db.get(RiskItem, risk_id)
    if row is None:
        raise HTTPException(status_code=404, detail="风险条目不存在")
    registry_service.update_risk(db, row, payload, actor=user.get("username", ""))
    db.commit()
    return ok(row.to_dict())
