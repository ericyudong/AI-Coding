"""模型实体：图块编码器注册表、基座模型、模型版本、训练任务、适配器、算力台账。

设计文档依据：第四章「蓝天健康模型技术方案」+ 第六章「技术栈、算力与部署架构」。

本模块承载方案最关键的两条约束：
1. **许可风险（R2）**：EncoderRegistry.commercial_usable 与 research_only 是硬字段，
   配合 settings.deployment_env 在服务层做门禁，保证 product 环境绝不会误用非商用权重。
2. **双源并行**：同一能力位并存「可商许可路线」与「自研编码器路线」两条记录，
   ModelBase.default_encoder_code 与 fallback_encoder_code 分别指向它们。
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class EncoderRegistry(BaseModel):
    """图块编码器注册表（含许可证元数据）。"""

    __tablename__ = "model_encoder"

    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(160), nullable=False)
    family = Column(String(64), default="")
    """UNI / Virchow / Hibou / Prov-GigaPath / CONCH / 自研"""
    arch = Column(String(64), default="ViT-L/16")
    params_m = Column(Float, default=0.0)
    embedding_dim = Column(Integer, default=1024)
    tile_size = Column(Integer, default=256)
    target_mpp = Column(Float, default=0.5)
    pretrain_scale = Column(String(160), default="")
    """预训练数据规模描述，如「10 万张 WSI / 1 亿图块」"""

    # ---- 许可证（R2 许可风险的判定依据）----
    license_code = Column(String(64), default="")
    license_name = Column(String(160), default="")
    commercial_usable = Column(Boolean, default=False)
    research_only = Column(Boolean, default=True)
    license_note = Column(String(512), default="")
    source_url = Column(String(320), default="")

    # ---- 运行形态 ----
    impl = Column(String(32), default="synthetic")
    """synthetic=内置确定性合成编码器 / onnx=ONNX 推理 / torch=PyTorch 权重 / remote=远端服务"""
    weight_path = Column(String(512), default="")
    onnx_path = Column(String(512), default="")
    onnx_sha256 = Column(String(64), default="")
    """ONNX 权重文件的 SHA256。让「库里这条记录」能对上「磁盘上那份文件」。"""
    input_norm = Column(String(32), default="reinhard")
    input_norm_onnx = Column(String(32), default="")
    """ONNX 预处理归一化预设：imagenet / half / unit / none。"""
    input_layout = Column(String(16), default="")
    """输入布局 NCHW / NHWC；留空表示从计算图推断。"""
    resize_mode = Column(String(16), default="")
    """图块缩放到模型输入尺寸时的插值方式。"""
    batch_size = Column(Integer, default=0)
    """推理批大小；0 表示按后端默认。"""
    weight_url = Column(String(512), default="")
    """权重下载地址（清单登记用；院内离线环境通常为空）。"""
    is_self_developed = Column(Boolean, default=False)

    status = Column(String(32), default="enabled")
    """enabled / disabled / deprecated"""
    benchmark_auroc = Column(Float, default=0.0)
    benchmark_note = Column(String(320), default="")
    sort_order = Column(Integer, default=0)


class ModelBase(BaseModel):
    """蓝天健康病理垂类模型基座定义。"""

    __tablename__ = "model_base"

    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    organ_scope = Column(String(200), default="")
    cancer_types_json = Column(Text, default="[]")
    task_scope_json = Column(Text, default="[]")
    """覆盖的辅助诊断任务清单"""

    default_encoder_code = Column(String(64), default="")
    """可商许可路线编码器（商用主线默认）。"""
    fallback_encoder_code = Column(String(64), default="")
    """自研编码器路线（6—18 个月内替换的目标）。"""

    mil_arch = Column(String(64), default="ABMIL-Gated")
    track = Column(String(16), default="commercial")
    """commercial=商用主线（图块级+切片级聚合）/ exploration=探索线（多模态 Agent）"""
    current_stage = Column(String(16), default="Stage A")
    """Stage A 特征预计算 / B 域自适应继续预训练 / C 监督微调与聚合 / D 多模态对齐"""
    description = Column(Text, default="")
    owner_name = Column(String(80), default="")
    status = Column(String(32), default="active")

    versions = relationship("ModelVersion", back_populates="base", lazy="selectin")


class ModelVersion(BaseModel):
    """模型版本。locked 版本是注册申报的基线，禁止就地修改（对应变更注册要求）。"""

    __tablename__ = "model_version"

    base_id = Column(Integer, ForeignKey("model_base.id", ondelete="CASCADE"), index=True, nullable=False)
    semver = Column(String(32), nullable=False)
    name = Column(String(200), default="")
    encoder_code = Column(String(64), index=True, default="")
    mil_config_json = Column(Text, default="{}")
    training_job_id = Column(Integer, ForeignKey("model_training_job.id", ondelete="SET NULL"), nullable=True)
    metrics_json = Column(Text, default="{}")
    """核心指标快照：AUROC / 敏感度 / 特异度 / ECE / 外部验证结果"""
    artifact_path = Column(String(512), default="")
    param_count = Column(Integer, default=0)
    locked = Column(Boolean, default=False)
    is_registration_candidate = Column(Boolean, default=False)
    released_at = Column(String(32), default="")
    changelog = Column(Text, default="")
    status = Column(String(32), default="draft")
    """draft / validated / locked / deprecated"""

    base = relationship("ModelBase", back_populates="versions", lazy="selectin")


class TrainingJob(BaseModel):
    """训练 / 特征预计算任务。"""

    __tablename__ = "model_training_job"

    code = Column(String(64), unique=True, index=True, nullable=False)
    job_type = Column(String(32), nullable=False)
    """feature_pretrain=特征预计算 / domain_adapt=域自适应继续预训练 /
       supervised_finetune=监督微调 / mil_aggregate=切片级聚合训练 /
       encoder_selfsup=自研编码器自监督预训练 / eval_only=仅评测"""
    stage = Column(String(16), default="Stage A")
    base_id = Column(Integer, ForeignKey("model_base.id", ondelete="SET NULL"), nullable=True)
    encoder_code = Column(String(64), index=True, default="")
    dataset_ids_json = Column(Text, default="[]")
    params_json = Column(Text, default="{}")
    license_env = Column(String(16), default="research")
    """任务运行环境的许可证约束：research 允许非商用权重，product 不允许。"""

    train_slide_count = Column(Integer, default=0)
    val_slide_count = Column(Integer, default=0)

    status = Column(String(32), default="pending")
    """pending / running / succeeded / failed / cancelled"""
    progress = Column(Float, default=0.0)
    started_at = Column(String(32), default="")
    finished_at = Column(String(32), default="")
    duration_sec = Column(Integer, default=0)
    gpu_hours = Column(Float, default=0.0)
    cost_estimate = Column(Float, default=0.0)
    """按租用单价估算的成本（元），对应设计文档 6.2「以租用为主」。"""

    output_version_id = Column(Integer, nullable=True)
    metrics_json = Column(Text, default="{}")
    log_tail = Column(Text, default="")
    triggered_by = Column(String(80), default="")


class LoraAdapter(BaseModel):
    """LoRA 适配器（自有数据监督微调产物）。"""

    __tablename__ = "model_lora_adapter"

    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(160), default="")
    target_encoder_code = Column(String(64), index=True, default="")
    rank = Column(Integer, default=16)
    alpha = Column(Integer, default=32)
    dropout = Column(Float, default=0.05)
    target_modules = Column(String(320), default="qkv,proj")
    trainable_params = Column(Integer, default=0)
    total_params = Column(Integer, default=0)
    path = Column(String(512), default="")
    training_job_id = Column(Integer, ForeignKey("model_training_job.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(32), default="active")
    note = Column(String(512), default="")


class ComputeResource(BaseModel):
    """算力资源台账（租用 / 自建）。"""

    __tablename__ = "model_compute_resource"

    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(160), nullable=False)
    resource_type = Column(String(16), default="rented")
    """rented=租用 / self_built=自建 / edge=边缘节点"""
    gpu_model = Column(String(80), default="")
    gpu_count = Column(Integer, default=0)
    gpu_memory_gb = Column(Integer, default=0)
    cpu_cores = Column(Integer, default=0)
    memory_gb = Column(Integer, default=0)
    storage_tb = Column(Float, default=0.0)
    vendor = Column(String(120), default="")
    location = Column(String(120), default="")
    hourly_cost = Column(Float, default=0.0)
    utilization = Column(Float, default=0.0)
    is_gateway = Column(Boolean, default=False)
    """是否为国产化算力（信创要求相关）"""
    status = Column(String(32), default="available")
    """available / busy / maintenance / offline"""
