"""合规与注册支撑实体。

设计文档依据：第七章「合规与注册路径」。

- EthicsRecord           —— 伦理审批台账
- ConsentRecord          —— 知情同意覆盖台账
- AuditChainRecord       —— 审计哈希链（由 core/audit.py 写入）
- DataBoundaryCheck      —— 数据不出域校验记录
- SecurityAssessment     —— 第三方检测 / 网络安全测评 / 软件定版
- ExplainabilityPackage  —— 可解释性四件套（空间 / 语义 / 量化 / 拒识）
- ReviewQuestionAnswer   —— 审评三道关口（数据可溯源 / 算法可解释 / 临床可验证）的应答台账
- ChangeRegistration     —— 核心算法不变而性能优化的变更注册（2025 年第 63 号公告）
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text

from app.models.base import BaseModel

REVIEW_GROUPS = ("data_traceability", "algorithm_explainability", "clinical_validity")
REVIEW_GROUP_LABELS = {
    "data_traceability": "数据可溯源",
    "algorithm_explainability": "算法可解释",
    "clinical_validity": "临床可验证",
}


class EthicsRecord(BaseModel):
    """伦理审批记录。"""

    __tablename__ = "cmp_ethics_record"

    code = Column(String(64), unique=True, index=True, nullable=False)
    asset_id = Column(Integer, ForeignKey("asset_dataset.id", ondelete="SET NULL"), nullable=True)
    hospital = Column(String(200), nullable=False)
    committee = Column(String(200), default="")
    ethics_no = Column(String(120), default="")
    approval_date = Column(String(32), default="")
    valid_until = Column(String(32), default="")
    scope = Column(String(512), default="")
    """审批覆盖范围（用途、数据范围、期限）。"""
    use_purpose = Column(String(200), default="")
    """科研 / 产品开发 / 注册申报"""
    document_path = Column(String(512), default="")
    status = Column(String(32), default="approved")
    """approved / pending / expired / revoked"""
    owner_name = Column(String(80), default="")
    note = Column(String(512), default="")


class ConsentRecord(BaseModel):
    """知情同意覆盖台账。注册阶段必须可逐例证明。"""

    __tablename__ = "cmp_consent_record"

    code = Column(String(64), unique=True, index=True, nullable=False)
    asset_id = Column(Integer, ForeignKey("asset_dataset.id", ondelete="SET NULL"), nullable=True)
    consent_type = Column(String(32), default="broad")
    """broad=泛知情同意 / study=特定研究 / specific=逐例具体授权 / waived=豁免"""
    case_count = Column(Integer, default=0)
    covered_count = Column(Integer, default=0)
    coverage_rate = Column(Float, default=0.0)
    waiver_granted = Column(Boolean, default=False)
    waiver_reason = Column(String(512), default="")
    waiver_approved_by = Column(String(80), default="")
    document_ref = Column(String(512), default="")
    last_audit_at = Column(String(32), default="")
    status = Column(String(32), default="valid")


class AuditChainRecord(BaseModel):
    """审计哈希链记录。禁止业务侧直接修改，只允许追加。"""

    __tablename__ = "cmp_audit_chain"

    seq = Column(Integer, unique=True, index=True, nullable=False)
    action = Column(String(120), index=True, nullable=False)
    resource_type = Column(String(64), index=True, default="")
    resource_id = Column(String(64), index=True, default="")
    actor = Column(String(80), default="")
    actor_role = Column(String(120), default="")
    summary = Column(String(512), default="")
    risk_level = Column(String(16), default="normal")
    """normal / attention / critical"""
    payload_json = Column(Text, default="{}")
    body_json = Column(Text, default="{}")
    prev_hash = Column(String(64), default="")
    record_hash = Column(String(64), index=True, default="")

    def to_dict(self, exclude: tuple[str, ...] = (), include: tuple[str, ...] | None = None) -> dict:
        data = super().to_dict(exclude=exclude, include=include)
        return data


class DataBoundaryCheck(BaseModel):
    """数据不出域校验记录（对应部署架构中的本地化约束）。"""

    __tablename__ = "cmp_data_boundary_check"

    code = Column(String(64), unique=True, index=True, nullable=False)
    checked_at = Column(String(32), default="")
    scope = Column(String(200), default="全部资产")
    slide_count = Column(Integer, default=0)
    checks_json = Column(Text, default="[]")
    """逐项检查结果 [{item, expectation, actual, passed, detail}]"""
    passed = Column(Boolean, default=True)
    violation_count = Column(Integer, default=0)
    violations_json = Column(Text, default="[]")
    method = Column(String(120), default="静态配置核查 + 出网流量审计")
    checked_by = Column(String(80), default="")
    note = Column(String(512), default="")


class SecurityAssessment(BaseModel):
    """第三方检测 / 网络安全测评 / 软件定版记录。"""

    __tablename__ = "cmp_security_assessment"

    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    assessment_type = Column(String(32), default="third_party_test")
    """third_party_test=第三方检测 / network_security=网络安全测评 / software_freeze=软件定版 / emc=电磁兼容（硬件相关）"""
    organization = Column(String(200), default="")
    report_no = Column(String(120), default="")
    result = Column(String(32), default="pending")
    """passed / failed / pending / na"""
    assessed_at = Column(String(32), default="")
    valid_until = Column(String(32), default="")
    issues_json = Column(Text, default="[]")
    owner_name = Column(String(80), default="")
    note = Column(String(512), default="")


class ExplainabilityPackage(BaseModel):
    """可解释性四件套：空间 / 语义 / 量化 / 拒识。"""

    __tablename__ = "cmp_explainability_package"

    code = Column(String(64), unique=True, index=True, nullable=False)
    model_version_id = Column(Integer, ForeignKey("model_version.id", ondelete="SET NULL"), nullable=True)
    model_version_label = Column(String(120), default="")
    spatial_desc = Column(Text, default="")
    """空间可解释：注意力热区定位到具体区域坐标与倍率。"""
    semantic_desc = Column(Text, default="")
    """语义可解释：形态学特征的自然语言描述。"""
    quantitative_desc = Column(Text, default="")
    """量化可解释：概率、置信区间、校准误差、投票一致性。"""
    rejection_desc = Column(Text, default="")
    """拒识机制：越界/低置信度时拒绝给出结论并转人工。"""
    items_json = Column(Text, default="[]")
    completeness = Column(Float, default=0.0)
    status = Column(String(32), default="draft")
    """draft / complete / verified"""
    verified_by = Column(String(80), default="")


class ReviewQuestionAnswer(BaseModel):
    """审评三道关口的应答台账。

    设计文档明确：能否通过三类证审评，取决于这三个问题；
    技术选型必须以此倒推，而不是先选型再补合规。
    """

    __tablename__ = "cmp_review_answer"

    code = Column(String(64), unique=True, index=True, nullable=False)
    group_key = Column(String(40), index=True, nullable=False)
    """data_traceability / algorithm_explainability / clinical_validity"""
    question = Column(String(512), nullable=False)
    answer = Column(Text, default="")
    evidence_refs_json = Column(Text, default="[]")
    """支撑材料引用：台账编号 / 报告编号 / 接口路径。"""
    regulation_ref = Column(String(300), default="")
    owner_name = Column(String(80), default="")
    status = Column(String(32), default="draft")
    """draft / ready / gap"""
    gap_note = Column(String(512), default="")
    sort_order = Column(Integer, default=0)


class ChangeRegistration(BaseModel):
    """变更注册台账（对应 2025 年第 63 号公告的优化通道）。"""

    __tablename__ = "cmp_change_registration"

    code = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(200), nullable=False)
    change_type = Column(String(32), default="performance_optimization")
    """performance_optimization=核心算法不变而性能优化 / major=重大变更 / minor=轻微变更"""
    from_version = Column(String(64), default="")
    to_version = Column(String(64), default="")
    algorithm_unchanged = Column(Boolean, default=True)
    impact_analysis = Column(Text, default="")
    verification_ref = Column(String(200), default="")
    status = Column(String(32), default="draft")
    owner_name = Column(String(80), default="")
    submitted_at = Column(String(32), default="")
    note = Column(String(512), default="")
