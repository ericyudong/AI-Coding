"""数据资产实体。

设计文档依据：第三章「数据资产盘点与治理方案」。
- DataAsset       —— 资产批次（对应 3.1「资产盘点」）
- Slide           —— 数字病理切片（对应 3.2「切片级」与 3.3 增量扩展）
- SlideFeature    —— 特征预计算产物，落盘 npz，库内留元数据（对应 4.3 Stage A）
- StorageStat     —— 存储分层统计（对应 6.3 热/温/冷三层）
- AssetExtension  —— 数据扩展三条路径（院内增量 / 外部合作 / 公开数据补充）
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class DataAsset(BaseModel):
    """数据资产批次。核心口径字段用于回答审评的「数据可溯源」。"""

    __tablename__ = "asset_dataset"

    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)

    # 来源与授权（合规必填口径）
    source_type = Column(String(32), default="in_hospital")
    """in_hospital=院内自有 / partner=外部合作 / public=公开数据集"""
    source_org = Column(String(200), default="")
    ethics_approved = Column(Boolean, default=False)
    ethics_no = Column(String(120), default="")
    consent_covered = Column(Boolean, default=False)
    """是否逐例覆盖知情同意（设计文档：注册阶段必须可证明）。"""
    deidentified = Column(Boolean, default=False)
    data_boundary = Column(String(32), default="local")
    """local=数据不出域 / federated=仅出梯度 / export=已获批导出"""

    # 业务口径
    organ_system = Column(String(80), default="")
    cancer_type = Column(String(120), default="")
    staining_types = Column(String(200), default="H&E")
    slide_count = Column(Integer, default=0)
    annotated_slide_count = Column(Integer, default=0)
    patient_count = Column(Integer, default=0)
    total_bytes = Column(Integer, default=0)
    magnification = Column(String(64), default="20X")
    year_from = Column(Integer, default=2020)
    year_to = Column(Integer, default=2025)
    org_code = Column(String(64), index=True, default="")
    """归属机构。与 asset_slide.org_code 一致，便于单表过滤。"""
    site_codes = Column(String(400), default="")
    """本资产涉及的数据中心，逗号分隔（如 "SITE-A,SITE-B"），用于 site 级隔离。"""
    owner_department = Column(String(120), default="")
    owner_name = Column(String(80), default="")

    # 治理与优先级
    quality_score = Column(Float, default=0.0)
    label_coverage = Column(Float, default=0.0)
    p0_action = Column(Boolean, default=False)
    """是否 P0 阶段必须处置（设计文档：首期聚焦 2—3 个样本充足的病种）。"""
    status = Column(String(32), default="registered")
    """registered=已登记 / profiling=盘点中 / ready=可训练 / restricted=受限"""
    notes = Column(Text, default="")

    slides = relationship("Slide", back_populates="asset", cascade="all, delete-orphan", lazy="selectin")


class Slide(BaseModel):
    """数字病理切片（WSI）。"""

    __tablename__ = "asset_slide"

    code = Column(String(64), unique=True, index=True, nullable=False)
    asset_id = Column(Integer, ForeignKey("asset_dataset.id", ondelete="SET NULL"), nullable=True)

    case_no = Column(String(64), index=True, default="")
    patient_pseudo_id = Column(String(64), index=True, default="")
    """脱敏后的伪匿名患者编号；真实身份信息不作为平台字段存储。"""

    organ = Column(String(80), default="")
    cancer_type = Column(String(120), default="")
    staining = Column(String(32), default="H&E")
    """H&E / IHC / 特殊染色"""
    ihc_marker = Column(String(64), default="")
    diagnosis_text = Column(String(512), default="")
    icd_o_3 = Column(String(32), default="")

    magnification = Column(String(16), default="20X")
    mpp = Column(Float, default=0.5)
    width = Column(Integer, default=0)
    height = Column(Integer, default=0)
    level_count = Column(Integer, default=1)
    tile_count = Column(Integer, default=0)
    scanner = Column(String(80), default="")

    file_path = Column(String(512), default="")
    file_bytes = Column(Integer, default=0)
    checksum = Column(String(64), index=True, default="")
    """文件内容 SHA256。用于上传去重与"这份特征到底来自哪个文件"的溯源。"""
    org_code = Column(String(64), index=True, default="")
    """归属机构。行级数据隔离的直接依据（见 core/scoping.py）。"""
    source_filename = Column(String(256), default="")
    """上传时的原始文件名。科室对账时用的是原始文件名，不是我们重命名后的路径。"""
    uploaded_by = Column(String(80), default="")
    thumbnail_path = Column(String(512), default="")
    storage_tier = Column(String(16), default="hot")
    """hot=NVMe SSD / warm=NAS RAID6 / cold=对象存储归档"""

    split = Column(String(16), default="train")
    """train / val / test / external（外部多中心验证集）"""
    site_code = Column(String(32), default="")
    """来源中心编号，用于跨中心泛化（设计文档 R3 中心特异性）评估。"""

    has_lesion = Column(Boolean, default=False)
    lesion_ratio = Column(Float, default=0.0)
    lesion_bbox_json = Column(Text, default="[]")
    """合成/标注的病灶区域框，供 Agent 导航命中率与注意力图对照使用。"""

    status = Column(String(32), default="registered")
    """registered / profiled / featured / inferred / failed"""

    asset = relationship("DataAsset", back_populates="slides", lazy="selectin")


class SlideFeature(BaseModel):
    """切片级特征库（特征预计算产物）。

    设计文档 4.3 Stage A：把万张级切片一次性转成可复用特征库。
    向量本体落盘 data/features/*.npz，库内只留元数据与可核查摘要。
    """

    __tablename__ = "asset_slide_feature"

    slide_id = Column(Integer, ForeignKey("asset_slide.id", ondelete="CASCADE"), index=True, nullable=False)
    slide_code = Column(String(64), index=True, default="")
    encoder_code = Column(String(64), index=True, nullable=False)
    embedding_dim = Column(Integer, default=0)
    tile_count = Column(Integer, default=0)
    magnification = Column(String(16), default="20X")
    tile_size = Column(Integer, default=256)
    stride = Column(Integer, default=256)
    normalize = Column(String(32), default="reinhard")
    feature_path = Column(String(512), default="")
    coords_path = Column(String(512), default="")
    checksum = Column(String(64), default="")
    """特征包 SHA-256，用于审评阶段核验特征可复现。"""
    elapsed_ms = Column(Integer, default=0)
    job_id = Column(Integer, default=0)


class StorageStat(BaseModel):
    """存储分层与容量统计（对应设计文档 6.3）。"""

    __tablename__ = "asset_storage_stat"

    stat_date = Column(String(16), index=True, nullable=False)
    tier = Column(String(16), index=True, nullable=False)
    """hot / warm / cold"""
    slide_count = Column(Integer, default=0)
    bytes_used = Column(Integer, default=0)
    capacity_bytes = Column(Integer, default=0)
    media = Column(String(120), default="")


class AssetExtension(BaseModel):
    """数据扩展路径（设计文档 3.3：院内增量 / 外部合作 / 公开数据补充）。"""

    __tablename__ = "asset_extension"

    asset_id = Column(Integer, ForeignKey("asset_dataset.id", ondelete="CASCADE"), nullable=True)
    path_type = Column(String(32), nullable=False)
    """increment=院内增量 / partner=外部合作 / public=公开数据补充"""
    target_slide_count = Column(Integer, default=0)
    current_slide_count = Column(Integer, default=0)
    partner_name = Column(String(200), default="")
    agreement_signed = Column(Boolean, default=False)
    ethics_required = Column(Boolean, default=True)
    owner_name = Column(String(80), default="")
    deadline = Column(String(32), default="")
    status = Column(String(32), default="planning")
    """planning / in_progress / done / blocked"""
    note = Column(String(512), default="")
