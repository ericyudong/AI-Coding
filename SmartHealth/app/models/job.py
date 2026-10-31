"""异步作业实体：统一作业队列、执行记录与执行日志。

设计动机（商用必需）：
训练、推理、特征预计算、评测、联邦聚合这类任务的耗时在数十秒到数小时量级。
把它们放在 HTTP 请求里同步执行，必然导致：请求超时、无进度、无法取消、
进程重启即丢失、无法重试、无法限流 —— 这是演示系统与生产系统的分水岭。

本模块提供统一的作业账本：
- AsyncJob       —— 作业主表（队列 + 执行状态 + 进度 + 结果 + 错误）
- AsyncJobEvent  —— 作业事件流（入队/开始/进度里程碑/取消/重试/结束），可审计回放

作业的**业务细节**仍保留在各业务表（TrainingJob / InferenceJob / FederatedJob），
本表只负责「调度、进度、生命周期」，通过 ref_type + ref_id 关联。
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, ForeignKey, Index, Integer, String, Text

from app.models.base import BaseModel

# ---------------------------------------------------------------- 作业类型
JOB_TYPES: dict[str, str] = {
    "feature_precompute": "切片特征预计算",
    "train": "模型训练（Stage B/C）",
    "inference": "批量推理",
    "evaluate": "评测运行",
    "mrmc": "MRMC 人工对照",
    "federated": "联邦式增量微调",
    "import_slides": "切片批量导入",
    "qc_recompute": "标注一致性与质控重算",
    "explainability": "可解释性材料重建",
    "boundary_check": "数据不出域校验",
}

# ---------------------------------------------------------------- 作业状态
JOB_STATUSES: dict[str, str] = {
    "queued": "排队中",
    "running": "执行中",
    "succeeded": "已成功",
    "failed": "已失败",
    "cancelled": "已取消",
    "timeout": "已超时",
    "dead": "已耗尽重试",
}

# 终态：不再被调度
TERMINAL_STATUSES = ("succeeded", "failed", "cancelled", "timeout", "dead")


class AsyncJob(BaseModel):
    """统一异步作业。"""

    __tablename__ = "sys_async_job"
    __table_args__ = (
        Index("ix_async_job_status_priority", "status", "priority", "id"),
        Index("ix_async_job_dedup", "dedup_key", "status"),
    )

    code = Column(String(64), unique=True, index=True, nullable=False)
    job_type = Column(String(32), index=True, nullable=False)
    title = Column(String(240), default="")

    status = Column(String(16), index=True, default="queued")
    priority = Column(Integer, default=50)
    """数值越小越优先。交互式单例（0—30） > 批量（40—60） > 后台回归（70—99）。"""

    progress = Column(Float, default=0.0)
    stage_text = Column(String(240), default="")
    """当前阶段的人类可读描述，前端进度条下方直接显示。"""

    payload_json = Column(Text, default="{}")
    result_json = Column(Text, default="{}")
    error_text = Column(Text, default="")
    error_detail = Column(Text, default="")
    """错误堆栈（仅管理员可见，用于排障）。"""

    ref_type = Column(String(48), default="")
    """关联的业务实体类型，如 training_job / inference_job / federated_job / slide"""
    ref_id = Column(Integer, nullable=True)
    ref_label = Column(String(240), default="")

    dedup_key = Column(String(200), default="", index=True)
    """幂等键。同一 dedup_key 存在未终态作业时，重复提交直接返回已有作业。"""

    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=2)
    timeout_sec = Column(Integer, default=0)
    """0 表示不超时（训练类任务按需显式设置）。"""

    cancel_requested = Column(Boolean, default=False)
    """取消是请求式的：Worker 在安全检查点响应，避免落库到一半被硬杀。"""

    worker_id = Column(String(64), default="")
    heartbeat_at = Column(String(32), default="")
    queued_at = Column(String(32), default="")
    started_at = Column(String(32), default="")
    finished_at = Column(String(32), default="")
    duration_sec = Column(Float, default=0.0)

    created_by = Column(String(80), default="")
    created_by_name = Column(String(80), default="")
    org_code = Column(String(64), index=True, default="")
    """归属机构。院内私有化下用于数据隔离；联邦类作业为空（跨机构）。"""
    site_code = Column(String(32), index=True, default="")

    note = Column(String(512), default="")

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def type_label(self) -> str:
        return JOB_TYPES.get(self.job_type, self.job_type)

    @property
    def status_label(self) -> str:
        return JOB_STATUSES.get(self.status, self.status)


class AsyncJobEvent(BaseModel):
    """作业事件流。用于审计回放与「这个任务到底发生了什么」的排障。"""

    __tablename__ = "sys_async_job_event"

    job_id = Column(Integer, ForeignKey("sys_async_job.id", ondelete="CASCADE"),
                    index=True, nullable=False)
    seq = Column(Integer, default=1)
    event = Column(String(32), default="info")
    """queued / started / progress / log / cancel_requested / cancelled / retry / finished / error"""
    message = Column(String(500), default="")
    progress = Column(Float, default=0.0)
    actor = Column(String(80), default="")
    at = Column(String(32), default="")
