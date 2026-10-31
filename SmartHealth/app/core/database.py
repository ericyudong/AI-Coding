"""数据库会话与建表/迁移入口。

职责：
- 构造引擎（方言差异委托给 `db_engine.create_app_engine`）
- 提供请求级会话依赖
- `init_db()` 统一走「迁移器」，而不是 `create_all` 裸跑

为什么不再直接 `create_all`：
`create_all` 只能"建不存在的表"，对已存在的表**不会**加列/改类型；
演示阶段靠 `sync_missing_columns` 打补丁还凑合，多环境一铺开必然出现
"开发库有这列、生产库没有"的静默不一致。生产必须走版本化迁移。
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings
from app.core.db_engine import create_app_engine, describe_database_url

logger = logging.getLogger(__name__)

if settings.is_sqlite:
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)

engine = create_app_engine()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False,
                            expire_on_commit=False)

# --------------------------------------------------------------- 写事务会话
# SQLite 有一个只在并发写时才暴露的陷阱：**同一事务里"先 SELECT 再 UPDATE"**
# 会走"锁升级"。若此刻别的进程持有写锁，SQLite 会**立即**返回 SQLITE_BUSY，
# 且刻意不等待 busy_timeout（它认为立即报错比死等更安全）。
# 结果是：配了 busy_timeout=60s 仍然秒失败 "database is locked"。
#
# 解法是让写事务一开头就取写锁（BEGIN IMMEDIATE），把"升级"变成"等待"：
# 此时 busy_timeout 正常生效，多个 Worker 会排队而不是互相把对方打回。
#
# 为什么不干脆让全库都 IMMEDIATE：那会让只读的 API 查询也排在同一把写锁上，
# 在 WAL 模式下白白丢掉"读不阻塞写"的优势。所以只给**确定要写的路径**
# （作业执行、作业领取、状态回写）用这个会话；API 的只读查询仍用普通会话。
if settings.is_sqlite:
    from sqlalchemy import event as _sa_event

    # 独立一个引擎（共享同一个连接池配置），对它挂两个事件钩子：
    #   1) connect 时关掉 pysqlite 的隐式 BEGIN 管理；
    #   2) begin 时显式发 `BEGIN IMMEDIATE`，让写锁在事务开头就拿到。
    # 这是 SQLAlchemy 官方推荐的 SQLite 事务控制方式 ——
    # 注意：`execution_options(isolation_level="IMMEDIATE")` 在 pysqlite 方言下
    # **不被接受**（只认 READ UNCOMMITTED / SERIALIZABLE / AUTOCOMMIT），
    # 所以只能用事件钩子，不能图省事写 isolation_level。
    _writer_engine = create_app_engine()

    @_sa_event.listens_for(_writer_engine, "connect")
    def _writer_no_implicit_begin(dbapi_connection, _record):  # pragma: no cover
        dbapi_connection.isolation_level = None

    @_sa_event.listens_for(_writer_engine, "begin")
    def _writer_begin_immediate(conn):  # pragma: no cover
        conn.exec_driver_sql("BEGIN IMMEDIATE")

    WriterSessionLocal = sessionmaker(bind=_writer_engine, autocommit=False,
                                      autoflush=False, expire_on_commit=False)
else:
    # PostgreSQL 等真实数据库不需要这套：行级锁 + SKIP LOCKED 已经解决并发领取，
    # 且其"读后写"不会因为升级而立即失败（而是等锁）。
    WriterSessionLocal = SessionLocal


class Base(DeclarativeBase):
    """所有 ORM 实体的基类。"""


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：请求级数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(*, run_migrations: bool = True) -> dict:
    """建表 + 迁移。返回迁移结果摘要（供启动日志与 /readyz 展示）。"""
    from app import models  # noqa: F401  —— 触发所有实体注册到 Base.metadata

    Base.metadata.create_all(bind=engine)
    if not run_migrations:
        return {"applied": [], "skipped": True}
    from app.core.migrations import run_migrations as _run

    return _run(engine)


def sync_missing_columns() -> list[str]:
    """为已存在的表补齐模型新增列，返回实际执行的 DDL 列表。

    保留它是为了兼容 SQLite 单机开发：迁移器覆盖"我们已知的变更"，
    而这支兜底逻辑覆盖"开发者新加了模型字段但还没写迁移"的场景，
    避免开发过程中反复手动删库。
    **生产环境应以迁移器为准**，兜底逻辑只记 warning。
    """
    executed: list[str] = []
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        db_columns = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in db_columns:
                continue
            ddl = (f"ALTER TABLE {table.name} ADD COLUMN "
                   f"{column.name} {column.type.compile(engine.dialect)}")
            if column.default is not None and column.default.is_scalar:
                default_value = column.default.arg
                if isinstance(default_value, bool):
                    ddl += f" DEFAULT {1 if default_value else 0}"
                elif isinstance(default_value, (int, float)):
                    ddl += f" DEFAULT {default_value}"
                elif isinstance(default_value, str):
                    escaped = default_value.replace("'", "''")
                    ddl += f" DEFAULT '{escaped}'"
            try:
                with engine.begin() as conn:
                    conn.execute(text(ddl))
                executed.append(ddl)
            except Exception as exc:  # pragma: no cover - 兼容非 SQLite 方言
                logger.warning("补列失败（已跳过）：%s -> %s", ddl, exc)
    if executed:
        logger.warning(
            "检测到 %d 处「模型有列但库中没有」的差异，已用兜底补列修复。"
            "请补一条正式迁移，避免生产环境出现同样的静默不一致：%s",
            len(executed), "; ".join(executed[:3]),
        )
    return executed


def drop_all() -> None:
    from app import models  # noqa: F401

    Base.metadata.drop_all(bind=engine)


def database_summary() -> dict:
    """数据库自省摘要（启动日志 / /readyz / doctor 共用）。"""
    from app.core.db_engine import ping, pool_status

    tables = sorted(inspect(engine).get_table_names())
    return {
        "backend": settings.db_backend,
        "url": describe_database_url(),
        "table_count": len(tables),
        "ping": ping(engine),
        "pool": pool_status(engine),
    }
