"""版本化数据库迁移。

为什么不用 Alembic：
本项目的迁移需求是「加列 / 加表 / 加索引 / 回填」，没有复杂的模型重写。
引入 Alembic 会增加一套 autogenerate 工作流与版本目录，反而让「现场运维在
一个没有源码仓库的院内环境里升级」变难。这里实现一个**自包含、可审计**的迁移器：

- 迁移记录落在 `sys_schema_version`，每行一个版本 + 校验和 + 执行者 + 耗时。
- 每条迁移是纯 Python 函数，接收 `conn`，**必须幂等**（重跑不出错）。
- 迁移前抢**分布式锁**：多进程同时启动时只有一个执行迁移，其余等待。
- 对「已有表但还没有版本表」的老库自动打**基线**，避免把已有结构重放一遍。

关键约定（这三条决定了迁移器能不能上生产）：
1. **幂等**：迁移体必须先 `has_column/has_table` 判断再改。重复执行是常态
   （服务重启、蓝绿切换、回滚后重放），不幂等就意味着一次重启炸一次。
2. **方言感知**：SQLite 与 PostgreSQL 的 DDL 有细微差别（列类型、IF NOT EXISTS、
   索引并发创建）。统一用 `dialect_*` 辅助函数出 SQL，不在迁移体里手写方言判断。
3. **失败即中止且可诊断**：任一迁移失败时事务回滚、记录 error、抛出，
   由调用方决定是否阻止服务启动（本项目的策略是：**拒绝启动**，
   带着未知的库结构对外提供服务比启动失败危险得多）。
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.core.config import settings

logger = logging.getLogger(__name__)

VERSION_TABLE = "sys_schema_version"

_DDL_VERSION_SQLITE = f"""
CREATE TABLE IF NOT EXISTS {VERSION_TABLE} (
    version     INTEGER PRIMARY KEY,
    name        VARCHAR(160) NOT NULL,
    checksum    VARCHAR(64)  NOT NULL DEFAULT '',
    applied_at  VARCHAR(32)  NOT NULL DEFAULT '',
    applied_by  VARCHAR(120) NOT NULL DEFAULT '',
    duration_ms INTEGER      NOT NULL DEFAULT 0,
    dialect     VARCHAR(24)  NOT NULL DEFAULT '',
    note        VARCHAR(300) NOT NULL DEFAULT ''
)
"""

_DDL_VERSION_PG = f"""
CREATE TABLE IF NOT EXISTS {VERSION_TABLE} (
    version     INTEGER PRIMARY KEY,
    name        VARCHAR(160) NOT NULL,
    checksum    VARCHAR(64)  NOT NULL DEFAULT '',
    applied_at  VARCHAR(32)  NOT NULL DEFAULT '',
    applied_by  VARCHAR(120) NOT NULL DEFAULT '',
    duration_ms INTEGER      NOT NULL DEFAULT 0,
    dialect     VARCHAR(24)  NOT NULL DEFAULT '',
    note        VARCHAR(300) NOT NULL DEFAULT ''
)
"""


# ================================================================= 方言辅助
def is_pg(engine: Engine) -> bool:
    return engine.dialect.name == "postgresql"


def has_table(engine: Engine, name: str) -> bool:
    return name in set(inspect(engine).get_table_names())


def columns_of(engine: Engine, table: str) -> set[str]:
    try:
        return {c["name"] for c in inspect(engine).get_columns(table)}
    except Exception:
        return set()


def indexes_of(engine: Engine, table: str) -> set[str]:
    try:
        return {i["name"] for i in inspect(engine).get_indexes(table)}
    except Exception:
        return set()


def add_column(conn, engine: Engine, table: str, column: str, ddl_type: str,
               default: Any = None, *, not_null: bool = False) -> bool:
    """幂等加列。已存在返回 False。"""
    if table not in set(inspect(conn).get_table_names()):
        return False
    if column in columns_of(conn, table):
        return False
    sql = f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"
    if default is not None:
        if isinstance(default, bool):
            sql += f" DEFAULT {1 if default else 0}"
        elif isinstance(default, (int, float)):
            sql += f" DEFAULT {default}"
        else:
            escaped = str(default).replace("'", "''")
            sql += f" DEFAULT '{escaped}'"
    conn.execute(text(sql))
    if not_null and default is not None:
        conn.execute(text(f"UPDATE {table} SET {column} = " + (
            f"{1 if default is True else 0 if default is False else default}"
            if isinstance(default, (int, float, bool)) else f"'{str(default).replace(chr(39), chr(39) * 2)}'"
        ) + f" WHERE {column} IS NULL"))
    return True


def create_index(conn, engine: Engine, table: str, name: str, columns: str) -> bool:
    """幂等建索引。PG 用 IF NOT EXISTS，SQLite 也支持。"""
    if table not in set(inspect(conn).get_table_names()):
        return False
    if name in indexes_of(conn, table):
        return False
    conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})"))
    return True


def backfill(conn, table: str, column: str, value: str) -> int:
    """把 NULL/空串回填为给定值，返回影响行数。"""
    if table not in set(inspect(conn).get_table_names()):
        return 0
    if column not in columns_of(conn, table):
        return 0
    result = conn.execute(text(
        f"UPDATE {table} SET {column} = :v WHERE {column} IS NULL OR {column} = ''"
    ), {"v": value})
    return int(result.rowcount or 0)


# ================================================================= 迁移定义
@dataclass
class Migration:
    version: int
    name: str
    fn: Callable[[Any, Engine], str]
    note: str = ""

    @property
    def checksum(self) -> str:
        """基于函数源码算校验和：同版本改了实现会被发现。"""
        try:
            import inspect as _inspect

            src = _inspect.getsource(self.fn)
        except Exception:
            src = self.name
        return hashlib.sha256((self.name + src).encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- 0001 基线
def m0001_baseline(conn, engine: Engine) -> str:
    """基线：把「迁移器引入之前就已存在的表」登记为版本 1。

    这一步不做任何结构变更 —— 它的唯一作用是让后续迁移知道"起点在哪"。
    对全新的空库，`create_all` 已建好全部表，这里同样只登记。
    """
    tables = sorted(inspect(conn).get_table_names())
    return f"基线登记，已存在 {len(tables)} 张表"


# ---------------------------------------------------------------- 0002 切片溯源与机构
def m0002_slide_provenance(conn, engine: Engine) -> str:
    """切片表补齐：文件指纹、原始文件名、上传人、机构归属。

    对应需求：上传去重（checksum）、科室按原始文件名对账（source_filename）、
    行级数据隔离（org_code）、操作追溯（uploaded_by）。
    """
    if not has_table(conn, "asset_slide"):
        return "asset_slide 不存在，跳过"
    changed = []
    for col, typ, dft in (
        ("checksum", "VARCHAR(64)", ""),
        ("source_filename", "VARCHAR(256)", ""),
        ("uploaded_by", "VARCHAR(80)", ""),
        ("org_code", "VARCHAR(64)", ""),
    ):
        if add_column(conn, engine, "asset_slide", col, typ, dft):
            changed.append(col)
    create_index(conn, engine, "asset_slide", "ix_asset_slide_checksum", "checksum")
    create_index(conn, engine, "asset_slide", "ix_asset_slide_org_code", "org_code")
    return f"新增列 {changed or '无（已是最新）'}"


# ---------------------------------------------------------------- 0003 资产机构
def m0003_asset_scope(conn, engine: Engine) -> str:
    """数据资产补齐机构归属与涉及中心。"""
    if not has_table(conn, "asset_dataset"):
        return "asset_dataset 不存在，跳过"
    changed = []
    for col, typ, dft in (("org_code", "VARCHAR(64)", ""), ("site_codes", "VARCHAR(400)", "")):
        if add_column(conn, engine, "asset_dataset", col, typ, dft):
            changed.append(col)
    create_index(conn, engine, "asset_dataset", "ix_asset_dataset_org_code", "org_code")
    return f"新增列 {changed or '无（已是最新）'}"


# ---------------------------------------------------------------- 0004 用户机构与安全
def m0004_user_scope_and_security(conn, engine: Engine) -> str:
    """用户表补齐数据范围与登录安全字段。"""
    if not has_table(conn, "sys_user"):
        return "sys_user 不存在，跳过"
    changed = []
    for col, typ, dft in (
        ("org_code", "VARCHAR(64)", ""),
        ("site_code", "VARCHAR(32)", ""),
        ("data_scope", "VARCHAR(16)", "all"),
        ("must_change_password", "BOOLEAN", False),
        ("failed_login_count", "INTEGER", 0),
        ("locked_until", "VARCHAR(32)", ""),
    ):
        if add_column(conn, engine, "sys_user", col, typ, dft):
            changed.append(col)
    create_index(conn, engine, "sys_user", "ix_sys_user_org_code", "org_code")
    create_index(conn, engine, "sys_user", "ix_sys_user_site_code", "site_code")
    return f"新增列 {changed or '无（已是最新）'}"


# ---------------------------------------------------------------- 0005 刷新会话与登录尝试
_DDL_REFRESH_SQLITE = """
CREATE TABLE IF NOT EXISTS sys_refresh_session (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    token_hash    VARCHAR(128) NOT NULL UNIQUE,
    issued_at     VARCHAR(32) DEFAULT '',
    expires_at    VARCHAR(32) DEFAULT '',
    rotated_from  VARCHAR(128) DEFAULT '',
    revoked_at    VARCHAR(32) DEFAULT '',
    revoke_reason VARCHAR(120) DEFAULT '',
    device        VARCHAR(200) DEFAULT '',
    client_ip     VARCHAR(64) DEFAULT '',
    last_used_at  VARCHAR(32) DEFAULT '',
    use_count     INTEGER DEFAULT 0,
    created_at    VARCHAR(32) DEFAULT '',
    updated_at    VARCHAR(32) DEFAULT ''
)
"""

_DDL_REFRESH_PG = """
CREATE TABLE IF NOT EXISTS sys_refresh_session (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES sys_user(id) ON DELETE CASCADE,
    token_hash    VARCHAR(128) NOT NULL UNIQUE,
    issued_at     VARCHAR(32) DEFAULT '',
    expires_at    VARCHAR(32) DEFAULT '',
    rotated_from  VARCHAR(128) DEFAULT '',
    revoked_at    VARCHAR(32) DEFAULT '',
    revoke_reason VARCHAR(120) DEFAULT '',
    device        VARCHAR(200) DEFAULT '',
    client_ip     VARCHAR(64) DEFAULT '',
    last_used_at  VARCHAR(32) DEFAULT '',
    use_count     INTEGER DEFAULT 0,
    created_at    VARCHAR(32) DEFAULT '',
    updated_at    VARCHAR(32) DEFAULT ''
)
"""

_DDL_ATTEMPT_SQLITE = """
CREATE TABLE IF NOT EXISTS sys_login_attempt (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   VARCHAR(64) DEFAULT '',
    client_ip  VARCHAR(64) DEFAULT '',
    success    BOOLEAN DEFAULT 0,
    reason     VARCHAR(120) DEFAULT '',
    at         VARCHAR(32) DEFAULT '',
    created_at VARCHAR(32) DEFAULT '',
    updated_at VARCHAR(32) DEFAULT ''
)
"""

_DDL_ATTEMPT_PG = """
CREATE TABLE IF NOT EXISTS sys_login_attempt (
    id         SERIAL PRIMARY KEY,
    username   VARCHAR(64) DEFAULT '',
    client_ip  VARCHAR(64) DEFAULT '',
    success    BOOLEAN DEFAULT FALSE,
    reason     VARCHAR(120) DEFAULT '',
    at         VARCHAR(32) DEFAULT '',
    created_at VARCHAR(32) DEFAULT '',
    updated_at VARCHAR(32) DEFAULT ''
)
"""


def m0005_auth_sessions(conn, engine: Engine) -> str:
    """刷新令牌会话与登录尝试记录（对应商用安全基线）。"""
    made = []
    if not has_table(conn, "sys_refresh_session"):
        conn.execute(text(_DDL_REFRESH_PG if is_pg(engine) else _DDL_REFRESH_SQLITE))
        made.append("sys_refresh_session")
    if not has_table(conn, "sys_login_attempt"):
        conn.execute(text(_DDL_ATTEMPT_PG if is_pg(engine) else _DDL_ATTEMPT_SQLITE))
        made.append("sys_login_attempt")
    create_index(conn, engine, "sys_refresh_session", "ix_refresh_user", "user_id")
    create_index(conn, engine, "sys_login_attempt", "ix_attempt_username", "username")
    create_index(conn, engine, "sys_login_attempt", "ix_attempt_ip", "client_ip")
    return f"新建表 {made or '无（已存在）'}"


# ---------------------------------------------------------------- 0006 异步作业
_DDL_JOB_SQLITE = """
CREATE TABLE IF NOT EXISTS sys_async_job (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    code             VARCHAR(48) NOT NULL UNIQUE,
    job_type         VARCHAR(48) NOT NULL,
    title            VARCHAR(200) DEFAULT '',
    status           VARCHAR(16) DEFAULT 'queued',
    priority         INTEGER DEFAULT 50,
    progress         FLOAT DEFAULT 0.0,
    stage_text       VARCHAR(300) DEFAULT '',
    payload_json     TEXT DEFAULT '{}',
    result_json      TEXT DEFAULT '',
    error_text       VARCHAR(800) DEFAULT '',
    error_detail     TEXT DEFAULT '',
    dedup_key        VARCHAR(200) DEFAULT '',
    ref_type         VARCHAR(32) DEFAULT '',
    ref_id           INTEGER,
    ref_label        VARCHAR(120) DEFAULT '',
    created_by       VARCHAR(80) DEFAULT '',
    created_by_name  VARCHAR(80) DEFAULT '',
    org_code         VARCHAR(64) DEFAULT '',
    site_code        VARCHAR(32) DEFAULT '',
    worker_id        VARCHAR(64) DEFAULT '',
    attempts         INTEGER DEFAULT 0,
    max_attempts     INTEGER DEFAULT 2,
    timeout_sec      INTEGER DEFAULT 3600,
    queued_at        VARCHAR(32) DEFAULT '',
    started_at       VARCHAR(32) DEFAULT '',
    finished_at      VARCHAR(32) DEFAULT '',
    heartbeat_at     VARCHAR(32) DEFAULT '',
    duration_sec     FLOAT DEFAULT 0.0,
    cancel_requested BOOLEAN DEFAULT 0,
    created_at       VARCHAR(32) DEFAULT '',
    updated_at       VARCHAR(32) DEFAULT ''
)
"""

_DDL_JOB_PG = """
CREATE TABLE IF NOT EXISTS sys_async_job (
    id               SERIAL PRIMARY KEY,
    code             VARCHAR(48) NOT NULL UNIQUE,
    job_type         VARCHAR(48) NOT NULL,
    title            VARCHAR(200) DEFAULT '',
    status           VARCHAR(16) DEFAULT 'queued',
    priority         INTEGER DEFAULT 50,
    progress         DOUBLE PRECISION DEFAULT 0.0,
    stage_text       VARCHAR(300) DEFAULT '',
    payload_json     TEXT DEFAULT '{}',
    result_json      TEXT DEFAULT '',
    error_text       VARCHAR(800) DEFAULT '',
    error_detail     TEXT DEFAULT '',
    dedup_key        VARCHAR(200) DEFAULT '',
    ref_type         VARCHAR(32) DEFAULT '',
    ref_id           INTEGER,
    ref_label        VARCHAR(120) DEFAULT '',
    created_by       VARCHAR(80) DEFAULT '',
    created_by_name  VARCHAR(80) DEFAULT '',
    org_code         VARCHAR(64) DEFAULT '',
    site_code        VARCHAR(32) DEFAULT '',
    worker_id        VARCHAR(64) DEFAULT '',
    attempts         INTEGER DEFAULT 0,
    max_attempts     INTEGER DEFAULT 2,
    timeout_sec      INTEGER DEFAULT 3600,
    queued_at        VARCHAR(32) DEFAULT '',
    started_at       VARCHAR(32) DEFAULT '',
    finished_at      VARCHAR(32) DEFAULT '',
    heartbeat_at     VARCHAR(32) DEFAULT '',
    duration_sec     DOUBLE PRECISION DEFAULT 0.0,
    cancel_requested BOOLEAN DEFAULT FALSE,
    created_at       VARCHAR(32) DEFAULT '',
    updated_at       VARCHAR(32) DEFAULT ''
)
"""

_DDL_JOB_EVENT_SQLITE = """
CREATE TABLE IF NOT EXISTS sys_async_job_event (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id   INTEGER NOT NULL,
    seq      INTEGER DEFAULT 0,
    event    VARCHAR(32) DEFAULT '',
    message  VARCHAR(500) DEFAULT '',
    progress FLOAT DEFAULT 0.0,
    actor    VARCHAR(80) DEFAULT '',
    at       VARCHAR(32) DEFAULT '',
    created_at VARCHAR(32) DEFAULT '',
    updated_at VARCHAR(32) DEFAULT ''
)
"""

_DDL_JOB_EVENT_PG = """
CREATE TABLE IF NOT EXISTS sys_async_job_event (
    id       SERIAL PRIMARY KEY,
    job_id   INTEGER NOT NULL REFERENCES sys_async_job(id) ON DELETE CASCADE,
    seq      INTEGER DEFAULT 0,
    event    VARCHAR(32) DEFAULT '',
    message  VARCHAR(500) DEFAULT '',
    progress DOUBLE PRECISION DEFAULT 0.0,
    actor    VARCHAR(80) DEFAULT '',
    at       VARCHAR(32) DEFAULT '',
    created_at VARCHAR(32) DEFAULT '',
    updated_at VARCHAR(32) DEFAULT ''
)
"""


def m0006_async_jobs(conn, engine: Engine) -> str:
    """异步作业队列与事件表。"""
    made = []
    if not has_table(conn, "sys_async_job"):
        conn.execute(text(_DDL_JOB_PG if is_pg(engine) else _DDL_JOB_SQLITE))
        made.append("sys_async_job")
    if not has_table(conn, "sys_async_job_event"):
        conn.execute(text(_DDL_JOB_EVENT_PG if is_pg(engine) else _DDL_JOB_EVENT_SQLITE))
        made.append("sys_async_job_event")
    # 领取作业的复合索引：多 Worker 下这是最热的查询路径
    create_index(conn, engine, "sys_async_job",
                 "ix_job_dispatch", "status, priority, queued_at")
    create_index(conn, engine, "sys_async_job", "ix_job_dedup", "dedup_key, status")
    create_index(conn, engine, "sys_async_job", "ix_job_type_status", "job_type, status")
    create_index(conn, engine, "sys_async_job_event", "ix_job_event_job", "job_id, seq")
    return f"新建表 {made or '无（已存在）'}"


# ---------------------------------------------------------------- 0007 案例向量 case_no
def m0007_case_embedding_case_no(conn, engine: Engine) -> str:
    """切片级向量索引补齐 case_no（评测与检索的病例级分组依据）。

    表名是 `pipe_case_embedding`（模型前缀 pipe_ = pipeline 域）。
    """
    table = "pipe_case_embedding"
    if not has_table(conn, table):
        return f"{table} 不存在，跳过"
    if add_column(conn, engine, table, "case_no", "VARCHAR(64)", ""):
        # 从切片表回填，让历史数据也能按病例分组
        if has_table(conn, "asset_slide"):
            conn.execute(text(
                f"UPDATE {table} SET case_no = ("
                "  SELECT s.case_no FROM asset_slide s WHERE s.id = "
                f"{table}.slide_id"
                ") WHERE (case_no IS NULL OR case_no = '')"
                "  AND slide_id IN (SELECT id FROM asset_slide)"
            ))
        return "新增列 case_no 并回填"
    return "无（已是最新）"


# ---------------------------------------------------------------- 0009 编码器 ONNX 字段
def m0009_encoder_onnx_fields(conn, engine: Engine) -> str:
    """编码器注册表补齐 ONNX 相关列。

    背景：模型清单（configs/model_registry.json）与库内注册表都要能回答
    "这个编码器怎么跑、权重是哪一份"。少了这几列，seed 在全新库上会直接失败
    （老库因为记录已存在不会触发），属于只有干净环境才暴露的缺陷 ——
    正是 CI 用全新数据库跑一遍的价值所在。
    """
    table = "model_encoder"
    if not has_table(conn, table):
        return f"{table} 不存在，跳过"
    changed = []
    for col, typ, dft in (
        ("onnx_sha256", "VARCHAR(64)", ""),
        ("input_norm_onnx", "VARCHAR(32)", ""),
        ("input_layout", "VARCHAR(16)", ""),
        ("resize_mode", "VARCHAR(16)", ""),
        ("batch_size", "INTEGER", 0),
        ("weight_url", "VARCHAR(512)", ""),
    ):
        if add_column(conn, engine, table, col, typ, dft):
            changed.append(col)
    return f"新增列 {changed or '无（已是最新）'}"


# ---------------------------------------------------------------- 0008 兜底补列
def m0008_sync_missing_columns(conn, engine: Engine) -> str:
    """兜底：把「模型有但库里没有」的列补上。

    迁移条目覆盖的是"我们已知的变更"；开发者新加字段但忘了写迁移时，
    这一步保证开发库不会因为缺列而 500。**生产以显式迁移为准**，
    这里执行了任何 DDL 都会打 warning，提示补正式迁移。
    """
    from app.core.database import Base
    from app import models  # noqa: F401

    existing = set(inspect(conn).get_table_names())
    executed: list[str] = []
    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            continue
        have = {c["name"] for c in inspect(conn).get_columns(table.name)}
        for column in table.columns:
            if column.name in have:
                continue
            ddl = (f"ALTER TABLE {table.name} ADD COLUMN {column.name} "
                   f"{column.type.compile(engine.dialect)}")
            if column.default is not None and column.default.is_scalar:
                value = column.default.arg
                if isinstance(value, bool):
                    ddl += f" DEFAULT {1 if value else 0}"
                elif isinstance(value, (int, float)):
                    ddl += f" DEFAULT {value}"
                elif isinstance(value, str):
                    ddl += f" DEFAULT '{value.replace(chr(39), chr(39) * 2)}'"
            try:
                conn.execute(text(ddl))
                executed.append(f"{table.name}.{column.name}")
            except Exception as exc:
                logger.warning("兜底补列失败（已跳过）%s.%s：%s", table.name, column.name, exc)
    if executed:
        logger.warning(
            "兜底补列执行了 %d 处 DDL：%s。请补一条正式迁移，"
            "否则生产库会在下次升级时出现同样的静默不一致。",
            len(executed), ", ".join(executed[:5]),
        )
    return f"兜底补列 {executed or '无'}"


# ================================================================= 注册表
MIGRATIONS: list[Migration] = [
    Migration(1, "baseline", m0001_baseline, "迁移器引入前的结构基线"),
    Migration(2, "slide_provenance_and_scope", m0002_slide_provenance,
              "切片文件指纹/原始文件名/上传人/机构"),
    Migration(3, "asset_scope", m0003_asset_scope, "数据资产机构归属"),
    Migration(4, "user_scope_and_security", m0004_user_scope_and_security,
              "用户数据范围与登录安全"),
    Migration(5, "auth_sessions", m0005_auth_sessions, "刷新会话与登录尝试"),
    Migration(6, "async_jobs", m0006_async_jobs, "异步作业队列与事件"),
    Migration(7, "case_embedding_case_no", m0007_case_embedding_case_no, "案例向量病例号"),
    Migration(8, "sync_missing_columns", m0008_sync_missing_columns, "兜底补列"),
    Migration(9, "encoder_onnx_fields", m0009_encoder_onnx_fields,
              "编码器注册表 ONNX 字段（权重校验和/归一化/布局/批大小）"),
]


# ================================================================= 运行器
def _ensure_version_table(engine: Engine) -> None:
    from app.core.database import SessionLocal  # noqa: F401

    with engine.begin() as conn:
        conn.execute(text(_DDL_VERSION_PG if is_pg(engine) else _DDL_VERSION_SQLITE))


def applied_versions(engine: Engine) -> dict[int, dict]:
    if not has_table(engine, VERSION_TABLE):
        return {}
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"SELECT version, name, checksum, applied_at, applied_by, duration_ms, dialect, note "
            f"FROM {VERSION_TABLE} ORDER BY version"
        )).mappings().all()
    return {int(r["version"]): dict(r) for r in rows}


def _needs_baseline(engine: Engine) -> bool:
    """已有业务表但还没有版本表 = 迁移器引入之前建的老库。"""
    if has_table(engine, VERSION_TABLE):
        return False
    business = {t for t in inspect(engine).get_table_names()
                if t not in (VERSION_TABLE, "sys_distributed_lock")}
    return bool(business)


def run_migrations(engine: Engine, *, lock_wait: float = 60.0) -> dict:
    """执行未应用的迁移。返回摘要（供启动日志 / doctor / readyz 展示）。

    迁移前抢分布式锁：多进程同时启动时，只有一个执行，其余等待后直接读结果。
    抢不到锁**不会**跳过迁移 —— 而是等待；等待超时则抛出，
    因为"带着未知库结构启动"比"启动失败"危险得多。
    """
    from app.core.locks import Lock, LockNotAcquired

    started = time.time()
    summary: dict[str, Any] = {
        "backend": settings.db_backend,
        "applied": [], "baseline_marked": False,
        "skipped": [], "failed": None, "elapsed_ms": 0,
    }

    lock = Lock("smarthealth:migrate", lease_seconds=180, wait_seconds=lock_wait,
                note=f"migrate@{settings.app_short_name}")
    if not lock.acquire():
        raise LockNotAcquired(
            "未能在 {}s 内取得迁移锁（可能另一个进程正在迁移且卡住）。"
            "请检查 sys_distributed_lock / Redis，再重启。".format(lock_wait)
        )

    try:
        _ensure_version_table(engine)
        already = applied_versions(engine)

        if not already and _needs_baseline(engine):
            # 老库：把当前结构登记为版本 1，避免重放历史迁移
            with engine.begin() as conn:
                conn.execute(text(
                    f"INSERT INTO {VERSION_TABLE} (version, name, checksum, applied_at,"
                    f" applied_by, duration_ms, dialect, note) VALUES"
                    f" (:v, :n, :c, :at, :by, 0, :d, :note)"
                ), {"v": 1, "n": "baseline", "c": MIGRATIONS[0].checksum,
                    "at": _now(), "by": _actor(), "d": settings.db_backend,
                    "note": "迁移器引入时对已有结构打基线"})
            already = applied_versions(engine)
            summary["baseline_marked"] = True
            logger.info("迁移器：检测到存量数据库，已登记基线（跳过历史重放）")

        for mig in MIGRATIONS:
            if mig.version in already:
                applied_summary = already[mig.version]
                if applied_summary.get("checksum") and applied_summary["checksum"] != mig.checksum:
                    logger.warning(
                        "迁移 %d(%s) 的校验和与库中记录不一致（库=%s 代码=%s）。"
                        "说明同一版本号被改过实现 —— 后续环境不会重放，可能出现结构漂移。",
                        mig.version, mig.name, applied_summary["checksum"][:8], mig.checksum[:8],
                    )
                summary["skipped"].append(mig.version)
                continue

            t0 = time.monotonic()
            try:
                with engine.begin() as conn:
                    detail = mig.fn(conn, engine) or ""
                    conn.execute(text(
                        f"INSERT INTO {VERSION_TABLE} (version, name, checksum, applied_at,"
                        f" applied_by, duration_ms, dialect, note) VALUES"
                        f" (:v, :n, :c, :at, :by, :ms, :d, :note)"
                    ), {"v": mig.version, "n": mig.name, "c": mig.checksum,
                        "at": _now(), "by": _actor(),
                        "ms": int((time.monotonic() - t0) * 1000),
                        "d": settings.db_backend, "note": str(detail)[:300]})
            except Exception as exc:
                summary["failed"] = {"version": mig.version, "name": mig.name,
                                     "error": f"{type(exc).__name__}: {exc}"}
                logger.exception("迁移 %d(%s) 执行失败，已回滚该迁移", mig.version, mig.name)
                raise
            ms = int((time.monotonic() - t0) * 1000)
            summary["applied"].append({"version": mig.version, "name": mig.name,
                                       "detail": str(detail)[:200], "ms": ms})
            logger.info("迁移 %d(%s) 已应用（%d ms）：%s", mig.version, mig.name, ms, detail)
    finally:
        lock.release()

    summary["elapsed_ms"] = int((time.time() - started) * 1000)
    if summary["applied"]:
        logger.info("迁移完成：应用 %d 条，跳过 %d 条，耗时 %d ms",
                    len(summary["applied"]), len(summary["skipped"]), summary["elapsed_ms"])
    return summary


def migration_status(engine: Engine) -> dict:
    """当前迁移状态（doctor / readyz / 运维接口共用）。"""
    try:
        applied = applied_versions(engine)
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}
    pending = [{"version": m.version, "name": m.name, "note": m.note}
               for m in MIGRATIONS if m.version not in applied]
    drift = []
    for m in MIGRATIONS:
        rec = applied.get(m.version)
        if rec and rec.get("checksum") and rec["checksum"] != m.checksum:
            drift.append({"version": m.version, "name": m.name,
                          "db_checksum": rec["checksum"], "code_checksum": m.checksum})
    return {
        "ok": not pending and not drift,
        "current_version": max(applied) if applied else 0,
        "registered": len(MIGRATIONS),
        "applied": len(applied),
        "pending": pending,
        "checksum_drift": drift,
        "applied_detail": [
            {"version": v, "name": r.get("name"), "at": r.get("applied_at"),
             "by": r.get("applied_by"), "ms": r.get("duration_ms"), "note": r.get("note")}
            for v, r in sorted(applied.items())
        ],
    }


def _now() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")


def _actor() -> str:
    import os
    import socket

    return f"pid={os.getpid()}@{socket.gethostname()[:40]}"
