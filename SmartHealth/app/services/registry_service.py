"""注册申报、路线图、里程碑与风险管理的业务逻辑。

设计文档依据：
- 第七章「合规与注册路径」（注册四阶段与行业典型周期）
- 第八章「实施路线图与里程碑」（P0—P3 与 M1—M8）
- 第十章「风险与应对」（R1—R10，其中 R1/R2/R3 为必须在 P0 就有动作的前置风险）

本模块的一个刻意设计：`RegistrationStage` 同时保存**行业典型周期**与**项目计划窗口**。
若计划窗口短于行业下限，会自动标注为进度风险（需要依赖创新医疗器械特别审查加速通道），
而不是把两个数字糊在一起 —— 立项决策最怕的就是把激进排期当成常规排期。
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.registry import (
    ClinicalTrialSite,
    GuidelineDoc,
    RegistrationMilestone,
    RegistrationPath,
    RegistrationStage,
    RiskItem,
)

PROJECT_TOTAL_MONTHS = 30

# 注册四阶段：行业典型周期取自设计文档第七章
REGISTRATION_STAGE_PLAN: list[dict[str, Any]] = [
    {
        "code": "classification", "name": "分类界定与前置沟通", "sort_order": 1,
        "duration_months_min": 2, "duration_months_max": 3,
        "start_month": 0, "end_month": 4, "phase": "P0",
        "key_actions": "提交分类界定申请；与审评机构开展前置沟通；确认辅助决策类软件按第三类管理",
        "deliverables": "分类界定结论；前置沟通记录；注册策略说明书",
    },
    {
        "code": "product_freeze", "name": "产品定型与检验", "sort_order": 2,
        "duration_months_min": 4, "duration_months_max": 6,
        "start_month": 4, "end_month": 10, "phase": "P1",
        "key_actions": "软件定版；建立质量管理体系；第三方检测；网络安全测评；确认可用性与临床评价路径",
        "deliverables": "软件版本定版记录；第三方检测报告；网络安全测评报告；QMS 文件",
    },
    {
        "code": "clinical_trial", "name": "临床试验", "sort_order": 3,
        "duration_months_min": 10, "duration_months_max": 16,
        "start_month": 10, "end_month": 20, "phase": "P2",
        "key_actions": "伦理审批；多中心入组；以 MRMC 方式设计对照；数据锁定与统计报告",
        "deliverables": "伦理批件；临床试验方案与报告；MRMC 统计结果",
    },
    {
        "code": "submission", "name": "注册申报与审评", "sort_order": 4,
        "duration_months_min": 8, "duration_months_max": 12,
        "start_month": 20, "end_month": 30, "phase": "P3",
        "key_actions": "提交注册资料；发补回复；生产质量管理体系核查；取得注册证",
        "deliverables": "注册申报资料；发补回复记录；体系核查结论；医疗器械注册证",
    },
]

# 八个里程碑（M1—M8），与设计文档 8.2 关键里程碑汇总逐字对应
MILESTONE_PLAN: list[dict[str, Any]] = [
    {"code": "M1", "phase": "P0", "phase_name": "奠基期", "title": "数据资产与标签体系就绪",
     "target_month": 4, "acceptance_criteria": "盘点报告发布，标注 SOP 通过医学审核",
     "deliverable": "《数据资产盘点与标签体系说明书》+ 已审核 SOP"},
    {"code": "M2", "phase": "P0", "phase_name": "奠基期", "title": "评测基座与基线跑通",
     "target_month": 4, "acceptance_criteria": "端到端流程可复现，基线指标留档",
     "deliverable": "评测基座 + 基线指标留档报告"},
    {"code": "M3", "phase": "P1", "phase_name": "单点突破", "title": "首个单病种达标",
     "target_month": 10, "acceptance_criteria": "内部验证集 AUROC 达预设阈值，外部验证通过",
     "deliverable": "首个单病种模型版本 + 内外验证报告"},
    {"code": "M4", "phase": "P2", "phase_name": "模型成体", "title": "自研编码器替换完成",
     "target_month": 16, "acceptance_criteria": "性能不劣于参照权重，许可风险清零",
     "deliverable": "自研编码器版本 + 性能对照报告"},
    {"code": "M5", "phase": "P2", "phase_name": "模型成体", "title": "Agent v1 上线",
     "target_month": 18, "acceptance_criteria": "试点科室日均使用，医生满意度达标",
     "deliverable": "Agent v1 + 试点运行报告"},
    {"code": "M6", "phase": "P3", "phase_name": "注册与规模化", "title": "临床试验启动",
     "target_month": 20, "acceptance_criteria": "伦理审批通过，完成首例入组",
     "deliverable": "伦理批件 + 首例入组记录"},
    {"code": "M7", "phase": "P3", "phase_name": "注册与规模化", "title": "三类证获批",
     "target_month": 30, "acceptance_criteria": "取得医疗器械注册证",
     "deliverable": "医疗器械注册证"},
    {"code": "M8", "phase": "P3", "phase_name": "注册与规模化", "title": "基层产品首交付",
     "target_month": 30, "acceptance_criteria": "完成首批医联体部署",
     "deliverable": "基层交付验收单"},
]

# 风险台账 R1—R10，与设计文档第十章逐条对应
RISK_PLAN: list[dict[str, Any]] = [
    {
        "code": "R1", "title": "数据规模不足", "category": "数据", "layer": "data",
        "description": "万张级切片在部分病种上样本不足，难以支撑独立任务。",
        "impact": "模型泛化受限，部分病种无法独立支撑任务。",
        "response": "首期聚焦 2—3 个样本充足的病种；同步执行院内增量 + 外部合作 + 公开数据补充三条扩展路径。",
        "likelihood": 4, "severity": 3, "is_frontloaded": True,
        "p0_action": "完成数据资产盘点，锁定首批 2—3 个单病种；启动三条扩展路径",
        "budget_note": "不需要单独列支，但需明确数据合作方的商务与伦理成本",
    },
    {
        "code": "R2", "title": "开源权重许可风险", "category": "合规", "layer": "compliance",
        "description": "业界最强开源病理权重多为非商用许可（CC BY-NC-ND / CC BY-NC / 研究用途）。",
        "impact": "商用产品面临法律障碍，注册申报受阻，可能在注册阶段造成根本性返工。",
        "response": "双源并行：短期用可商用权重，6—18 个月内完成自研编码器替换，科研与产品环境严格隔离。",
        "likelihood": 3, "severity": 5, "is_frontloaded": True,
        "p0_action": "在立项决议中即明确双源并行策略，并单独列支自研编码器替换成本",
        "budget_note": "**必须单独列支**：自研编码器自监督预训练与替换验证的成本与人力",
    },
    {
        "code": "R3", "title": "跨中心泛化衰减（中心特异性）", "category": "算法", "layer": "technical",
        "description": "不同医院染色机与扫描仪差异导致特征分布漂移。",
        "impact": "院内表现优异、院外性能显著下降。",
        "response": "项目中期即启动多中心验证；染色归一化 + 中心不变性训练；联邦式增量微调。",
        "likelihood": 4, "severity": 4, "is_frontloaded": True,
        "p0_action": "评测基座建立时即按中心分组统计指标，避免后期才发现衰减",
        "budget_note": "多中心验证的差旅与数据合规成本",
    },
    {
        "code": "R4", "title": "临床信任不足", "category": "临床", "layer": "clinical",
        "description": "医生对 AI 结论缺乏信任，或担心承担额外责任。",
        "impact": "医生不愿使用，产品形同虚设。",
        "response": "可解释性四件套（空间/语义/量化/拒识）；医生终审设计；从辅助性最强的场景切入。",
        "likelihood": 3, "severity": 4, "is_frontloaded": False,
        "p0_action": "在标签体系设计中即纳入可解释性字段需求",
        "budget_note": "",
    },
    {
        "code": "R5", "title": "注册周期长于预期", "category": "商业", "layer": "commercial",
        "description": "临床试验入组慢、发补轮次多，导致取证时间后移。",
        "impact": "现金流压力，团队士气受影响。",
        "response": "分阶段收入设计（科研合作、试点服务先行）；申请创新医疗器械特别审查加速通道；P0 阶段即完成分类界定确认。",
        "likelihood": 3, "severity": 4, "is_frontloaded": False,
        "p0_action": "P0 阶段完成分类界定确认与前置沟通",
        "budget_note": "加速通道申报与沟通成本",
    },
    {
        "code": "R6", "title": "幻觉与越界推理", "category": "安全", "layer": "technical",
        "description": "多模态描述智能体可能生成无依据的结论。",
        "impact": "临床安全风险，合规隐患。",
        "response": "输入能力声明 + 证据强制引用 + 置信度校准 + 拒识 + 人在环路五重防控。",
        "likelihood": 3, "severity": 5, "is_frontloaded": False,
        "p0_action": "在 Agent 编排设计中固化五重防控，禁止无证据结论输出",
        "budget_note": "",
    },
    {
        "code": "R7", "title": "竞争加剧（已有开源先例）", "category": "商业", "layer": "commercial",
        "description": "国内已有临床级病理大模型开源，模型复现不再构成壁垒。",
        "impact": "差异化被压缩，议价能力下降。",
        "response": "差异化落在标签深度、Agent 编排体验与场景下沉能力，而非模型参数本身。",
        "likelihood": 4, "severity": 3, "is_frontloaded": False,
        "p0_action": "明确「不复现模型」的战略定位，把资源投向标签体系与 Agent",
        "budget_note": "",
    },
    {
        "code": "R8", "title": "算力与成本超支", "category": "成本", "layer": "commercial",
        "description": "训练与推理算力开销超出预算。",
        "impact": "项目经济性恶化。",
        "response": "特征预计算 + 低倍优先探查策略降低单例算力开销；训练以租用为主。",
        "likelihood": 3, "severity": 3, "is_frontloaded": False,
        "p0_action": "建立算力台账与单例成本核算口径",
        "budget_note": "算力以租用为主，资本开支压后到产品验证通过之后",
    },
    {
        "code": "R9", "title": "复合型人才短缺", "category": "团队", "layer": "team",
        "description": "既懂病理又懂算法的复合型人才稀缺。",
        "impact": "进度延误。",
        "response": "医工交叉培养机制；核心岗位外部引进；与临床科室建立联合培养。",
        "likelihood": 4, "severity": 3, "is_frontloaded": False,
        "p0_action": "首席医学官（或同等职能）必须在 P0 阶段到位",
        "budget_note": "关键岗位的引进成本",
    },
    {
        "code": "R10", "title": "数据合规瑕疵", "category": "合规", "layer": "compliance",
        "description": "伦理批件范围不足、知情同意缺失或标注资质记录不全。",
        "impact": "注册被否或产品下架。",
        "response": "伦理与知情同意台账化；标注 SOP 与仲裁记录全程留痕；数据不出域架构。",
        "likelihood": 2, "severity": 5, "is_frontloaded": False,
        "p0_action": "建立伦理/知情同意/标注资质三类台账并纳入审计链",
        "budget_note": "伦理与法务审核成本",
    },
]

# 法规依据库，与设计文档附录 3 主要参考依据逐条对应
GUIDELINE_PLAN: list[dict[str, Any]] = [
    {
        "code": "GD-01", "title": "关于促进和规范「人工智能+医疗卫生」应用发展的实施意见",
        "publisher": "国家卫生健康委等五部门", "doc_no": "国卫办规划发〔2025〕30 号",
        "publish_date": "2025-10", "category": "policy",
        "key_points": "到 2027 年形成一批临床专病专科垂直大模型和智能体应用；到 2030 年二级以上医院普遍开展医学影像智能辅助诊断；明确「赋能而不替代」的定位。",
        "applies_to": "产品定位、预期用途表述、Agent 的辅助定位设计",
    },
    {
        "code": "GD-02", "title": "关于优化全生命周期监管支持高端医疗器械创新发展有关举措的公告",
        "publisher": "国家药品监督管理局", "doc_no": "2025 年第 63 号",
        "publish_date": "2025-06", "category": "nmpa",
        "key_points": "研究制定「多病种、大模型人工智能」领域相关技术指导原则或审评要点；简化核心算法不变而性能优化的变更注册要求。",
        "applies_to": "多病种扩展的注册策略；模型迭代的变更注册路径",
    },
    {
        "code": "GD-03", "title": "人工智能医疗器械注册审查指导原则（2022 修订版）",
        "publisher": "国家药品监督管理局器审中心", "doc_no": "2022 年第 8 号",
        "publish_date": "2022-03", "category": "guide",
        "key_points": "辅助决策类 AI 医用软件按第三类医疗器械管理；需境内多中心临床试验；关注数据集构建、算法可解释性、网络安全与更新控制。",
        "applies_to": "注册路径与技术选型的核心依据；审评三道关口（数据可溯源/算法可解释/临床可验证）",
    },
    {
        "code": "GD-04", "title": "病理类医疗服务价格项目立项指南（试行）",
        "publisher": "国家医疗保障局", "doc_no": "", "publish_date": "2025-12", "category": "payment",
        "key_points": "明确将「人工智能辅助诊断」列为病理诊断的扩展项并纳入价格构成。",
        "applies_to": "商业闭环的支付前提；院内收费路径设计",
    },
    {
        "code": "GD-05", "title": "医疗器械分类目录", "publisher": "国家药品监督管理局", "doc_no": "",
        "publish_date": "", "category": "nmpa",
        "key_points": "辅助决策类软件归入第三类医疗器械管理。",
        "applies_to": "分类界定申请的直接依据",
    },
    {
        "code": "GD-06", "title": "创新医疗器械特别审查程序",
        "publisher": "国家药品监督管理局", "doc_no": "", "publish_date": "", "category": "nmpa",
        "key_points": "对国内首创、国际领先、具有显著临床应用价值的产品，可申请特别审查加速。",
        "applies_to": "R5 应对措施；30 个月排期的可行性前提",
    },
]


# ------------------------------------------------------------------ 初始化
def ensure_registration_plan(db: Session, product_name: str = "蓝天健康病理辅助诊断软件") -> RegistrationPath:
    """幂等地建立注册路径、阶段、里程碑、风险与法规依据。"""
    path = db.execute(select(RegistrationPath).limit(1)).scalar_one_or_none()
    if path is None:
        path = RegistrationPath(
            code="RP-SH-01",
            product_name=product_name,
            product_type="AI-SaMD",
            device_class="III",
            classification_code="21-04 决策支持软件",
            classification_conclusion="待分类界定申请确认（P0 阶段完成）",
            intended_use=(
                "本产品用于数字病理全切片图像（H&E 染色）的辅助分析，"
                "对目标病种进行病灶区域的自动识别与定位，输出辅助提示与可追溯的判断依据，"
                "供病理医师阅片时参考。本产品不提供最终诊断结论，最终诊断由病理医师作出。"
            ),
            target_population="拟接受病理组织学检查的患者（含术中与常规病理）",
            indications="首批适应症聚焦淋巴结转移检测与消化道早癌识别两个单病种。",
            contraindications="不适用于冰冻切片、细胞学涂片与特殊染色（如免疫组化）切片。",
            usage_scenario="院内病理科，由具备执业资质的病理医师或技师操作",
            path_type="innovation",
            innovation_qualified=False,
            change_registration_available=True,
            status="planning",
            target_approval_month=PROJECT_TOTAL_MONTHS,
            expected_duration_months="24—36（本项目排期 30 个月，依赖创新特别审查加速通道）",
            owner_name="注册与合规负责人",
            note=(
                "分类界定结论必须在 P0 阶段确认 —— 这是 R5「注册周期长于预期」的首要应对动作。"
                "本产品的注册申报依赖「核心算法不变而性能优化」的变更注册优化通道以支持后续迭代。"
            ),
        )
        db.add(path)
        db.flush()

    if not db.execute(select(func.count(RegistrationStage.id))).scalar():
        for item in REGISTRATION_STAGE_PLAN:
            planned = item["end_month"] - item["start_month"]
            shortfall = planned < item["duration_months_min"]
            note = ""
            if shortfall:
                note = (
                    f"计划周期 {planned} 个月短于行业典型下限 {item['duration_months_min']} 个月，"
                    "属于进度风险：需要依赖创新医疗器械特别审查加速通道与并行作业，"
                    "建议在里程碑复盘中持续跟踪。"
                )
            db.add(RegistrationStage(
                path_id=path.id,
                code=item["code"],
                name=item["name"],
                sort_order=item["sort_order"],
                duration_months_min=item["duration_months_min"],
                duration_months_max=item["duration_months_max"],
                start_month=item["start_month"],
                end_month=item["end_month"],
                key_actions=item["key_actions"],
                deliverables=item["deliverables"],
                owner_name="注册与合规负责人",
                note=note,
            ))
        db.flush()

    if not db.execute(select(func.count(RegistrationMilestone.id))).scalar():
        base_date = date(2026, 11, 1)
        for item in MILESTONE_PLAN:
            month = item["target_month"]
            target = base_date + _months_delta(month)
            db.add(RegistrationMilestone(
                path_id=path.id,
                code=item["code"],
                phase=item["phase"],
                phase_name=item["phase_name"],
                title=item["title"],
                target_month=month,
                target_date=target.isoformat(),
                acceptance_criteria=item["acceptance_criteria"],
                deliverable=item["deliverable"],
                owner_name=_milestone_owner(item["code"]),
                evidence_refs_json="[]",
            ))
        db.flush()

    if not db.execute(select(func.count(RiskItem.id))).scalar():
        for item in RISK_PLAN:
            db.add(RiskItem(
                code=item["code"],
                title=item["title"],
                category=item["category"],
                layer=item["layer"],
                description=item["description"],
                impact=item["impact"],
                response=item["response"],
                likelihood=item["likelihood"],
                severity=item["severity"],
                risk_score=item["likelihood"] * item["severity"],
                is_frontloaded=item["is_frontloaded"],
                p0_action=item["p0_action"],
                owner_name="项目经理",
                status="mitigating" if item["is_frontloaded"] else "open",
                budget_note=item["budget_note"],
            ))
        db.flush()

    if not db.execute(select(func.count(GuidelineDoc.id))).scalar():
        for item in GUIDELINE_PLAN:
            db.add(GuidelineDoc(**item))
        db.flush()

    return path


def _months_delta(months: int) -> Any:
    from datetime import timedelta

    return timedelta(days=int(months * 30.44))


def _milestone_owner(code: str) -> str:
    return {
        "M1": "首席医学官", "M2": "算法负责人", "M3": "算法负责人",
        "M4": "编码器组负责人", "M5": "Agent 组负责人",
        "M6": "临床运营负责人", "M7": "注册与合规负责人", "M8": "业务发展负责人",
    }.get(code, "项目经理")


# ------------------------------------------------------------------ 只读视图
def registration_timeline(db: Session) -> dict[str, Any]:
    """注册时间轴（甘特数据）：阶段窗口 + 里程碑 + 进度。"""
    path = db.execute(select(RegistrationPath).limit(1)).scalar_one_or_none()
    stages = list(db.execute(
        select(RegistrationStage).order_by(RegistrationStage.sort_order.asc())
    ).scalars())
    milestones = list(db.execute(
        select(RegistrationMilestone).order_by(RegistrationMilestone.target_month.asc(),
                                               RegistrationMilestone.code.asc())
    ).scalars())

    stage_payload: list[dict[str, Any]] = []
    for stage in stages:
        planned = stage.end_month - stage.start_month
        stage_payload.append({
            **stage.to_dict(),
            "planned_months": planned,
            "industry_typical": f"{stage.duration_months_min}—{stage.duration_months_max} 个月",
            "compressed": planned < stage.duration_months_min,
        })

    done = sum(1 for m in milestones if m.status == "done")
    at_risk = sum(1 for m in milestones if m.status == "at_risk")
    overall = round(done / len(milestones), 6) if milestones else 0.0
    return {
        "path": path.to_dict() if path else None,
        "total_months": PROJECT_TOTAL_MONTHS,
        "stages": stage_payload,
        "milestones": [m.to_dict() for m in milestones],
        "phase_bands": _phase_bands(),
        "milestone_done": done,
        "milestone_total": len(milestones),
        "milestone_at_risk": at_risk,
        "overall_progress": overall,
        "compliance_note": (
            "注册四阶段同时保存「行业典型周期」与「项目计划窗口」。"
            "若计划窗口短于行业下限，系统会标记为进度风险并要求依赖加速通道 —— "
            "避免把激进排期当作常规排期来立项。"
        ),
    }


def _phase_bands() -> list[dict[str, Any]]:
    return [
        {"key": "P0", "name": "奠基期", "start_month": 0, "end_month": 4,
         "goal": "把数据变成资产"},
        {"key": "P1", "name": "单点突破", "start_month": 4, "end_month": 10,
         "goal": "跑通第一个可验证任务"},
        {"key": "P2", "name": "模型成体", "start_month": 10, "end_month": 18,
         "goal": "形成完整能力矩阵"},
        {"key": "P3", "name": "注册与规模化", "start_month": 18, "end_month": 30,
         "goal": "拿到入场券并完成首批交付"},
    ]


def risk_board(db: Session) -> dict[str, Any]:
    """风险看板：2×2 矩阵定位 + 前置风险清单 + 预算提示。"""
    risks = list(db.execute(select(RiskItem).order_by(RiskItem.code.asc())).scalars())
    frontloaded = [r for r in risks if r.is_frontloaded]
    budget_items = [r for r in risks if r.budget_note]
    quadrants: dict[str, list[str]] = {"高概率高影响": [], "高概率低影响": [], "低概率高影响": [], "低概率低影响": []}
    for risk in risks:
        high_l = risk.likelihood >= 4
        high_s = risk.severity >= 4
        key = ("高概率" if high_l else "低概率") + ("高影响" if high_s else "低影响")
        quadrants[key].append(risk.code)
    return {
        "items": [
            {**r.to_dict(), "quadrant": ("高概率" if r.likelihood >= 4 else "低概率")
             + ("高影响" if r.severity >= 4 else "低影响")}
            for r in risks
        ],
        "frontloaded": [r.to_dict() for r in frontloaded],
        "frontloaded_count": len(frontloaded),
        "quadrants": quadrants,
        "max_risk_score": max((r.risk_score for r in risks), default=0),
        "avg_risk_score": round(float(np.mean([r.risk_score for r in risks])), 4) if risks else 0.0,
        "budget_flagged": [{"code": r.code, "title": r.title, "note": r.budget_note} for r in budget_items],
        "verdict": (
            "R1、R2、R3 是必须在 P0 阶段就有明确动作的前置风险，其余可在推进中动态管理。"
            "其中 R2（许可风险）最容易在早期被忽视，却可能在注册阶段造成根本性返工 —— "
            "建议在立项决议中即明确双源并行策略与预算。"
        ),
    }


def milestone_overview(db: Session) -> dict[str, Any]:
    milestones = list(db.execute(
        select(RegistrationMilestone).order_by(RegistrationMilestone.target_month.asc())
    ).scalars())
    stages = list(db.execute(select(RegistrationStage).order_by(RegistrationStage.sort_order.asc())).scalars())
    return {
        "milestones": [m.to_dict() for m in milestones],
        "stages": [s.to_dict() for s in stages],
        "by_phase": _group_by(milestones),
        "done": sum(1 for m in milestones if m.status == "done"),
        "total": len(milestones),
    }


def _group_by(milestones: list[RegistrationMilestone]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for m in milestones:
        bucket = result.setdefault(m.phase, {
            "phase": m.phase, "name": m.phase_name, "total": 0, "done": 0, "items": [],
        })
        bucket["total"] += 1
        if m.status == "done":
            bucket["done"] += 1
        bucket["items"].append({"code": m.code, "title": m.title, "status": m.status,
                                "target_month": m.target_month, "progress": m.progress})
    for bucket in result.values():
        bucket["progress"] = round(bucket["done"] / bucket["total"], 6) if bucket["total"] else 0.0
    return result


def trial_sites(db: Session) -> dict[str, Any]:
    sites = list(db.execute(select(ClinicalTrialSite)).scalars())
    enroll_target = sum(s.target_cases for s in sites)
    enroll_actual = sum(s.enrolled_cases for s in sites)
    return {
        "sites": [s.to_dict() for s in sites],
        "site_count": len(sites),
        "approved_ethics": sum(1 for s in sites if s.ethics_status == "approved"),
        "target_cases": enroll_target,
        "enrolled_cases": enroll_actual,
        "enrollment_rate": round(enroll_actual / enroll_target, 6) if enroll_target else 0.0,
        "note": "多中心伦理与合同准备在 P2 阶段并行推进，以支撑第 20 月完成首例入组。",
    }


def update_milestone(db: Session, milestone: RegistrationMilestone, payload: dict[str, Any],
                     actor: str = "") -> RegistrationMilestone:
    from app.core.audit import record_audit

    changed = milestone.update_from(payload, allowed=(
        "status", "progress", "actual_date", "owner_name", "note", "evidence_refs_json",
    ))
    db.flush()
    record_audit(
        db,
        action="update_milestone",
        resource_type="registration_milestone",
        resource_id=milestone.id,
        actor=actor,
        summary=f"更新里程碑 {milestone.code} {milestone.title}：{', '.join(changed) or '无变化'}",
        payload={"changed": changed, "status": milestone.status, "progress": milestone.progress},
    )
    return milestone


def update_risk(db: Session, risk: RiskItem, payload: dict[str, Any], actor: str = "") -> RiskItem:
    from app.core.audit import record_audit

    changed = risk.update_from(payload, allowed=(
        "status", "owner_name", "response", "p0_action", "note",
        "likelihood", "severity", "review_date", "budget_note",
    ))
    if "likelihood" in changed or "severity" in changed:
        risk.risk_score = int(risk.likelihood) * int(risk.severity)
    db.flush()
    record_audit(
        db,
        action="update_risk",
        resource_type="reg_risk",
        resource_id=risk.id,
        actor=actor,
        summary=f"更新风险 {risk.code} {risk.title}：{', '.join(changed) or '无变化'}",
        payload={"changed": changed, "status": risk.status, "risk_score": risk.risk_score},
        risk_level="attention" if risk.severity >= 4 else "normal",
    )
    return risk
