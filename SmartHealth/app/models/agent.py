"""智慧医疗 Agent 实体。

设计文档依据：第五章「智慧医疗 Agent 设计」。

五智能体结构（对标 SlideSeek 的 Supervisor+Explorer 与 PathFinder 的四智能体）：
  orchestrator 编排 —— 制定策略、拆解任务、整合证据、判定收敛
  triage       分诊 —— 低倍速全片初筛，判断是否含病变、是否超能力范围
  navigation   导航 —— 模拟医生阅片轨迹，低倍到高倍逐级定位高价值病灶区域
  description  描述 —— 生成精准的形态学自然语言描述
  diagnosis    诊断 —— 整合多轮证据输出鉴别诊断，多轨迹投票

两条硬约束（设计文档明确要求）：
  1. 证据强制引用：每条结论必须绑定具体区域/来源（AgentEvidence）
  2. 医生终审：AI 不给最终诊断，只给可追溯的依据（ReviewTicket）
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel

AGENT_ROLES = ("orchestrator", "triage", "navigation", "description", "diagnosis")
AGENT_ROLE_LABELS = {
    "orchestrator": "编排智能体",
    "triage": "分诊智能体",
    "navigation": "导航智能体",
    "description": "描述智能体",
    "diagnosis": "诊断智能体",
}

MAGNIFICATION_LADDER = ("5X", "10X", "20X", "40X")


class AgentCapability(BaseModel):
    """能力边界声明。Agent 在越界时必须拒识，这是安全设计的输入。"""

    __tablename__ = "agent_capability"

    code = Column(String(64), unique=True, index=True, nullable=False)
    model_base_id = Column(Integer, ForeignKey("model_base.id", ondelete="SET NULL"), nullable=True)
    supported_stainings = Column(String(200), default="H&E")
    supported_organs_json = Column(Text, default="[]")
    supported_tasks_json = Column(Text, default="[]")
    unsupported_json = Column(Text, default="[]")
    """明确不支持的范围（如特殊染色、细胞学涂片、冰冻切片）"""
    min_tissue_ratio = Column(Float, default=0.10)
    max_mpp = Column(Float, default=1.0)
    declaration_text = Column(Text, default="")
    status = Column(String(32), default="active")


class AgentSession(BaseModel):
    """一次 Agent 分析会话。"""

    __tablename__ = "agent_session"

    code = Column(String(64), unique=True, index=True, nullable=False)
    slide_id = Column(Integer, ForeignKey("asset_slide.id", ondelete="CASCADE"), index=True, nullable=False)
    slide_code = Column(String(64), index=True, default="")
    prediction_id = Column(Integer, ForeignKey("pipe_slide_prediction.id", ondelete="SET NULL"), nullable=True)
    inference_job_id = Column(Integer, ForeignKey("pipe_inference_job.id", ondelete="SET NULL"), nullable=True)
    model_version_id = Column(Integer, ForeignKey("model_version.id", ondelete="SET NULL"), nullable=True)
    model_version_label = Column(String(120), default="")

    question = Column(String(512), default="")
    """临床提出的问题，如「该淋巴结是否存在转移灶？」"""
    task_code = Column(String(64), default="lymph_node_metastasis")

    status = Column(String(32), default="queued")
    """queued / running / awaiting_review / reviewed / rejected / failed"""
    plan_json = Column(Text, default="{}")
    """编排智能体的分析计划（策略、探查预算、收敛条件）。"""

    probed_region_count = Column(Integer, default=0)
    """实际探查区域数，对标 SlideSeek 平均 47 个区域。"""
    trajectory_count = Column(Integer, default=0)

    verdict = Column(String(200), default="")
    """AI 倾向性结论（非最终诊断）。"""
    probability = Column(Float, default=0.0)
    calibrated_probability = Column(Float, default=0.0)
    confidence_level = Column(String(16), default="")
    rejected = Column(Boolean, default=False)
    reject_reason = Column(String(300), default="")
    converged = Column(Boolean, default=False)

    evidence_count = Column(Integer, default=0)
    elapsed_ms = Column(Integer, default=0)
    token_usage = Column(Integer, default=0)
    summary_text = Column(Text, default="")
    created_by = Column(String(80), default="")

    steps = relationship("AgentStep", back_populates="session", cascade="all, delete-orphan", lazy="selectin")
    probes = relationship("AgentProbe", back_populates="session", cascade="all, delete-orphan", lazy="selectin")
    evidence = relationship("AgentEvidence", back_populates="session", cascade="all, delete-orphan", lazy="selectin")
    diagnoses = relationship("AgentDiagnosis", back_populates="session", cascade="all, delete-orphan", lazy="selectin")
    votes = relationship("AgentVote", back_populates="session", cascade="all, delete-orphan", lazy="selectin")


class AgentStep(BaseModel):
    """智能体执行轨迹（每个 agent 一条或多条）。"""

    __tablename__ = "agent_step"

    session_id = Column(Integer, ForeignKey("agent_session.id", ondelete="CASCADE"), index=True, nullable=False)
    seq = Column(Integer, default=0)
    agent = Column(String(24), index=True, default="orchestrator")
    agent_label = Column(String(64), default="")
    action = Column(String(120), default="")
    input_summary = Column(String(512), default="")
    output_summary = Column(Text, default="")
    region_json = Column(Text, default="{}")
    refs_json = Column(Text, default="[]")
    """该步骤引用的证据 id 列表 —— 证据强制引用的落点。"""
    status = Column(String(24), default="succeeded")
    elapsed_ms = Column(Integer, default=0)
    token_usage = Column(Integer, default=0)

    session = relationship("AgentSession", back_populates="steps", lazy="selectin")


class AgentProbe(BaseModel):
    """探查记录。分诊在低倍层全片扫描，导航在低倍→高倍逐级收敛。"""

    __tablename__ = "agent_probe"

    session_id = Column(Integer, ForeignKey("agent_session.id", ondelete="CASCADE"), index=True, nullable=False)
    seq = Column(Integer, default=0)
    agent = Column(String(24), default="navigation")
    level = Column(Integer, default=2)
    x = Column(Integer, default=0)
    y = Column(Integer, default=0)
    w = Column(Integer, default=0)
    h = Column(Integer, default=0)
    magnification = Column(String(16), default="5X")
    attention = Column(Float, default=0.0)
    tissue_ratio = Column(Float, default=0.0)
    decision = Column(String(24), default="escalate")
    """triage_out=分诊排除 / escalate=升级到更高倍 / confirm=确认为目标区 / skip=跳过"""
    reason = Column(String(300), default="")
    hit_lesion = Column(Boolean, default=False)
    elapsed_ms = Column(Integer, default=0)

    session = relationship("AgentSession", back_populates="probes", lazy="selectin")


class AgentEvidence(BaseModel):
    """证据条目。每条 AI 结论都必须挂到具体的证据上。"""

    __tablename__ = "agent_evidence"

    session_id = Column(Integer, ForeignKey("agent_session.id", ondelete="CASCADE"), index=True, nullable=False)
    seq = Column(Integer, default=0)
    claim = Column(String(512), default="")
    """被支撑的论断。"""
    evidence_type = Column(String(32), default="attention_region")
    """attention_region / morphology / model_score / similar_case / guideline / capability"""
    source_desc = Column(String(300), default="")
    region_json = Column(Text, default="{}")
    """区域证据：{level, x, y, w, h, magnification}"""
    ref_id = Column(String(64), default="")
    """外部引用 id：相似病例切片号、指南条目编号等。"""
    score = Column(Float, default=0.0)
    strength = Column(String(16), default="moderate")
    """strong / moderate / weak"""
    agent = Column(String(24), default="description")
    created_seq = Column(Integer, default=0)

    session = relationship("AgentSession", back_populates="evidence", lazy="selectin")


class AgentDiagnosis(BaseModel):
    """鉴别诊断列表。rank=1 为主诊断倾向，其余为鉴别项。"""

    __tablename__ = "agent_diagnosis"

    session_id = Column(Integer, ForeignKey("agent_session.id", ondelete="CASCADE"), index=True, nullable=False)
    rank = Column(Integer, default=1)
    category = Column(String(24), default="primary")
    """primary=主诊断倾向 / differential=鉴别项"""
    diagnosis_name = Column(String(200), default="")
    icd_o_3 = Column(String(32), default="")
    probability = Column(Float, default=0.0)
    rationale = Column(Text, default="")
    evidence_ids_json = Column(Text, default="[]")
    evidence_count = Column(Integer, default=0)

    session = relationship("AgentSession", back_populates="diagnoses", lazy="selectin")


class AgentVote(BaseModel):
    """多轨迹投票。不同区域种子/采样顺序下的独立结论，用于稳定性评估。"""

    __tablename__ = "agent_vote"

    session_id = Column(Integer, ForeignKey("agent_session.id", ondelete="CASCADE"), index=True, nullable=False)
    trajectory_no = Column(Integer, default=1)
    region_seed = Column(Integer, default=0)
    probed_regions = Column(Integer, default=0)
    predicted_label = Column(String(120), default="")
    probability = Column(Float, default=0.0)
    agreement = Column(Boolean, default=False)
    note = Column(String(300), default="")

    session = relationship("AgentSession", back_populates="votes", lazy="selectin")


class ReviewTicket(BaseModel):
    """医生终审工单。AI 结论必须经医生确认，产品才闭环。"""

    __tablename__ = "agent_review_ticket"

    code = Column(String(64), unique=True, index=True, nullable=False)
    session_id = Column(Integer, ForeignKey("agent_session.id", ondelete="CASCADE"), index=True, nullable=False)
    slide_id = Column(Integer, ForeignKey("asset_slide.id", ondelete="SET NULL"), nullable=True)
    slide_code = Column(String(64), index=True, default="")

    ai_verdict = Column(String(200), default="")
    ai_probability = Column(Float, default=0.0)
    ai_confidence_level = Column(String(16), default="")
    ai_rejected = Column(Boolean, default=False)

    priority = Column(String(16), default="normal")
    """high=低置信度或拒识，需优先人工复核 / normal"""
    status = Column(String(32), default="pending")
    """pending / claimed / decided / escalated"""
    claimed_by = Column(String(80), default="")
    doctor_name = Column(String(80), default="")
    doctor_verdict = Column(String(200), default="")
    agreement = Column(String(24), default="")
    """agree=采纳 / modify=修正 / disagree=否定"""
    comments = Column(Text, default="")
    turnaround_min = Column(Integer, default=0)
    decided_at = Column(String(32), default="")
    final_label = Column(String(120), default="")
