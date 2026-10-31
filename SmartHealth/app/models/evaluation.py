"""评测基座实体。

设计文档依据：
- 第三章（评测基准是自有标注资产的首要用途）
- 第四章 M3 里程碑（首个单病种达标：内部验证集 AUROC 达阈值，外部验证通过）
- 第七章（临床可验证 → 以 MRMC 方式设计临床试验，医生终审作为对照条件）
- 第十章 R3（跨中心泛化衰减 → 按中心分组的指标）

- EvalDataset / EvalDatasetItem —— 评测集与成员（含中心编号，支持按中心分组）
- EvalRun                     —— 一次评测运行，含自举置信区间
- EvalRocPoint                —— ROC 曲线点
- EvalMetric                  —— 指标明细（可分组、可带 CI）
- MrMcComparison              —— 多阅片者多病例（MRMC）对照
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class EvalDataset(BaseModel):
    """评测集。`is_external=True` 表示外部多中心验证集（院外泛化）。"""

    __tablename__ = "eval_dataset"

    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    task_code = Column(String(64), index=True, default="lymph_node_metastasis")
    label_name = Column(String(120), default="阳性")
    dataset_kind = Column(String(24), default="internal_val")
    """internal_train / internal_val / internal_test / external / regression"""
    is_external = Column(Boolean, default=False)
    slide_count = Column(Integer, default=0)
    patient_count = Column(Integer, default=0)
    positive_count = Column(Integer, default=0)
    positive_rate = Column(Float, default=0.0)
    site_count = Column(Integer, default=0)
    version = Column(String(32), default="v1.0")
    frozen = Column(Boolean, default=False)
    """冻结后禁止增删成员，保证评测结果可比（注册阶段要求）。"""
    description = Column(Text, default="")
    owner_name = Column(String(80), default="")

    items = relationship("EvalDatasetItem", back_populates="dataset", cascade="all, delete-orphan", lazy="selectin")


class EvalDatasetItem(BaseModel):
    __tablename__ = "eval_dataset_item"

    dataset_id = Column(Integer, ForeignKey("eval_dataset.id", ondelete="CASCADE"), index=True, nullable=False)
    slide_id = Column(Integer, ForeignKey("asset_slide.id", ondelete="SET NULL"), nullable=True)
    slide_code = Column(String(64), index=True, default="")
    label_truth = Column(String(120), default="阳性")
    site_code = Column(String(32), index=True, default="SITE-A")
    case_no = Column(String(64), default="")
    reader_a_label = Column(String(120), default="")
    reader_b_label = Column(String(120), default="")
    """两名阅片医生的独立判读结果，供 MRMC 对照。"""
    note = Column(String(300), default="")

    dataset = relationship("EvalDataset", back_populates="items", lazy="selectin")


class EvalRun(BaseModel):
    """一次评测运行。指标含自举置信区间，可按中心分组。"""

    __tablename__ = "eval_run"

    code = Column(String(64), unique=True, index=True, nullable=False)
    dataset_id = Column(Integer, ForeignKey("eval_dataset.id", ondelete="CASCADE"), index=True, nullable=False)
    model_version_id = Column(Integer, ForeignKey("model_version.id", ondelete="SET NULL"), nullable=True)
    model_version_label = Column(String(120), default="")
    task_code = Column(String(64), index=True, default="")
    threshold = Column(Float, default=0.5)
    bootstrap_rounds = Column(Integer, default=500)
    status = Column(String(32), default="pending")
    sample_count = Column(Integer, default=0)
    positive_count = Column(Integer, default=0)

    auroc = Column(Float, default=0.0)
    auprc = Column(Float, default=0.0)
    accuracy = Column(Float, default=0.0)
    sensitivity = Column(Float, default=0.0)
    specificity = Column(Float, default=0.0)
    ppv = Column(Float, default=0.0)
    npv = Column(Float, default=0.0)
    f1 = Column(Float, default=0.0)
    brier = Column(Float, default=0.0)
    ece = Column(Float, default=0.0)
    """期望校准误差。校准质量直接决定「置信度分级」是否可信。"""
    auroc_ci_low = Column(Float, default=0.0)
    auroc_ci_high = Column(Float, default=0.0)

    confusion_json = Column(Text, default="{}")
    by_site_json = Column(Text, default="{}")
    """按中心分组的 AUROC/敏感度，用于发现中心特异性衰减（R3）。"""
    generalization_json = Column(Text, default="{}")
    """跨中心泛化评估结果：院内 vs 院外的 AUC 对比与衰减幅度。"""
    reliability_json = Column(Text, default="[]")
    """校准可靠性曲线数据 [{bin, mean_pred, frac_pos, count}]"""

    started_at = Column(String(32), default="")
    finished_at = Column(String(32), default="")
    elapsed_ms = Column(Integer, default=0)
    passed = Column(Boolean, default=False)
    pass_note = Column(String(300), default="")
    triggered_by = Column(String(80), default="")

    metrics = relationship("EvalMetric", back_populates="run", cascade="all, delete-orphan", lazy="selectin")
    roc_points = relationship("EvalRocPoint", back_populates="run", cascade="all, delete-orphan", lazy="selectin")


class EvalRocPoint(BaseModel):
    __tablename__ = "eval_roc_point"

    run_id = Column(Integer, ForeignKey("eval_run.id", ondelete="CASCADE"), index=True, nullable=False)
    group_key = Column(String(64), default="overall")
    fpr = Column(Float, default=0.0)
    tpr = Column(Float, default=0.0)
    threshold = Column(Float, default=0.0)

    run = relationship("EvalRun", back_populates="roc_points", lazy="selectin")


class EvalMetric(BaseModel):
    """指标明细，支持多维分组（overall / site:XXX / subgroup:XXX）。"""

    __tablename__ = "eval_metric"

    run_id = Column(Integer, ForeignKey("eval_run.id", ondelete="CASCADE"), index=True, nullable=False)
    group_key = Column(String(64), index=True, default="overall")
    metric_key = Column(String(64), index=True, default="")
    metric_label = Column(String(120), default="")
    value = Column(Float, default=0.0)
    ci_low = Column(Float, default=0.0)
    ci_high = Column(Float, default=0.0)
    sample_count = Column(Integer, default=0)
    value_type = Column(String(16), default="ratio")

    run = relationship("EvalRun", back_populates="metrics", lazy="selectin")


class MrMcComparison(BaseModel):
    """MRMC（多阅片者多病例）对照。

    设计文档明确：临床试验以 MRMC 方式设计，医生终审作为对照条件。
    本表保存 AI 与两名（可扩展至多名）阅片者的 AUC 对照与配对自举显著性。
    """

    __tablename__ = "eval_mrmc_comparison"

    code = Column(String(64), unique=True, index=True, nullable=False)
    dataset_id = Column(Integer, ForeignKey("eval_dataset.id", ondelete="CASCADE"), index=True, nullable=False)
    ai_run_id = Column(Integer, ForeignKey("eval_run.id", ondelete="SET NULL"), nullable=True)
    model_version_label = Column(String(120), default="")

    reader_a_name = Column(String(80), default="")
    reader_a_title = Column(String(80), default="")
    reader_b_name = Column(String(80), default="")
    reader_b_title = Column(String(80), default="")

    auc_ai = Column(Float, default=0.0)
    auc_reader_a = Column(Float, default=0.0)
    auc_reader_b = Column(Float, default=0.0)
    reader_average_auc = Column(Float, default=0.0)

    delta_ai_vs_reader_a = Column(Float, default=0.0)
    delta_ai_vs_reader_a_ci_low = Column(Float, default=0.0)
    delta_ai_vs_reader_a_ci_high = Column(Float, default=0.0)
    p_value = Column(Float, default=1.0)
    method = Column(String(64), default="paired-bootstrap")
    conclusion = Column(Text, default="")
    status = Column(String(32), default="done")
    note = Column(String(512), default="")
