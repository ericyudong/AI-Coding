"""智慧医疗 Agent 接口（对应设计文档第五章）。

这是整个平台差异化能力的对外出口：会话运行、五智能体轨迹、证据链、鉴别诊断、
多轨迹投票、医生终审，以及能力边界声明。
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.api.v1.common import crud_router, list_query, ok, serialize
from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, audit, require
from app.models.agent import (
    AGENT_ROLE_LABELS,
    AGENT_ROLES,
    AgentCapability,
    AgentEvidence,
    AgentProbe,
    AgentSession,
    AgentStep,
    ReviewTicket,
)
from app.models.asset import Slide
from app.models.modeling import ModelVersion
from app.services.agent_service import (
    TRIAGE_BUDGET,
    NAVIGATION_BUDGET,
    CONFIRM_BUDGET,
    MORPHOLOGY_RULES,
    REJECT_RULES,
    agent_metrics,
    run_agent_session,
    session_detail,
)

router = APIRouter(tags=["06 智慧医疗 Agent"])

router.include_router(crud_router(
    model=AgentSession, prefix="/agents/sessions", tag="Agent 会话", resource_type="agent_session",
    permission_read="agent:read", permission_write=None,
    search_fields=("code", "slide_code", "question", "verdict", "model_version_label"),
    filter_fields=("status", "task_code", "rejected", "confidence_level", "slide_id"),
    json_fields=("plan_json",), order_by="id",
))

router.include_router(crud_router(
    model=AgentStep, prefix="/agents/steps", tag="智能体轨迹", resource_type="agent_step",
    permission_read="agent:read", permission_write=None,
    search_fields=("action", "agent", "input_summary", "output_summary"),
    filter_fields=("agent", "status", "session_id"),
    json_fields=("region_json", "refs_json"), order_by="id",
))

router.include_router(crud_router(
    model=AgentEvidence, prefix="/agents/evidence", tag="证据条目", resource_type="agent_evidence",
    permission_read="agent:read", permission_write=None,
    search_fields=("claim", "source_desc", "ref_id"),
    filter_fields=("evidence_type", "strength", "agent", "session_id"),
    json_fields=("region_json",), order_by="id",
))

router.include_router(crud_router(
    model=AgentProbe, prefix="/agents/probes", tag="探查记录", resource_type="agent_probe",
    permission_read="agent:read", permission_write=None,
    search_fields=("reason",),
    filter_fields=("agent", "decision", "magnification", "session_id", "hit_lesion"),
    order_by="id",
))

router.include_router(crud_router(
    model=AgentCapability, prefix="/agents/capabilities", tag="能力边界声明",
    resource_type="agent_capability",
    permission_read="agent:read", permission_write="agent:run",
    search_fields=("code", "declaration_text"),
    filter_fields=("status",),
    json_fields=("supported_organs_json", "supported_tasks_json", "unsupported_json"),
    order_by="id",
))


# ------------------------------------------------------------------ 会话运行
@router.post("/agents/run", summary="运行 Agent 分析会话（编排 → 分诊 → 导航 → 描述 → 诊断）")
def run(db: DbSession, payload: dict = Body(...),
        user: dict = Depends(require("agent:run"))) -> dict:
    slide_id = payload.get("slide_id")
    slide_code = payload.get("slide_code")
    slide = None
    if slide_id:
        slide = db.get(Slide, int(slide_id))
    elif slide_code:
        slide = db.execute(select(Slide).where(Slide.code == str(slide_code))).scalar_one_or_none()
    if slide is None:
        raise HTTPException(status_code=404, detail="切片不存在，请提供 slide_id 或 slide_code")

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
        raise HTTPException(status_code=404, detail="没有可用的模型版本，请先执行训练")

    try:
        outcome = run_agent_session(
            db, slide=slide, model_version=version,
            task_code=str(payload.get("task_code") or "lymph_node_metastasis"),
            question=str(payload.get("question") or ""),
            max_regions=payload.get("max_regions"),
            trajectories=payload.get("trajectories"),
            deployment_env=user.get("deployment_env"),
            created_by=user.get("username", ""),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Agent 会话执行失败：{exc}") from exc

    db.commit()
    detail = session_detail(db, outcome["session"].id)
    return ok(detail)


@router.get("/agents/sessions/{session_id}/detail", summary="Agent 会话详情（完整可追溯链）")
def detail(session_id: int, db: DbSession,
           user: dict = Depends(require("agent:read"))) -> dict:
    payload = session_detail(db, session_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ok(payload)


@router.get("/agents/sessions/{session_id}/evidence-chain", summary="证据链（每条结论 → 证据 → 来源）")
def evidence_chain(session_id: int, db: DbSession,
                   user: dict = Depends(require("agent:read"))) -> dict:
    session = db.get(AgentSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    evidence = sorted(session.evidence, key=lambda e: e.seq)
    steps = sorted(session.steps, key=lambda s: s.seq)
    by_seq = {e.seq: e for e in evidence}

    chain = []
    for step in steps:
        refs = json.loads(step.refs_json or "[]")
        chain.append({
            "step_seq": step.seq,
            "agent": step.agent,
            "agent_label": step.agent_label,
            "action": step.action,
            "output_summary": step.output_summary,
            "references": [
                {
                    "evidence_seq": ref,
                    "claim": by_seq[ref].claim if ref in by_seq else "(引用已失效)",
                    "evidence_type": by_seq[ref].evidence_type if ref in by_seq else "",
                    "source_desc": by_seq[ref].source_desc if ref in by_seq else "",
                    "region": json.loads(by_seq[ref].region_json or "{}") if ref in by_seq else {},
                    "strength": by_seq[ref].strength if ref in by_seq else "",
                }
                for ref in refs
            ],
        })

    orphan = [e.seq for e in evidence if not any(e.seq in json.loads(s.refs_json or "[]") for s in steps)]
    return ok({
        "session_code": session.code,
        "slide_code": session.slide_code,
        "verdict": session.verdict,
        "evidence_total": len(evidence),
        "chain": chain,
        "orphan_evidence": orphan,
        "integrity_note": (
            "全部证据均被至少一个智能体步骤引用，证据链完整。"
            if not orphan else
            f"存在 {len(orphan)} 条未被引用的证据，说明有结论未挂到可追溯依据上。"
        ),
        "hard_constraint": "证据强制引用：每条 AI 结论必须绑定具体区域坐标或外部引用。",
    })


# ------------------------------------------------------------------ 能力判定
@router.post("/agents/capability-check", summary="能力边界校验（不落库，仅返回判定）")
def capability_check(db: DbSession, payload: dict = Body(...),
                     user: dict = Depends(require("agent:read"))) -> dict:
    from app.services.agent_service import _check_capability

    slide_id = payload.get("slide_id")
    slide = db.get(Slide, int(slide_id)) if slide_id else None
    if slide is None:
        raise HTTPException(status_code=404, detail="切片不存在")
    version = db.execute(select(ModelVersion).order_by(ModelVersion.id.desc()).limit(1)).scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="没有可用的模型版本")
    passed, reason, detail_payload = _check_capability(
        db, slide, str(payload.get("task_code") or "lymph_node_metastasis"), version
    )
    return ok({
        "passed": passed,
        "reason": reason,
        "checks": detail_payload["checks"],
        "declaration": detail_payload["declaration"],
        "conclusion": "在能力声明范围内，可正常分析。" if passed
                      else f"超出能力声明范围，将直接拒识：{reason}",
    })


# ------------------------------------------------------------------ 医生终审
@router.get("/agents/tickets", summary="医生终审工单列表")
def tickets(db: DbSession, user: dict = Depends(require("review:read")),
            page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
            status: str = Query(""), priority: str = Query(""), search: str = Query("")) -> dict:
    columns = {c.key: c for c in ReviewTicket.__table__.columns}
    filters = {}
    if status:
        filters[columns["status"]] = status
    if priority:
        filters[columns["priority"]] = priority
    items, total = list_query(
        db, ReviewTicket, page=page, page_size=page_size, search=search,
        search_fields=[columns[f] for f in ("code", "slide_code", "doctor_name", "ai_verdict")],
        filters=filters, order_by=columns["id"], descending=True,
    )
    return ok({
        "items": [serialize(t) for t in items],
        "meta": {"total": total, "page": page, "page_size": page_size,
                 "pages": (total + page_size - 1) // page_size},
    })


@router.post("/agents/tickets/{ticket_id}/decide", summary="提交医生终审结论")
def decide(ticket_id: int, db: DbSession, payload: dict = Body(...),
           user: dict = Depends(require("review:decide"))) -> dict:
    ticket = db.get(ReviewTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket.status == "decided":
        raise HTTPException(status_code=400, detail="该工单已完成终审，不可重复提交")

    agreement = str(payload.get("agreement") or "").strip()
    if agreement not in {"agree", "modify", "disagree"}:
        raise HTTPException(status_code=422, detail="agreement 必须为 agree / modify / disagree")
    verdict = str(payload.get("doctor_verdict") or "").strip()
    if not verdict:
        raise HTTPException(status_code=422, detail="必须填写医生结论")

    ticket.status = "decided"
    ticket.claimed_by = user.get("username", "")
    ticket.doctor_name = payload.get("doctor_name") or user.get("real_name") or user.get("username")
    ticket.doctor_verdict = verdict
    ticket.final_label = verdict
    ticket.agreement = agreement
    ticket.comments = str(payload.get("comments") or "")
    ticket.turnaround_min = int(payload.get("turnaround_min") or 0)
    ticket.decided_at = datetime.now().isoformat(timespec="seconds")

    session = db.get(AgentSession, ticket.session_id)
    if session:
        session.status = "reviewed"
    db.flush()

    audit(db, user, action="doctor_review_decision", resource_type="review_ticket",
          resource_id=ticket.id,
          summary=(f"医生终审工单 {ticket.code}：{agreement}（AI 倾向 {ticket.ai_verdict} → "
                   f"医生结论 {verdict}）"),
          payload={"agreement": agreement, "comments": ticket.comments,
                   "ai_verdict": ticket.ai_verdict, "doctor_verdict": verdict},
          risk_level="attention" if agreement == "disagree" else "normal")
    db.commit()
    return ok(ticket.to_dict())


@router.post("/agents/tickets/{ticket_id}/claim", summary="认领终审工单")
def claim(ticket_id: int, db: DbSession, user: dict = Depends(require("review:decide"))) -> dict:
    ticket = db.get(ReviewTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket.status == "decided":
        raise HTTPException(status_code=400, detail="该工单已完成终审")
    ticket.status = "claimed"
    ticket.claimed_by = user.get("username", "")
    db.flush()
    audit(db, user, action="claim_review_ticket", resource_type="review_ticket",
          resource_id=ticket.id, summary=f"认领终审工单 {ticket.code}")
    db.commit()
    return ok(ticket.to_dict())


# ------------------------------------------------------------------ 指标与说明
@router.get("/agents/metrics", summary="Agent 平台运行指标")
def metrics(db: DbSession, user: dict = Depends(require("agent:read"))) -> dict:
    return ok({
        **agent_metrics(db),
        "probe_budget": {
            "triage": TRIAGE_BUDGET, "navigation": NAVIGATION_BUDGET, "confirm": CONFIRM_BUDGET,
            "total": TRIAGE_BUDGET + NAVIGATION_BUDGET + CONFIRM_BUDGET,
            "benchmark": "业内分层探查方案平均探查约 47 个区域",
        },
        "confidence_threshold": settings.agent_confidence_threshold,
        "min_evidence": settings.agent_min_evidence,
        "reject_rules": [{"key": k, "desc": v} for k, v in REJECT_RULES],
    })


@router.get("/agents/architecture", summary="五智能体架构说明与描述生成规则")
def architecture(user: dict = Depends(require("agent:read"))) -> dict:
    return ok({
        "agents": [
            {"key": "orchestrator", "label": AGENT_ROLE_LABELS["orchestrator"],
             "responsibility": "制定分析策略、拆解任务、分配子智能体、整合证据、判定收敛与是否超能力范围",
             "reference": "对标 SlideSeek 的 Supervisor"},
            {"key": "triage", "label": AGENT_ROLE_LABELS["triage"],
             "responsibility": "低倍速全片快速初筛，判断是否含病变、是否需优先处理",
             "reference": "对标 PathFinder 的分诊智能体"},
            {"key": "navigation", "label": AGENT_ROLE_LABELS["navigation"],
             "responsibility": "模拟病理医生阅片轨迹，从低倍到高倍逐级定位高价值病灶区域",
             "reference": "对标 SlideSeek 的 Explorer（层次化探查）"},
            {"key": "description", "label": AGENT_ROLE_LABELS["description"],
             "responsibility": "由实测形态学统计量生成规范化病理描述，并检索相似病例作为参照",
             "reference": "对标 PathFinder 的描述智能体 + RAG"},
            {"key": "diagnosis", "label": AGENT_ROLE_LABELS["diagnosis"],
             "responsibility": "整合多轮证据输出鉴别诊断与分级结论，采用多轨迹投票",
             "reference": "对标 PathFinder 的诊断智能体"},
        ],
        "role_order": list(AGENT_ROLES),
        "magnification_ladder": ["5X", "10X", "20X", "40X"],
        "morphology_rules": [
            {"key": r["key"], "metric": r["metric"], "threshold": str(r["threshold"]),
             "strength": r["strength"], "claim_template": r["claim"]}
            for r in MORPHOLOGY_RULES
        ],
        "hard_constraints": [
            "证据强制引用：每条结论必须绑定具体区域坐标或外部引用，未达阈值的描述不生成。",
            "医生终审：AI 不给最终诊断，只给可追溯的判断依据；最终诊断只能由终审接口写入。",
        ],
        "reject_design": (
            "拒识是设计的一部分而非异常：能力越界、组织不足、置信度过低、证据不足、"
            "多轨迹一致率不足都会触发拒识并转人工，且原因必须落库可查。"
        ),
    })


@router.get("/agents/overview", summary="Agent 平台总览")
def overview(db: DbSession, user: dict = Depends(require("agent:read"))) -> dict:
    metrics_payload = agent_metrics(db)
    recent = list(db.execute(
        select(AgentSession).order_by(AgentSession.id.desc()).limit(8)
    ).scalars())
    pending = int(db.execute(
        select(func.count(ReviewTicket.id)).where(ReviewTicket.status == "pending")
    ).scalar() or 0)
    evidence_rows = db.execute(
        select(AgentEvidence.evidence_type, func.count(AgentEvidence.id))
        .group_by(AgentEvidence.evidence_type)
    ).all()
    return ok({
        **metrics_payload,
        "recent_sessions": [s.to_dict() for s in recent],
        "pending_tickets": pending,
        "evidence_by_type": {str(k): int(v) for k, v in evidence_rows},
        "summary": (
            "差异化不在「再做一版病理大模型」，而在「科室级 Agent」——"
            "模型权重可以开源，但贴合本院病理科真实工作流的编排与标签体系无法开源。"
        ),
    })
