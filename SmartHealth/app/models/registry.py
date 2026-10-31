"""注册申报、里程碑与风险实体。

设计文档依据：第七章「合规与注册路径」、第八章「实施路线图与里程碑」、第十章「风险与应对」。

- RegistrationPath      —— 注册路径主档（第三类医疗器械 / SaMD）
- RegistrationStage     —— 注册四大阶段（分类界定 / 产品定型 / 临床试验 / 注册申报）
- RegistrationMilestone —— 8 个里程碑（M1—M8，含可外部核验的验收标准）
- RiskItem              —— 风险台账（R1—R10，标记前置风险）
- ClinicalTrialSite     —— 多中心临床试验中心
- GuidelineDoc          —— 法规依据库
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, Integer, String, Text

from app.models.base import BaseModel

REGISTRATION_STAGES: list[tuple[str, str, int]] = [
    ("classification", "分类界定与前置沟通", 3),
    ("product_freeze", "产品定型与检验", 6),
    ("clinical_trial", "临床试验", 16),
    ("submission", "注册申报与审评", 12),
]


class RegistrationPath(BaseModel):
    """注册路径主档。"""

    __tablename__ = "reg_path"

    code = Column(String(64), unique=True, index=True, nullable=False)
    product_name = Column(String(200), nullable=False)
    product_type = Column(String(32), default="SaMD")
    """SaMD=医疗器械软件 / AI-SaMD=人工智能医疗器械软件"""
    device_class = Column(String(16), default="III")
    """第三类：辅助决策类 AI 医用软件按第三类管理。"""
    classification_code = Column(String(64), default="")
    classification_conclusion = Column(String(300), default="")
    """分类界定结论，P0 阶段必须确认（设计文档 R5 应对措施）。"""

    intended_use = Column(Text, default="")
    """预期用途表述，注册核心文档。"""
    target_population = Column(String(300), default="")
    indications = Column(Text, default="")
    contraindications = Column(Text, default="")
    usage_scenario = Column(String(200), default="")
    """使用场景与操作者（病理医师 / 技师）。"""

    path_type = Column(String(32), default="normal")
    """normal=常规路径 / innovation=创新医疗器械特别审查程序"""
    innovation_qualified = Column(Boolean, default=False)
    change_registration_available = Column(Boolean, default=True)
    """是否符合「核心算法不变而性能优化」的变更注册优化通道（2025 年第 63 号公告）。"""

    model_base_id = Column(Integer, nullable=True)
    model_version_label = Column(String(120), default="")
    status = Column(String(32), default="planning")
    """planning / classification / verification / trial / submission / approved"""
    target_submit_date = Column(String(32), default="")
    target_approval_month = Column(Integer, default=30)
    expected_duration_months = Column(String(32), default="24—36")
    owner_name = Column(String(80), default="")
    note = Column(Text, default="")


class RegistrationStage(BaseModel):
    """注册阶段。start_month/end_month 以「项目第 N 月」计。"""

    __tablename__ = "reg_stage"

    path_id = Column(Integer, index=True, nullable=False)
    code = Column(String(64), index=True, nullable=False)
    name = Column(String(120), nullable=False)
    sort_order = Column(Integer, default=0)
    duration_months_min = Column(Integer, default=0)
    duration_months_max = Column(Integer, default=0)
    start_month = Column(Integer, default=0)
    end_month = Column(Integer, default=0)
    status = Column(String(24), default="pending")
    """pending / in_progress / done / at_risk"""
    progress = Column(Float, default=0.0)
    key_actions = Column(Text, default="")
    deliverables = Column(Text, default="")
    owner_name = Column(String(80), default="")
    note = Column(String(512), default="")


class RegistrationMilestone(BaseModel):
    """里程碑。每个里程碑必须绑定可外部核验的验收标准。"""

    __tablename__ = "reg_milestone"

    path_id = Column(Integer, index=True, nullable=True)
    code = Column(String(16), index=True, nullable=False)
    """M1 — M8"""
    phase = Column(String(16), default="P0")
    """P0 奠基期 / P1 单点突破 / P2 模型成体 / P3 注册与规模化"""
    phase_name = Column(String(64), default="")
    title = Column(String(200), nullable=False)
    target_month = Column(Integer, default=0)
    target_date = Column(String(32), default="")
    actual_date = Column(String(32), default="")
    acceptance_criteria = Column(Text, default="")
    """可外部核验的验收标准。"""
    deliverable = Column(String(300), default="")
    status = Column(String(24), default="pending")
    """pending / in_progress / done / at_risk / missed"""
    progress = Column(Float, default=0.0)
    owner_name = Column(String(80), default="")
    evidence_refs_json = Column(Text, default="[]")
    """验收证据引用（报告编号 / 接口 / 记录 id）。"""
    note = Column(String(512), default="")


class RiskItem(BaseModel):
    """风险台账（R1—R10）。is_frontloaded=True 表示必须在 P0 阶段就有动作的前置风险。"""

    __tablename__ = "reg_risk"

    code = Column(String(16), unique=True, index=True, nullable=False)
    title = Column(String(200), nullable=False)
    category = Column(String(64), default="")
    layer = Column(String(24), default="technical")
    """data / technical / clinical / commercial / compliance / team"""
    description = Column(Text, default="")
    impact = Column(Text, default="")
    response = Column(Text, default="")

    likelihood = Column(Integer, default=3)
    """发生概率 1—5"""
    severity = Column(Integer, default=3)
    """影响程度 1—5"""
    risk_score = Column(Integer, default=9)
    is_frontloaded = Column(Boolean, default=False)
    p0_action = Column(Text, default="")
    owner_name = Column(String(80), default="")
    status = Column(String(24), default="open")
    """open / mitigating / closed / accepted / occurred"""
    review_date = Column(String(32), default="")
    budget_note = Column(String(300), default="")
    """是否需要单独列支预算（如 R2 自研编码器替换成本）。"""
    note = Column(String(512), default="")


class ClinicalTrialSite(BaseModel):
    """多中心临床试验中心。"""

    __tablename__ = "reg_trial_site"

    code = Column(String(64), unique=True, index=True, nullable=False)
    hospital = Column(String(200), nullable=False)
    city = Column(String(64), default="")
    site_type = Column(String(32), default="lead")
    """lead=牵头单位 / participating=参与单位"""
    ethics_status = Column(String(24), default="pending")
    """pending / submitted / approved / rejected"""
    contract_status = Column(String(24), default="pending")
    pi_name = Column(String(80), default="")
    pi_title = Column(String(80), default="")
    target_cases = Column(Integer, default=0)
    enrolled_cases = Column(Integer, default=0)
    enrollment_rate = Column(Float, default=0.0)
    positive_rate = Column(Float, default=0.0)
    start_date = Column(String(32), default="")
    status = Column(String(24), default="preparing")
    """preparing / enrolling / closed / suspended"""
    note = Column(String(512), default="")


class GuidelineDoc(BaseModel):
    """法规依据库。方案中所有合规结论都应能挂到具体文件。"""

    __tablename__ = "reg_guideline"

    code = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(300), nullable=False)
    publisher = Column(String(200), default="")
    doc_no = Column(String(120), default="")
    publish_date = Column(String(32), default="")
    effective_date = Column(String(32), default="")
    category = Column(String(64), default="other")
    """policy=政策意见 / nmpa=药监公告 / guide=指导原则 / payment=医保价格 / standard=标准"""
    key_points = Column(Text, default="")
    applies_to = Column(String(300), default="")
    url = Column(String(320), default="")
