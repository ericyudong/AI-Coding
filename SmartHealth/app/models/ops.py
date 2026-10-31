"""运营看板实体：团队编制、成本结构、KPI 快照。

设计文档依据：第九章「投入产出与团队配置」（首期 17—25 人，建议 18 人起步）
与第十一章「结论与立项建议」。

注意：成本在本平台中**只保存相对结构比例**（与设计文档口径一致）。
不落任何自造的绝对金额，避免误导立项决策。
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, Integer, String, Text
from sqlalchemy.orm import relationship  # noqa: F401  （保持与其他模型一致的导入风格）

from app.models.base import BaseModel


class TeamRole(BaseModel):
    """团队编制角色。"""

    __tablename__ = "ops_team_role"

    code = Column(String(64), unique=True, index=True, nullable=False)
    role_name = Column(String(120), nullable=False)
    cluster = Column(String(32), default="algorithm")
    """clinical=临床 / algorithm=算法 / engineering=工程 / compliance=注册合规 / data=数据标注 / product=产品运营"""
    stage = Column(String(16), default="P0")
    """P0 / P1 / P2"""
    headcount_min = Column(Integer, default=0)
    headcount_max = Column(Integer, default=0)
    headcount_suggested = Column(Integer, default=0)
    is_mandatory = Column(Boolean, default=False)
    """是否必须在 P0 到位的必需岗（如首席医学官）。"""
    onboard_month = Column(Integer, default=0)
    skills = Column(String(512), default="")
    responsibility = Column(Text, default="")
    note = Column(String(512), default="")
    sort_order = Column(Integer, default=0)


class CostStructure(BaseModel):
    """成本结构（相对比例，非绝对金额）。"""

    __tablename__ = "ops_cost_structure"

    code = Column(String(64), unique=True, index=True, nullable=False)
    category = Column(String(120), nullable=False)
    ratio_low = Column(Float, default=0.0)
    ratio_high = Column(Float, default=0.0)
    elasticity = Column(String(32), default="medium")
    """high=最强弹性项（可调节奏） / medium / low"""
    phase = Column(String(16), default="all")
    note = Column(String(512), default="")
    sort_order = Column(Integer, default=0)


class RevenuePath(BaseModel):
    """收入路径（分阶段收入设计，对应 R5 的现金流应对）。"""

    __tablename__ = "ops_revenue_path"

    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(160), nullable=False)
    phase = Column(String(16), default="P0")
    """P0 / P1 / P2 / P3"""
    path_type = Column(String(32), default="research_cooperation")
    """research_cooperation=科研合作 / pilot_service=试点服务 / saas=云服务订阅 / device_sales=器械软件销售 / data_license=数据授权"""
    prerequisite = Column(String(300), default="")
    status = Column(String(24), default="planned")
    """planned / active / paused / ended"""
    note = Column(String(512), default="")


class KpiSnapshot(BaseModel):
    """运营 KPI 快照（用于看板的趋势口径）。"""

    __tablename__ = "ops_kpi_snapshot"

    snapshot_date = Column(String(16), index=True, nullable=False)
    asset_count = Column(Integer, default=0)
    slide_count = Column(Integer, default=0)
    annotated_slide_count = Column(Integer, default=0)
    region_annotation_count = Column(Integer, default=0)
    feature_ready_count = Column(Integer, default=0)
    model_auroc = Column(Float, default=0.0)
    external_auroc = Column(Float, default=0.0)
    agent_session_count = Column(Integer, default=0)
    agent_reject_rate = Column(Float, default=0.0)
    review_agreement_rate = Column(Float, default=0.0)
    milestone_done = Column(Integer, default=0)
    milestone_total = Column(Integer, default=0)
    audit_record_count = Column(Integer, default=0)
    edge_online_count = Column(Integer, default=0)
    headcount_now = Column(Integer, default=0)
    headcount_target = Column(Integer, default=0)


class StrategicDecision(BaseModel):
    """立项决策与首期动作（对应第十一章结论与立项建议）。"""

    __tablename__ = "ops_strategic_decision"

    code = Column(String(64), unique=True, index=True, nullable=False)
    decision_type = Column(String(32), default="project_approval")
    """project_approval=项目立项 / dual_track=双轨制确认 / budget=预算授权 / appointment=关键岗位任命"""
    title = Column(String(200), nullable=False)
    content = Column(Text, default="")
    rationale = Column(Text, default="")
    action_items_json = Column(Text, default="[]")
    """[{title, description, owner, deadline, status}]"""
    owner_name = Column(String(80), default="")
    status = Column(String(24), default="proposed")
    """proposed / approved / rejected / deferred"""
    decided_at = Column(String(32), default="")
    sort_order = Column(Integer, default=0)
