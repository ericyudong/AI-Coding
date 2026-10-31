"""运营看板服务：团队编制、投入结构、收益路径、KPI 快照与总览。

设计文档依据：第九章「投入产出与团队配置」与第十一章「结论与立项建议」。

口径纪律（与设计文档保持一致）：
- 团队编制与人数字段是**计划编制**，不是实际在编。
- 成本只保存**相对占比区间**，不落任何本地倒推的绝对金额 —— 绝对金额必须由公司
  预算口径与市场价格单独测算，写死在系统里会误导立项决策。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent import AgentProbe, AgentSession, ReviewTicket
from app.models.asset import AssetExtension, DataAsset, Slide, SlideFeature, StorageStat
from app.models.compliance import AuditChainRecord, ConsentRecord, DataBoundaryCheck, EthicsRecord
from app.models.edge import EdgeNode, FederatedJob
from app.models.evaluation import EvalRun, MrMcComparison
from app.models.label import Annotation, LabelSchema
from app.models.modeling import ModelVersion, TrainingJob
from app.models.ops import CostStructure, KpiSnapshot, RevenuePath, StrategicDecision, TeamRole
from app.models.registry import RegistrationMilestone, RiskItem

# -------------------------------------------------------------- 团队编制（9.1）
TEAM_PLAN: list[dict[str, Any]] = [
    {"code": "TE-ALG-VLM", "role_name": "算法工程师（视觉/多模态）", "cluster": "algorithm",
     "stage": "P0", "headcount_min": 5, "headcount_max": 7, "headcount_suggested": 6,
     "is_mandatory": True, "onboard_month": 0,
     "skills": "自监督预训练、多任务学习、多模态对齐、病理图像处理",
     "responsibility": "编码器继续预训练与自研编码器孵化、图块级特征模型、切片级聚合模型"},
    {"code": "TE-ALG-AGENT", "role_name": "算法工程师（Agent / LLM 工程）", "cluster": "algorithm",
     "stage": "P1", "headcount_min": 2, "headcount_max": 3, "headcount_suggested": 2,
     "is_mandatory": False, "onboard_month": 4,
     "skills": "Agent 编排、RAG、工具调用、评测体系",
     "responsibility": "五智能体编排、证据强制引用、置信度校准与拒识、相似病例检索"},
    {"code": "TE-DATA", "role_name": "数据工程", "cluster": "data",
     "stage": "P0", "headcount_min": 3, "headcount_max": 4, "headcount_suggested": 3,
     "is_mandatory": True, "onboard_month": 0,
     "skills": "数据治理流水线、存储架构、特征库运维",
     "responsibility": "数据资产盘点、四层标签体系落地、特征预计算流水线、存储分层运维"},
    {"code": "TE-PLATFORM", "role_name": "平台/后端工程", "cluster": "engineering",
     "stage": "P0", "headcount_min": 3, "headcount_max": 4, "headcount_suggested": 3,
     "is_mandatory": True, "onboard_month": 0,
     "skills": "推理服务、PIS/HIS 集成、云边协同、前端交互",
     "responsibility": "推理服务与院内私有化部署、PIS 集成、云边协同与联邦、工作台前端"},
    {"code": "TE-CLINICAL", "role_name": "医学与临床（含合作医生）", "cluster": "clinical",
     "stage": "P0", "headcount_min": 2, "headcount_max": 3, "headcount_suggested": 3,
     "is_mandatory": True, "onboard_month": 0,
     "skills": "病理诊断、标签体系设计、标注质控、临床验证设计",
     "responsibility": "标签体系设计、标注 SOP 与仲裁机制、临床验证方案、终审判读",
     "note": "**首席医学官（或同等职能）必须在 P0 阶段到位**：病理 AI 的成败不取决于算法有多先进，"
             "而取决于标签体系是否符合临床真实逻辑，这必须由临床人员主导，不能由算法团队代劳。"},
    {"code": "TE-REG", "role_name": "注册与合规", "cluster": "compliance",
     "stage": "P0", "headcount_min": 1, "headcount_max": 2, "headcount_suggested": 1,
     "is_mandatory": True, "onboard_month": 0,
     "skills": "医疗器械注册、QMS、临床评价协调",
     "responsibility": "注册路径规划与分类界定、质量管理体系、伦理与知情同意台账、审计链维护"},
    {"code": "TE-PRODUCT", "role_name": "产品与项目", "cluster": "product",
     "stage": "P1", "headcount_min": 1, "headcount_max": 2, "headcount_suggested": 1,
     "is_mandatory": False, "onboard_month": 4,
     "skills": "需求管理、场景落地、客户对接",
     "responsibility": "科室需求转化、试点落地、医联体与基层客户对接"},
]

# -------------------------------------------------------------- 投入结构（9.2）
COST_PLAN: list[dict[str, Any]] = [
    {"code": "COST-HR", "category": "人力成本", "ratio_low": 0.45, "ratio_high": 0.55,
     "elasticity": "high", "note": "最强弹性项，可通过团队规模调节节奏"},
    {"code": "COST-GPU", "category": "算力成本", "ratio_low": 0.10, "ratio_high": 0.15,
     "elasticity": "high", "note": "建议以租用为主，压低前期资本开支"},
    {"code": "COST-INFRA", "category": "存储与基础设施", "ratio_low": 0.08, "ratio_high": 0.12,
     "elasticity": "medium", "note": "随数据规模线性增长"},
    {"code": "COST-ANNO", "category": "数据标注与专家费用", "ratio_low": 0.10, "ratio_high": 0.15,
     "elasticity": "medium", "note": "决定标签质量，不建议压缩"},
    {"code": "COST-REG", "category": "合规与注册", "ratio_low": 0.08, "ratio_high": 0.12,
     "elasticity": "low", "note": "含检验检测、体系认证、临床评价协调"},
    {"code": "COST-OTHER", "category": "其他（差旅、设备、软件许可）", "ratio_low": 0.05, "ratio_high": 0.08,
     "elasticity": "medium", "note": ""},
]

# -------------------------------------------------------------- 收益路径（9.3）
REVENUE_PLAN: list[dict[str, Any]] = [
    {"code": "RV-RESEARCH", "name": "科研合作与数据服务", "phase": "P0",
     "path_type": "research_cooperation", "prerequisite": "无需注册证，需伦理与数据合作框架",
     "status": "active", "note": "全程可开展；横向课题与联合研究，是 R5 现金流应对的第一条路径"},
    {"code": "RV-PILOT", "name": "院内 AI 辅助诊断系统（试点服务）", "phase": "P2",
     "path_type": "pilot_service", "prerequisite": "非注册依赖的科研合作与试点服务形态",
     "status": "planned", "note": "P2 阶段可产生首笔收入"},
    {"code": "RV-DEVICE", "name": "三类证产品（医疗器械软件销售）", "phase": "P3",
     "path_type": "device_sales", "prerequisite": "取得三类医疗器械注册证",
     "status": "planned", "note": "取证后规模放量"},
    {"code": "RV-UNION", "name": "区域医联体方案（云边协同订阅）", "phase": "P3",
     "path_type": "saas", "prerequisite": "取证后同步推进，面向县域医院",
     "status": "planned", "note": "云上安全存算、以租代建、开箱即用；首年投入可下降 90%，"
                                 "五年总成本降低 40% 以上，PIS 集成周期约一周"},
    {"code": "RV-ASSET", "name": "技术资产（自研编码器与专利、数据资产）", "phase": "P2",
     "path_type": "data_license", "prerequisite": "自研编码器完成替换（M4）",
     "status": "planned", "note": "长期估值支撑，不直接产生当期收入"},
]


def ensure_ops_plan(db: Session) -> None:
    """幂等地建立团队、成本、收益与立项决策记录。"""
    if not db.execute(select(func.count(TeamRole.id))).scalar():
        total_min = sum(t["headcount_min"] for t in TEAM_PLAN)
        total_max = sum(t["headcount_max"] for t in TEAM_PLAN)
        assert total_min == 17 and total_max == 25, f"团队编制合计应为 17—25，实际 {total_min}—{total_max}"
        for order, item in enumerate(TEAM_PLAN):
            db.add(TeamRole(**item, sort_order=order))
        db.flush()

    if not db.execute(select(func.count(CostStructure.id))).scalar():
        for order, item in enumerate(COST_PLAN):
            db.add(CostStructure(**item, sort_order=order))
        db.flush()

    if not db.execute(select(func.count(RevenuePath.id))).scalar():
        for item in REVENUE_PLAN:
            db.add(RevenuePath(**item))
        db.flush()

    if not db.execute(select(func.count(StrategicDecision.id))).scalar():
        db.add(StrategicDecision(
            code="SD-APPROVE",
            decision_type="project_approval",
            title="建议立项：按双轨制推进蓝天健康病理垂类模型与智慧医疗 Agent",
            content=(
                "商用主线求稳（可注册、可验证、可回款），探索线求进（Agent 化、多模态、差异化）。"
                "首期投入聚焦 2—3 个高价值单病种打样，18 个月形成完整能力，30 个月完成首个三类证申报。"
            ),
            rationale=(
                "① 政策、支付与准入三通道已同时打开；"
                "② 存量数据的真实价值不在「多」而在「有医生标注」；"
                "③ 万张级数据不足以从零训练基础模型，但足以训练高价值垂直模型；"
                "④ 合规路径决定技术选型，必须先定路线再写代码；"
                "⑤ 差异化不在「再做一版病理大模型」，而在「科室级 Agent」。"
            ),
            action_items_json=json.dumps([
                {"title": "组建数据资产盘点小组", "description": "由临床医学负责人牵头，输出《数据资产盘点与标签体系说明书》",
                 "owner": "首席医学官", "deadline": "立项后 1 个月内", "status": "pending"},
                {"title": "确认双源并行策略与预算", "description": "在立项决议中锁定许可风险应对方案，单独列支自研编码器替换成本与人力",
                 "owner": "算法负责人 + 财务", "deadline": "立项后 1 个月内", "status": "pending"},
                {"title": "搭建评测基座", "description": "用可商用开源权重跑通「切片→特征→聚合→预测→评测」全链路，以最小成本验证工程能力",
                 "owner": "算法负责人", "deadline": "立项后 3 个月内", "status": "pending"},
            ], ensure_ascii=False),
            owner_name="项目发起人",
            status="proposed",
            sort_order=0,
        ))
        db.add(StrategicDecision(
            code="SD-DUALTRACK",
            decision_type="dual_track",
            title="确认双轨制与许可风险处置原则",
            content=(
                "商用主线仅使用可商用许可（Apache-2.0 及自有知识产权）的编码器；"
                "非商用权重（CC BY-NC / CC BY-NC-ND / 研究用途）仅在 research 环境用于科研与探索线验证，"
                "并由系统级许可门禁强制隔离。"
            ),
            rationale="若使用非商用许可权重直接做商用产品，将在注册环节面临根本性返工（风险 R2）。",
            action_items_json=json.dumps([
                {"title": "启用许可门禁", "description": "product 环境下调用非商用编码器直接拦截",
                 "owner": "平台负责人", "deadline": "立即", "status": "done"},
                {"title": "自研编码器替换计划纳入 M4 里程碑", "description": "第 16 个月内完成替换并使许可风险清零",
                 "owner": "编码器组负责人", "deadline": "第 16 月", "status": "pending"},
            ], ensure_ascii=False),
            owner_name="技术负责人",
            status="proposed",
            sort_order=1,
        ))
        db.flush()


# ------------------------------------------------------------------ KPI
def compute_kpi(db: Session) -> dict[str, Any]:
    def count(model, *conditions) -> int:
        stmt = select(func.count(model.id))
        if conditions:
            stmt = stmt.where(*conditions)
        return int(db.execute(stmt).scalar() or 0)

    slides = count(Slide)
    assets = count(DataAsset)
    annotated = int(db.execute(
        select(func.count(func.distinct(Annotation.slide_code)))
    ).scalar() or 0)
    region_ann = count(Annotation)
    features = count(SlideFeature)
    sessions = count(AgentSession)
    rejected = count(AgentSession, AgentSession.rejected.is_(True))
    decided = count(ReviewTicket, ReviewTicket.status == "decided")
    agree = count(ReviewTicket, ReviewTicket.agreement == "agree")
    milestones_done = count(RegistrationMilestone, RegistrationMilestone.status == "done")
    milestones_total = count(RegistrationMilestone)
    audits = count(AuditChainRecord)
    nodes_online = count(EdgeNode, EdgeNode.status == "online")
    latest_eval = db.execute(select(EvalRun).order_by(EvalRun.id.desc()).limit(1)).scalar_one_or_none()
    latest_mrmc = db.execute(select(MrMcComparison).order_by(MrMcComparison.id.desc()).limit(1)).scalar_one_or_none()
    headcount = int(db.execute(select(func.sum(TeamRole.headcount_suggested))).scalar() or 0)
    probes = float(db.execute(select(func.avg(AgentSession.probed_region_count))).scalar() or 0.0)

    generalization = json.loads(latest_eval.generalization_json or "{}") if latest_eval else {}
    return {
        "asset_count": assets,
        "slide_count": slides,
        "annotated_slide_count": annotated,
        "annotation_count": region_ann,
        "feature_ready_count": features,
        "feature_coverage": round(features / slides, 6) if slides else 0.0,
        "model_auroc": latest_eval.auroc if latest_eval else 0.0,
        "external_auroc": float(generalization.get("out_domain_auroc") or 0.0),
        "generalization_gap": generalization.get("gap"),
        "generalization_severity": generalization.get("severity", ""),
        "mrmc_conclusion": latest_mrmc.conclusion if latest_mrmc else "",
        "agent_session_count": sessions,
        "agent_reject_rate": round(rejected / sessions, 6) if sessions else 0.0,
        "agent_avg_probed_regions": round(probes, 3),
        "review_agreement_rate": round(agree / decided, 6) if decided else 0.0,
        "review_decided": decided,
        "milestone_done": milestones_done,
        "milestone_total": milestones_total,
        "audit_record_count": audits,
        "edge_online_count": nodes_online,
        "headcount_now": 0,
        "headcount_target": headcount,
    }


def snapshot_kpi(db: Session, snapshot_date: str = "") -> KpiSnapshot:
    data = compute_kpi(db)
    snapshot_date = snapshot_date or datetime.now().date().isoformat()
    existing = db.execute(
        select(KpiSnapshot).where(KpiSnapshot.snapshot_date == snapshot_date)
    ).scalar_one_or_none()
    payload = {
        **{k: v for k, v in data.items() if k in KpiSnapshot.column_names()},
        "snapshot_date": snapshot_date,
    }
    payload.pop("id", None)
    payload.pop("created_at", None)
    payload.pop("updated_at", None)
    if existing:
        existing.update_from(payload)
        record = existing
    else:
        record = KpiSnapshot(**payload)
        db.add(record)
    db.flush()
    return record


# ------------------------------------------------------------------ 看板
def dashboard(db: Session) -> dict[str, Any]:
    """立项决策看板：把「决策者真正关心的 8 个数字」放在最上层。"""
    from app.services.agent_service import agent_metrics
    from app.services.compliance_service import registration_readiness
    from app.services.encoder_service import encoder_service
    from app.services.edge_service import edge_overview
    from app.services.label_service import coverage_report, sop_status
    from app.services.pipeline_service import pipeline_overview
    from app.services.registry_service import milestone_overview, risk_board

    kpi = compute_kpi(db)
    readiness = registration_readiness(db)
    pipeline = pipeline_overview(db)
    agent = agent_metrics(db)
    risks = risk_board(db)
    milestones = milestone_overview(db)
    coverage = coverage_report(db)
    license_audit = encoder_service.license_audit()

    latest_version = db.execute(
        select(ModelVersion).order_by(ModelVersion.id.desc()).limit(1)
    ).scalar_one_or_none()
    latest_job = db.execute(
        select(TrainingJob).order_by(TrainingJob.id.desc()).limit(1)
    ).scalar_one_or_none()
    storage = [s.to_dict() for s in db.execute(
        select(StorageStat).order_by(StorageStat.stat_date.desc()).limit(6)
    ).scalars()]
    extensions = [e.to_dict() for e in db.execute(select(AssetExtension)).scalars()]
    ethics = [e.to_dict() for e in db.execute(select(EthicsRecord)).scalars()]
    consents = [c.to_dict() for c in db.execute(select(ConsentRecord)).scalars()]
    boundary = db.execute(
        select(DataBoundaryCheck).order_by(DataBoundaryCheck.id.desc()).limit(1)
    ).scalar_one_or_none()
    campaigns = [d.to_dict() for d in db.execute(
        select(StrategicDecision).order_by(StrategicDecision.sort_order.asc())
    ).scalars()]

    headline = [
        {"key": "stage", "label": "项目阶段", "value": latest_version.semver if latest_version else "待启动",
         "sub": f"里程碑 {kpi['milestone_done']}/{kpi['milestone_total']} 完成", "tone": "navy"},
        {"key": "data", "label": "已标注切片", "value": str(kpi["annotated_slide_count"]),
         "sub": f"标注记录 {kpi['annotation_count']} 条，标签覆盖率 "
                f"{round(coverage['by_layer']['slide']['coverage_rate'] * 100, 1)}%", "tone": "navy"},
        {"key": "auroc", "label": "内部验证 AUROC", "value": f"{kpi['model_auroc']:.3f}",
         "sub": "评测基座产出的最新版本指标", "tone": "blue"},
        {"key": "agent", "label": "Agent 会话", "value": str(kpi["agent_session_count"]),
         "sub": f"平均探查 {kpi['agent_avg_probed_regions']:.0f} 个区域，拒识率 "
                f"{round(kpi['agent_reject_rate'] * 100, 1)}%", "tone": "blue"},
        {"key": "review", "label": "医生终审一致率", "value": f"{kpi['review_agreement_rate']:.1%}",
         "sub": f"已终审 {kpi['review_decided']} 例", "tone": "cyan"},
        {"key": "license", "label": "可商用编码器", "value": f"{license_audit['allowed_count']}/{license_audit['total']}",
         "sub": f"自研编码器 {len(license_audit['self_developed_encoders'])} 个（许可风险终局方案）",
         "tone": "cyan"},
        {"key": "risk", "label": "前置风险", "value": str(risks["frontloaded_count"]),
         "sub": "必须在 P0 阶段就有动作", "tone": "warn"},
        {"key": "readiness", "label": "注册就绪度", "value": f"{readiness['readiness_score']:.0%}",
         "sub": f"{readiness['passed_count']}/{readiness['total_count']} 项通过", "tone": "warn"},
    ]

    return {
        "headline": headline,
        "kpi": kpi,
        "readiness": readiness,
        "pipeline": pipeline,
        "agent": agent,
        "risk": risks,
        "milestones": milestones,
        "coverage": coverage,
        "sop": sop_status(db),
        "license_audit": license_audit,
        "edge": edge_overview(db),
        "storage": storage,
        "asset_extensions": extensions,
        "ethics": ethics,
        "consents": consents,
        "data_boundary": boundary.to_dict() if boundary else None,
        "strategic_decisions": campaigns,
        "latest_training_job": latest_job.to_dict() if latest_job else None,
    }


def team_plan(db: Session) -> dict[str, Any]:
    roles = list(db.execute(select(TeamRole).order_by(TeamRole.sort_order.asc())).scalars())
    by_cluster: dict[str, Any] = {}
    for role in roles:
        bucket = by_cluster.setdefault(role.cluster, {"cluster": role.cluster, "min": 0, "max": 0,
                                                      "suggested": 0, "roles": []})
        bucket["min"] += role.headcount_min
        bucket["max"] += role.headcount_max
        bucket["suggested"] += role.headcount_suggested
        bucket["roles"].append(role.to_dict())
    mandatory = [r for r in roles if r.is_mandatory]
    return {
        "roles": [r.to_dict() for r in roles],
        "by_cluster": by_cluster,
        "cluster_labels": {
            "clinical": "医学与临床", "algorithm": "算法", "engineering": "平台/后端工程",
            "compliance": "注册与合规", "data": "数据工程", "product": "产品与项目",
        },
        "total_min": sum(r.headcount_min for r in roles),
        "total_max": sum(r.headcount_max for r in roles),
        "total_suggested": sum(r.headcount_suggested for r in roles),
        "mandatory_in_p0": [r.role_name for r in mandatory if r.stage == "P0"],
        "key_message": (
            "首期建议以 18 人左右起步，P2 阶段补齐。"
            "首席医学官（或同等职能）必须在 P0 阶段到位 —— "
            "病理 AI 的成败不取决于算法有多先进，而取决于标签体系是否符合临床真实逻辑。"
        ),
    }


def cost_structure(db: Session) -> dict[str, Any]:
    items = list(db.execute(select(CostStructure).order_by(CostStructure.sort_order.asc())).scalars())
    total_high = sum(i.ratio_high for i in items)
    return {
        "items": [i.to_dict() for i in items],
        "ratio_high_sum": round(total_high, 4),
        "basis_note": (
            "以上为成本投入的**相对结构建议**，具体金额需结合公司预算口径与市场价格另行测算。"
            "系统刻意不保存任何绝对金额，避免本地倒推的数字被当成预算口径。"
        ),
        "elasticity_note": "人力成本是最强弹性项，可通过团队规模调节节奏；数据标注与专家费用决定标签质量，不建议压缩。",
    }


def revenue_paths(db: Session) -> dict[str, Any]:
    items = list(db.execute(select(RevenuePath)).scalars())
    return {
        "items": [i.to_dict() for i in items],
        "first_revenue_phase": "P2",
        "note": "P2 阶段可通过非注册依赖的科研合作与试点服务产生首笔收入，缓解注册周期带来的现金流压力。",
        "grassroots_judgement": (
            "业内已证实的模式是「云上安全存算、以租代建、开箱即用」：相比传统院内集中自建，"
            "首年投入可下降 90%、五年总成本降低 40% 以上，且 PIS 系统集成周期约一周。"
            "这是一个价格敏感但容量巨大的市场，非常契合本方案云边协同的架构设计。"
        ),
    }


def strategic_decisions(db: Session) -> list[dict[str, Any]]:
    rows = list(db.execute(
        select(StrategicDecision).order_by(StrategicDecision.sort_order.asc())
    ).scalars())
    result = []
    for row in rows:
        payload = row.to_dict()
        payload["action_items"] = json.loads(row.action_items_json or "[]")
        result.append(payload)
    return result
