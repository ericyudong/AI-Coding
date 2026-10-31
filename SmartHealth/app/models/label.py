"""标签体系实体。

设计文档依据：第三章「数据资产盘点与治理方案」——四层标签体系（病例级 / 切片级 /
区域级 / 细胞级）+ 一层质控层；标注 SOP、资质记录与仲裁机制必须全程留痕。

- LabelSchema      —— 标签定义（四层 + 质控层）
- AnnotatorProfile —— 标注人员资质（职称 / 亚专科方向 / 培训记录）
- LabelSop         —— 标注 SOP 版本与审核状态
- Annotation       —— 标注记录（含区域框，供区域级/细胞级标签）
- QcRecord         —— 质控记录（合格率、返工、抽检）
- Arbitration      —— 专家意见冲突仲裁记录
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel

LABEL_LAYERS = ("case", "slide", "region", "cell", "qc")
LABEL_LAYER_LABELS = {
    "case": "病例级",
    "slide": "切片级",
    "region": "区域级",
    "cell": "细胞级",
    "qc": "质控层",
}


class LabelSchema(BaseModel):
    """标签定义。四层标签体系 + 质控层。"""

    __tablename__ = "label_schema"

    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(160), nullable=False)
    layer = Column(String(16), index=True, nullable=False)
    """case / slide / region / cell / qc"""

    value_type = Column(String(24), default="categorical")
    """categorical=枚举 / numeric=数值 / boolean / bbox=区域框 / mask=像素掩膜"""
    allowed_values_json = Column(Text, default="[]")
    unit = Column(String(32), default="")
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)

    # 医学术语对齐（可解释性与互操作性）
    snomed_code = Column(String(64), default="")
    icd_o_3_code = Column(String(32), default="")
    term_source = Column(String(80), default="")

    required_for_training = Column(Boolean, default=False)
    required_for_registration = Column(Boolean, default=False)
    """注册必备标签：缺失将直接阻断注册申报（设计文档第七章「问一 数据可溯源」）。"""
    multi_select = Column(Boolean, default=False)
    applicable_stainings = Column(String(120), default="H&E")
    description = Column(Text, default="")
    sort_order = Column(Integer, default=0)

    annotations = relationship("Annotation", back_populates="schema", lazy="selectin")


class AnnotatorProfile(BaseModel):
    """标注人员资质档案。审评要求可证明「谁标的、够不够格」。"""

    __tablename__ = "label_annotator"

    user_id = Column(Integer, ForeignKey("sys_user.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(80), index=True, nullable=False)
    employee_no = Column(String(64), default="")
    title = Column(String(80), default="")
    """主任医师 / 副主任医师 / 主治医师 / 住院医师 / 技师"""
    subspecialty = Column(String(120), default="")
    """亚专科方向：消化 / 呼吸 / 乳腺 / 妇科 / 血液 …"""
    hospital = Column(String(160), default="")
    years_experience = Column(Integer, default=0)
    annual_slide_volume = Column(Integer, default=0)
    certificate_no = Column(String(120), default="")
    training_records_json = Column(Text, default="[]")
    training_hours = Column(Float, default=0.0)
    qualification_verified = Column(Boolean, default=False)
    verified_by = Column(String(80), default="")
    verified_at = Column(String(32), default="")
    max_active_tasks = Column(Integer, default=200)
    status = Column(String(32), default="active")


class LabelSop(BaseModel):
    """标注 SOP（标准作业程序）版本。注册阶段必须提供完整 SOP 与运行记录。"""

    __tablename__ = "label_sop"

    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    version = Column(String(32), default="v1.0")
    scope = Column(String(200), default="")
    owner_name = Column(String(80), default="")
    medical_review_status = Column(String(32), default="pending")
    """pending / approved / rejected"""
    medical_reviewer = Column(String(80), default="")
    medical_reviewed_at = Column(String(32), default="")
    arbitration_rule = Column(Text, default="")
    """多名专家意见冲突时的仲裁规则（如 2/3 多数、上级医师终裁）。"""
    content = Column(Text, default="")
    effective_date = Column(String(32), default="")
    status = Column(String(32), default="draft")


class Annotation(BaseModel):
    """标注记录。区域级/细胞级标签携带坐标框。"""

    __tablename__ = "label_annotation"

    slide_id = Column(Integer, ForeignKey("asset_slide.id", ondelete="CASCADE"), index=True, nullable=False)
    slide_code = Column(String(64), index=True, default="")
    schema_id = Column(Integer, ForeignKey("label_schema.id", ondelete="CASCADE"), index=True, nullable=False)
    schema_code = Column(String(64), index=True, default="")
    layer = Column(String(16), index=True, default="slide")

    annotator_id = Column(Integer, ForeignKey("label_annotator.id", ondelete="SET NULL"), nullable=True)
    annotator_name = Column(String(80), default="")

    value_text = Column(String(512), default="")
    value_num = Column(Float, nullable=True)
    value_bool = Column(Boolean, nullable=True)
    region_json = Column(Text, default="[]")
    """区域框列表 [{level, x, y, w, h}] 或细胞坐标点，供区域级/细胞级标签使用。"""

    confidence = Column(Float, default=1.0)
    elapsed_sec = Column(Integer, default=0)
    tool = Column(String(64), default="web")
    revision = Column(Integer, default=1)
    status = Column(String(32), default="submitted")
    """submitted / qc_passed / qc_failed / arbitrated / final"""
    note = Column(String(512), default="")

    schema = relationship("LabelSchema", back_populates="annotations", lazy="selectin")


class QcRecord(BaseModel):
    """质控层记录：抽检、合格率、返工。"""

    __tablename__ = "label_qc"

    slide_id = Column(Integer, ForeignKey("asset_slide.id", ondelete="CASCADE"), index=True, nullable=True)
    slide_code = Column(String(64), index=True, default="")
    annotation_id = Column(Integer, ForeignKey("label_annotation.id", ondelete="SET NULL"), nullable=True)
    qc_type = Column(String(32), default="sampling")
    """sampling=抽检 / full=全量复核 / auto=自动一致性校验 / rework=返工复检"""
    reviewer_name = Column(String(80), default="")
    result = Column(String(16), default="pass")
    """pass / fail / rework"""
    score = Column(Float, default=0.0)
    defect_types_json = Column(Text, default="[]")
    rework_required = Column(Boolean, default=False)
    reviewed_at = Column(String(32), default="")
    note = Column(String(512), default="")


class Arbitration(BaseModel):
    """标注冲突仲裁记录。审评要求提供仲裁机制与运行记录。"""

    __tablename__ = "label_arbitration"

    slide_id = Column(Integer, ForeignKey("asset_slide.id", ondelete="CASCADE"), index=True, nullable=True)
    slide_code = Column(String(64), index=True, default="")
    schema_id = Column(Integer, ForeignKey("label_schema.id", ondelete="SET NULL"), nullable=True)
    schema_code = Column(String(64), default="")
    conflict_summary = Column(String(512), default="")
    opinions_json = Column(Text, default="[]")
    """各标注者意见 [{annotator, value, confidence}]"""
    rule_applied = Column(String(200), default="")
    final_value = Column(String(512), default="")
    arbitrator_name = Column(String(80), default="")
    arbitrator_title = Column(String(80), default="")
    status = Column(String(32), default="open")
    """open / resolved / escalated"""
    decided_at = Column(String(32), default="")
