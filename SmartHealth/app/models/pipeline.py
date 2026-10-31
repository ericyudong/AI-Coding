"""推理流水线实体：推理任务、切片预测、注意力热区、切片级向量索引。

设计文档依据：第四章 4.4（图块级特征 → 切片级聚合）与第五章（Agent 证据来源）。

关键设计：
- 注意力权重不是装饰。AttentionRegion 直接来自 ABMIL 的注意力分布，
  是「算法可解释」（注册审评问二）与 Agent「证据强制引用」的同一份底层数据。
- SlidePrediction.rejected 与 reject_reason 承载「拒识」机制，
  属注册审评关注的安全设计，必须有据可查。
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class InferenceJob(BaseModel):
    """批量/单例推理任务。"""

    __tablename__ = "pipe_inference_job"

    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(200), default="")
    model_version_id = Column(Integer, ForeignKey("model_version.id", ondelete="SET NULL"), index=True, nullable=True)
    model_version_label = Column(String(120), default="")
    encoder_code = Column(String(64), default="")
    job_kind = Column(String(24), default="batch")
    """batch=批量评测推理 / single=单切片 / agent=由 Agent 触发的按需推理"""

    slide_ids_json = Column(Text, default="[]")
    slice_count = Column(Integer, default=0)
    finished_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)

    normalize = Column(String(32), default="reinhard")
    tile_size = Column(Integer, default=256)
    stride = Column(Integer, default=256)
    max_tiles = Column(Integer, default=0)
    threshold = Column(Float, default=0.5)
    params_json = Column(Text, default="{}")

    status = Column(String(32), default="pending")
    """pending / running / succeeded / failed / cancelled"""
    progress = Column(Float, default=0.0)
    started_at = Column(String(32), default="")
    finished_at = Column(String(32), default="")
    elapsed_ms = Column(Integer, default=0)
    summary_json = Column(Text, default="{}")
    log_tail = Column(Text, default="")
    triggered_by = Column(String(80), default="")

    predictions = relationship("SlidePrediction", back_populates="job", lazy="selectin")


class SlidePrediction(BaseModel):
    """单张切片的模型输出。"""

    __tablename__ = "pipe_slide_prediction"

    job_id = Column(Integer, ForeignKey("pipe_inference_job.id", ondelete="CASCADE"), index=True, nullable=True)
    slide_id = Column(Integer, ForeignKey("asset_slide.id", ondelete="CASCADE"), index=True, nullable=False)
    slide_code = Column(String(64), index=True, default="")
    model_version_id = Column(Integer, ForeignKey("model_version.id", ondelete="SET NULL"), index=True, nullable=True)
    model_version_label = Column(String(120), default="")
    encoder_code = Column(String(64), default="")

    task_code = Column(String(64), default="lymph_node_metastasis")
    """任务编码，如淋巴结转移检测 / 消化道早癌识别 / 宫颈细胞学"""
    label_name = Column(String(120), default="阳性")
    label_truth = Column(String(120), default="")
    """金标准标签（来自标注），评测时用于计算指标。"""

    probability = Column(Float, default=0.0)
    calibrated_probability = Column(Float, default=0.0)
    threshold = Column(Float, default=0.5)
    decision = Column(String(16), default="negative")
    """positive / negative / rejected"""
    rejected = Column(Boolean, default=False)
    reject_reason = Column(String(200), default="")
    confidence_level = Column(String(16), default="")
    """high / medium / low（对应设计文档的置信度分级）"""

    tile_count = Column(Integer, default=0)
    embedding_dim = Column(Integer, default=0)
    elapsed_ms = Column(Integer, default=0)
    heatmap_path = Column(String(512), default="")
    attention_summary_json = Column(Text, default="{}")
    feature_path = Column(String(512), default="")

    job = relationship("InferenceJob", back_populates="predictions", lazy="selectin")
    regions = relationship("AttentionRegion", back_populates="prediction", cascade="all, delete-orphan", lazy="selectin")


class AttentionRegion(BaseModel):
    """ABMIL 注意力热区。既是可解释性证据，也是 Agent 导航的候选区域池。"""

    __tablename__ = "pipe_attention_region"

    prediction_id = Column(Integer, ForeignKey("pipe_slide_prediction.id", ondelete="CASCADE"), index=True, nullable=False)
    slide_id = Column(Integer, ForeignKey("asset_slide.id", ondelete="CASCADE"), index=True, nullable=False)
    rank = Column(Integer, default=0)
    """按注意力降序的序号，1 为最热区。"""

    level = Column(Integer, default=0)
    x = Column(Integer, default=0)
    y = Column(Integer, default=0)
    w = Column(Integer, default=0)
    h = Column(Integer, default=0)
    magnification = Column(String(16), default="20X")
    attention = Column(Float, default=0.0)
    attention_share = Column(Float, default=0.0)
    """该区域占整张切片注意力总量的比例，用于证据强度表述。"""
    mean_intensity = Column(Float, default=0.0)
    tissue_ratio = Column(Float, default=0.0)
    is_lesion_overlap = Column(Boolean, default=False)
    """是否落入金标准病灶框内，用于 Agent 导航命中率评估。"""

    prediction = relationship("SlidePrediction", back_populates="regions", lazy="selectin")


class CaseEmbedding(BaseModel):
    """切片级向量索引。支撑「相似病例检索」，是描述智能体的知识来源。"""

    __tablename__ = "pipe_case_embedding"

    slide_id = Column(Integer, ForeignKey("asset_slide.id", ondelete="CASCADE"), index=True, nullable=False)
    slide_code = Column(String(64), index=True, default="")
    case_no = Column(String(64), index=True, default="")
    """病例号。相似病例检索时用于排除同一病例的其他切片（避免数据泄漏式「相似」）。"""
    model_version_id = Column(Integer, ForeignKey("model_version.id", ondelete="SET NULL"), nullable=True)
    encoder_code = Column(String(64), default="")
    dim = Column(Integer, default=0)
    vector_path = Column(String(512), default="")
    diagnosis_text = Column(String(512), default="")
    cancer_type = Column(String(120), default="")
    organ = Column(String(80), default="")
    site_code = Column(String(32), default="")
    split = Column(String(16), default="train")
    status = Column(String(32), default="ready")
