"""合规与注册支持接口（对应设计文档第七章）。"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.api.v1.common import crud_router, list_query, ok, serialize
from app.api.v1.common import job_brief, want_async
from app.core.audit import recent_audits, verify_chain
from app.core.deps import CurrentUser, DbSession, audit, require
from app.models.compliance import (
    REVIEW_GROUP_LABELS,
    ChangeRegistration,
    ConsentRecord,
    DataBoundaryCheck,
    EthicsRecord,
    ExplainabilityPackage,
    ReviewQuestionAnswer,
    SecurityAssessment,
)
from app.models.modeling import ModelVersion
from app.services import compliance_service
from app.services import job_service

router = APIRouter(tags=["08 合规与注册"])

router.include_router(crud_router(
    model=EthicsRecord, prefix="/compliance/ethics", tag="伦理审批", resource_type="ethics_record",
    permission_read="compliance:read", permission_write="compliance:write",
    search_fields=("code", "hospital", "ethics_no", "scope", "owner_name"),
    filter_fields=("status", "hospital", "use_purpose"),
    order_by="id", summary_template="更新伦理审批 {row.code}",
))

router.include_router(crud_router(
    model=ConsentRecord, prefix="/compliance/consents", tag="知情同意", resource_type="consent_record",
    permission_read="compliance:read", permission_write="compliance:write",
    search_fields=("code", "document_ref", "waiver_reason"),
    filter_fields=("consent_type", "status"),
    order_by="id", summary_template="更新知情同意台账 {row.code}",
))

router.include_router(crud_router(
    model=SecurityAssessment, prefix="/compliance/assessments", tag="检测与测评",
    resource_type="security_assessment",
    permission_read="compliance:read", permission_write="compliance:write",
    search_fields=("code", "name", "organization", "report_no", "note"),
    filter_fields=("assessment_type", "result"),
    json_fields=("issues_json",), order_by="id",
    summary_template="更新检测测评 {row.code} {row.name}",
))

router.include_router(crud_router(
    model=ChangeRegistration, prefix="/compliance/change-registrations", tag="变更注册",
    resource_type="change_registration",
    permission_read="compliance:read", permission_write="compliance:write",
    search_fields=("code", "title", "from_version", "to_version", "impact_analysis"),
    filter_fields=("change_type", "status", "algorithm_unchanged"),
    order_by="id", summary_template="更新变更注册 {row.code}",
))

router.include_router(crud_router(
    model=DataBoundaryCheck, prefix="/compliance/boundary-checks", tag="数据不出域校验",
    resource_type="data_boundary_check",
    permission_read="compliance:read", permission_write=None,
    search_fields=("code", "scope", "checked_by", "note"),
    filter_fields=("passed",),
    json_fields=("checks_json", "violations_json"), order_by="id",
))


# ------------------------------------------------------------------ 审计链
@router.get("/compliance/audit-chain", summary="审计链记录（倒序）")
def audit_chain(db: DbSession, user: dict = Depends(require("compliance:read")),
                limit: int = Query(50, ge=1, le=500),
                resource_type: str = Query(""),
                action: str = Query("")) -> dict:
    from app.models.compliance import AuditChainRecord

    stmt = select(AuditChainRecord).order_by(AuditChainRecord.seq.desc()).limit(limit)
    if resource_type:
        stmt = (select(AuditChainRecord).where(AuditChainRecord.resource_type == resource_type)
                .order_by(AuditChainRecord.seq.desc()).limit(limit))
    if action:
        stmt = (select(AuditChainRecord).where(AuditChainRecord.action == action)
                .order_by(AuditChainRecord.seq.desc()).limit(limit))
    rows = list(db.execute(stmt).scalars())
    return ok({
        "items": [r.to_dict() for r in rows],
        "total": int(db.execute(select(func.count(AuditChainRecord.id))).scalar() or 0),
        "algorithm": "record_hash = SHA256(prev_hash || canonical_json(payload))",
    })


@router.get("/compliance/audit-chain/verify", summary="校验审计链完整性")
def audit_verify(db: DbSession, user: dict = Depends(require("compliance:read")),
                 limit: int = Query(0, ge=0, description="0 表示全量校验")) -> dict:
    return ok(verify_chain(db, limit=limit or None))


# ------------------------------------------------------------------ 可解释性
@router.get("/compliance/explainability", summary="可解释性四件套（空间/语义/量化/拒识）")
def explainability(db: DbSession, user: dict = Depends(require("compliance:read")),
                   model_version_id: int = Query(0)) -> dict:
    stmt = select(ExplainabilityPackage).order_by(ExplainabilityPackage.id.desc())
    if model_version_id:
        stmt = (select(ExplainabilityPackage)
                .where(ExplainabilityPackage.model_version_id == model_version_id)
                .order_by(ExplainabilityPackage.id.desc()))
    rows = list(db.execute(stmt).scalars())
    return ok({
        "items": [{**r.to_dict(), "items": json.loads(r.items_json or "[]")} for r in rows],
        "total": len(rows),
        "framework": [
            {"key": "spatial", "label": "空间可解释", "question": "决策依据在切片的哪个位置？"},
            {"key": "semantic", "label": "语义可解释", "question": "依据的形态学特征是什么？"},
            {"key": "quantitative", "label": "量化可解释", "question": "结论有多确定？"},
            {"key": "rejection", "label": "拒识机制", "question": "什么情况下会拒绝给出结论？"},
        ],
        "note": "四件套同时是 Agent「证据强制引用」的对外说明材料。",
    })


@router.post("/compliance/explainability/rebuild", summary="重建可解释性材料")
def rebuild_explainability(db: DbSession, payload: dict = Body(default={}),
                           user: dict = Depends(require("compliance:write"))) -> dict:
    if want_async(payload):
        job = job_service.submit_explainability(
            db, model_version_id=payload.get("model_version_id"),
            actor=user.get("username", ""), actor_name=user.get("real_name", ""))
        return ok({"async": True, "job": job_brief(job)}, message="可解释性重建作业已提交")

    version_id = payload.get("model_version_id")
    if version_id:
        version = db.get(ModelVersion, int(version_id))
    else:
        version = db.execute(
            select(ModelVersion).where(ModelVersion.is_registration_candidate.is_(True))
            .order_by(ModelVersion.id.desc()).limit(1)
        ).scalar_one_or_none() or db.execute(
            select(ModelVersion).order_by(ModelVersion.id.desc()).limit(1)
        ).scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="没有可用的模型版本")
    package = compliance_service.build_explainability_package(
        db, version, created_by=user.get("username", "")
    )
    db.commit()
    return ok({**package.to_dict(), "items": json.loads(package.items_json or "[]")})


# ------------------------------------------------------------------ 审评关口
@router.get("/compliance/review-answers", summary="审评三道关口应答台账")
def review_answers(db: DbSession, user: dict = Depends(require("compliance:read")),
                   group_key: str = Query("")) -> dict:
    stmt = select(ReviewQuestionAnswer).order_by(ReviewQuestionAnswer.group_key,
                                                 ReviewQuestionAnswer.sort_order)
    if group_key:
        stmt = (select(ReviewQuestionAnswer)
                .where(ReviewQuestionAnswer.group_key == group_key)
                .order_by(ReviewQuestionAnswer.sort_order))
    rows = list(db.execute(stmt).scalars())
    return ok({
        "items": [{**r.to_dict(), "evidence_refs": json.loads(r.evidence_refs_json or "[]"),
                   "group_label": REVIEW_GROUP_LABELS.get(r.group_key, r.group_key)}
                  for r in rows],
        "groups": [
            {"key": key, "label": label} for key, label in REVIEW_GROUP_LABELS.items()
        ],
        "framework": "审评只问三件事：数据可溯源、算法可解释、临床可验证 —— 技术选型必须以此倒推。",
    })


@router.patch("/compliance/review-answers/{answer_id}", summary="更新应答台账")
def update_review_answer(answer_id: int, db: DbSession, payload: dict = Body(...),
                         user: dict = Depends(require("compliance:write"))) -> dict:
    row = db.get(ReviewQuestionAnswer, answer_id)
    if row is None:
        raise HTTPException(status_code=404, detail="应答记录不存在")
    changed = row.update_from(payload, allowed=("answer", "status", "owner_name", "gap_note",
                                                "evidence_refs_json", "regulation_ref"))
    db.flush()
    audit(db, user, action="update_review_answer", resource_type="review_answer",
          resource_id=row.id, summary=f"更新审评应答 {row.code}：{', '.join(changed) or '无变化'}",
          payload={"changed": changed})
    db.commit()
    return ok(row.to_dict())


# ------------------------------------------------------------------ 就绪度
@router.get("/compliance/readiness", summary="注册就绪度体检（缺口 → 阻断哪个审评关口）")
def readiness(db: DbSession, user: dict = Depends(require("compliance:read"))) -> dict:
    return ok(compliance_service.registration_readiness(db))


@router.post("/compliance/boundary-check/run", summary="执行数据不出域校验")
def run_boundary_check(db: DbSession, payload: dict = Body(default={}),
                       user: dict = Depends(require("compliance:write"))) -> dict:
    if want_async(payload):
        job = job_service.submit_boundary_check(db, actor=user.get("username", ""),
                                                actor_name=user.get("real_name", ""))
        return ok({"async": True, "job": job_brief(job)}, message="数据不出域校验作业已提交")
    record = compliance_service.run_boundary_check(db, checked_by=user.get("username", ""))
    db.commit()
    return ok({**record.to_dict(),
               "checks": json.loads(record.checks_json or "[]"),
               "violations": json.loads(record.violations_json or "[]")})


@router.get("/compliance/overview", summary="合规总览")
def overview(db: DbSession, user: dict = Depends(require("compliance:read"))) -> dict:
    readiness_payload = compliance_service.registration_readiness(db)
    chain = verify_chain(db)
    ethics = int(db.execute(select(func.count(EthicsRecord.id))).scalar() or 0)
    consents = list(db.execute(select(ConsentRecord)).scalars())
    coverage = (
        sum(c.covered_count for c in consents) / max(sum(c.case_count for c in consents), 1)
        if consents else 0.0
    )
    boundary = db.execute(
        select(DataBoundaryCheck).order_by(DataBoundaryCheck.id.desc()).limit(1)
    ).scalar_one_or_none()
    return ok({
        "readiness": readiness_payload,
        "audit_chain": chain,
        "ethics_count": ethics,
        "consent_case_total": sum(c.case_count for c in consents),
        "consent_coverage_rate": round(coverage, 6),
        "assessment_total": int(db.execute(select(func.count(SecurityAssessment.id))).scalar() or 0),
        "assessment_passed": int(db.execute(
            select(func.count(SecurityAssessment.id)).where(SecurityAssessment.result == "passed")
        ).scalar() or 0),
        "latest_boundary_check": boundary.to_dict() if boundary else None,
        "review_group_labels": REVIEW_GROUP_LABELS,
    })
