"""云边协同与联邦式增量微调实体。

设计文档依据：第六章「技术栈、算力与部署架构」+ 第十章 R3（跨中心泛化衰减应对）。

- EdgeNode            —— 边缘节点（院内私有化 / 基层端侧）
- FederatedJob        —— 联邦式增量微调任务（数据不出域，只出梯度）
- FederatedRound      —— 每轮全局聚合结果
- FederatedParticipant—— 参与方记录（含「样本未离开机构」声明）
- DeploymentTask      —— 模型下发与回滚任务
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class EdgeNode(BaseModel):
    """边缘节点。院内私有化部署点或基层端侧推理节点。"""

    __tablename__ = "edge_node"

    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    hospital = Column(String(200), default="")
    site_code = Column(String(32), index=True, default="")
    """所属数据中心编号。与 asset_slide.site_code 对应，用于联邦学习划分本地数据。"""
    node_type = Column(String(24), default="edge_server")
    """pc=PC 端 / edge_server=边缘服务器 / gateway=基层一体机 / cloud=中心云"""
    region = Column(String(120), default="")
    cpu_cores = Column(Integer, default=0)
    memory_gb = Column(Integer, default=0)
    gpu_model = Column(String(80), default="")
    gpu_count = Column(Integer, default=0)
    storage_tb = Column(Float, default=0.0)

    deployment_mode = Column(String(24), default="local")
    """local=完全本地 / edge_cloud=云边协同 / cloud=云端"""
    model_version_id = Column(Integer, ForeignKey("model_version.id", ondelete="SET NULL"), nullable=True)
    model_version_label = Column(String(120), default="")
    edge_runtime = Column(String(64), default="")
    """端侧运行时，如 ONNX Runtime CPU（轻量化 Edge 版本）"""
    realtime_inference = Column(Boolean, default=False)
    """是否支持 PC 端实时推理（设计文档：轻量 Edge 版本支持端云协同、分钟级部署）"""

    local_slide_count = Column(Integer, default=0)
    daily_case_capacity = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    uptime_rate = Column(Float, default=0.0)

    status = Column(String(24), default="online")
    """online / offline / degraded / maintenance"""
    last_heartbeat = Column(String(32), default="")
    deploy_minutes = Column(Integer, default=0)
    """分钟级部署耗时实测。"""
    note = Column(String(512), default="")


class FederatedJob(BaseModel):
    """联邦式增量微调：模型参数/梯度出域，样本数据不出域。"""

    __tablename__ = "edge_federated_job"

    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    base_version_id = Column(Integer, ForeignKey("model_version.id", ondelete="SET NULL"), nullable=True)
    base_version_label = Column(String(120), default="")
    strategy = Column(String(24), default="fedavg")
    """fedavg / fedprox"""
    target_rounds = Column(Integer, default=10)
    min_clients = Column(Integer, default=2)
    local_epochs = Column(Integer, default=1)
    learning_rate = Column(Float, default=0.001)
    current_round = Column(Integer, default=0)
    global_metric_init = Column(Float, default=0.0)
    global_metric_final = Column(Float, default=0.0)
    metric_key = Column(String(32), default="auroc")
    target_metric = Column(Float, default=0.0)
    upload_bytes_total = Column(BigInteger, default=0)
    """累计上传字节数（多轮联邦任务累计可达 TB 级），用于证明「只出梯度不出数据」。"""
    sample_total = Column(Integer, default=0)
    status = Column(String(24), default="pending")
    """pending / running / succeeded / failed / cancelled"""
    started_at = Column(String(32), default="")
    finished_at = Column(String(32), default="")
    output_version_id = Column(Integer, nullable=True)
    note = Column(String(512), default="")

    rounds = relationship("FederatedRound", back_populates="job", cascade="all, delete-orphan", lazy="selectin")


class FederatedRound(BaseModel):
    __tablename__ = "edge_federated_round"

    job_id = Column(Integer, ForeignKey("edge_federated_job.id", ondelete="CASCADE"), index=True, nullable=False)
    round_no = Column(Integer, default=1)
    client_count = Column(Integer, default=0)
    global_loss = Column(Float, default=0.0)
    global_metric = Column(Float, default=0.0)
    upload_kb = Column(Integer, default=0)
    download_kb = Column(Integer, default=0)
    elapsed_sec = Column(Integer, default=0)
    weights_path = Column(String(512), default="")
    participants_json = Column(Text, default="[]")
    """[{node_code, hospital, sample_count, local_loss, local_metric, data_left_domain:false}]"""
    aggregated_at = Column(String(32), default="")

    job = relationship("FederatedJob", back_populates="rounds", lazy="selectin")


class DeploymentTask(BaseModel):
    """模型下发 / 更新 / 回滚任务。"""

    __tablename__ = "edge_deployment_task"

    code = Column(String(64), unique=True, index=True, nullable=False)
    node_id = Column(Integer, ForeignKey("edge_node.id", ondelete="CASCADE"), index=True, nullable=False)
    node_code = Column(String(64), default="")
    model_version_id = Column(Integer, ForeignKey("model_version.id", ondelete="SET NULL"), nullable=True)
    model_version_label = Column(String(120), default="")
    action = Column(String(24), default="install")
    """install / update / rollback"""
    package_path = Column(String(512), default="")
    package_size_mb = Column(Float, default=0.0)
    checksum = Column(String(64), default="")
    status = Column(String(24), default="pending")
    """pending / running / succeeded / failed / rolled_back"""
    elapsed_sec = Column(Integer, default=0)
    started_at = Column(String(32), default="")
    finished_at = Column(String(32), default="")
    log_tail = Column(Text, default="")
    triggered_by = Column(String(80), default="")
