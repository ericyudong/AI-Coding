"""全局配置。

设计文档依据：第六章「技术栈、算力与部署架构」+ 第七章「合规与注册路径」。
- `deployment_env` 是实现「双源并行」策略的关键开关：product 环境下非商用许可证编码器
  会被硬门禁拦截（见 services/encoder_service.py::assert_commercial_usable）。
- 数据目录按「数据不出域」原则默认落在院内本地磁盘，预览/缓存均不落对象存储。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SMARTHEALTH_",
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------ 基础
    app_name: str = "蓝天健康病理垂类多模态大模型与智慧医疗 Agent 平台"
    app_short_name: str = "SmartHealth"
    version: str = "1.0.0"
    debug: bool = True
    api_prefix: str = "/api/v1"

    # ------------------------------------------------------------------ 存储
    data_dir: Path = Field(default=BASE_DIR / "data")
    """院内本地数据根目录（数据不出域）。"""

    @property
    def wsi_dir(self) -> Path:
        return self.data_dir / "wsi"

    @property
    def tile_cache_dir(self) -> Path:
        return self.data_dir / "tile_cache"

    @property
    def feature_dir(self) -> Path:
        return self.data_dir / "features"

    @property
    def artifact_dir(self) -> Path:
        return self.data_dir / "artifacts"

    # ------------------------------------------------------------------ 数据库
    database_url: str = Field(default=f"sqlite:///{(BASE_DIR / 'data' / 'smarthealth.db').as_posix()}")
    """数据库连接串。

    开发/单机演示用 SQLite（零依赖）；院内生产建议 PostgreSQL：
        SMARTHEALTH_DATABASE_URL=postgresql+psycopg://user:pwd@host:5432/smarthealth
    SQLite 是**单写者**数据库，作业并发一高就会排队等写锁 —— 它是这个系统的规模天花板。
    """

    @property
    def db_backend(self) -> str:
        """'postgresql' | 'sqlite' | 'unknown'。用于决定连接池参数与专有 SQL。"""
        url = (self.database_url or "").lower()
        if url.startswith("postgresql") or url.startswith("postgres"):
            return "postgresql"
        if url.startswith("sqlite"):
            return "sqlite"
        return "unknown"

    @property
    def is_sqlite(self) -> bool:
        return self.db_backend == "sqlite"

    # 连接池（仅 PostgreSQL 等真实数据库生效；SQLite 用默认即可）
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    db_statement_timeout_ms: int = 0
    """单条 SQL 最长执行时间（毫秒）。0 表示不限制。
    作业与 API 共库时建议设 30000—120000，避免一条慢查询把连接池占满。"""

    # ------------------------------------------------------------------ 分布式协调
    redis_url: str = ""
    """Redis 连接串，如 redis://127.0.0.1:6379/0。
    配置后：分布式锁与事件推送走 Redis（跨进程/跨实例）。
    未配置：退化为数据库锁 + 数据库轮询，功能可用但效率较低。"""
    lock_lease_seconds: int = 120
    """分布式锁租约。持有者需在租约内续期，否则视为失效（防止进程崩溃后死锁）。"""

    # ------------------------------------------------------------------ 认证
    secret_key: str = "smarthealth-dev-secret-change-me-in-hospital-deployment"
    jwt_algorithm: str = "HS256"
    admin_username: str = "admin"
    admin_password: str = "admin123"

    # -------------------------------------------------------- 部署环境与许可证
    deployment_env: Literal["research", "product"] = "research"
    """research=科研/探索线环境（允许非商用许可权重）；product=商用产品环境（仅允许可商用权重）。"""

    strict_license_gate: bool = True
    """开启后，product 环境调用非商用编码器将直接抛 LicenseViolation。"""

    # ------------------------------------------------------------------ 模型
    default_encoder: str = "hibou-b-synth"
    """默认图块编码器（可商用路线）。"""

    default_mil_hidden: int = 256
    default_mil_attention: int = 64
    default_tile_size: int = 256
    default_tile_mpp: float = 0.5
    """图块物理分辨率（微米/像素），用于倍率换算：mpp 0.25≈40X，0.5≈20X，1.0≈10X，2.0≈5X。"""

    # ------------------------------------------------------------------ Agent
    agent_max_regions: int = 48
    """单张切片默认探查区域上限（对标 SlideSeek 平均探查 47 个区域）。"""

    agent_navigation_trajectories: int = 3
    """诊断智能体的多轨迹投票条数。"""

    agent_confidence_threshold: float = 0.62
    """校准后置信度（max(p, 1-p)）低于此值触发拒识并转人工复核。

    0.62 对应「校准概率落在 0.38—0.62 之间即拒识」。该阈值是可用性与安全性的
    平衡点：调高会大量无谓拒识，调低则失去安全兜底意义。
    """

    agent_min_evidence: int = 3
    """最少证据条数，不足则拒识。"""

    agent_top_k_similar_cases: int = 5
    """描述智能体的相似病例检索条数。"""

    # ------------------------------------------------------------------ 合规
    audit_chain_enabled: bool = True
    reject_requires_manual_review: bool = True

    # ------------------------------------------------------------------ 作业引擎
    job_workers: int = 2
    """异步作业 Worker 数量。训练类任务与 API 共享进程，2—4 个是合理区间。"""
    job_async_default: bool = True
    """业务接口默认异步化：True=提交作业立即返回（202），False=请求内同步执行。
    生产环境必须为 True；仅在自动化测试或极小规模离线场景才关闭。"""
    job_heartbeat_stale_sec: int = 180
    """心跳超过该秒数即判定 Worker 失联并回收作业。"""

    workers_in_api: bool = True
    """API 进程内是否运行作业 Worker。

    单进程部署（演示/小院内）：True，够用且简单。
    多进程部署（uvicorn --workers N 或独立 Worker 进程）：**必须 False**，
    否则每个 API 进程都会带一份 Worker，并发度不可控、心跳互相干扰。
    """
    worker_concurrency: int = 4
    """独立 Worker 进程内的并发作业数。"""
    worker_drain_seconds: int = 20
    """Worker 收到停止信号后等待在跑作业退出的秒数。"""

    # ------------------------------------------------------------------ 调度与限流
    scheduler_enabled: bool = True
    """周期任务开关（边缘心跳、队列告警、令牌清理、KPI 快照）。"""
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 600
    """单用户每分钟请求上限。院内单科室并发很低，600 足够宽松又足以挡住脚本刷接口。"""
    rate_limit_login_per_minute: int = 20
    login_max_failures: int = 5
    """连续失败次数达到该值即锁定账号。"""
    login_lock_minutes: int = 15
    password_min_length: int = 8
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14
    audit_request_logging: bool = True
    """是否记录结构化访问日志与 trace id。"""

    # ------------------------------------------------------------------ 服务
    backend_host: str = "127.0.0.1"
    backend_port: int = 8100
    frontend_port: int = 8101
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.wsi_dir, self.tile_cache_dir, self.feature_dir, self.artifact_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings


settings = get_settings()
