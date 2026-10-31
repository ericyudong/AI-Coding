"""数据库引擎构造（方言感知）与连通性/连接池自省。

为什么要把"引擎构造"单独管起来：
SQLite 与 PostgreSQL 的差异不只是连接串 ——
- SQLite 需要 `check_same_thread=False` 与 `PRAGMA journal_mode/busy_timeout`；
- PostgreSQL 需要连接池上限、回收时间、`statement_timeout`，且**绝不能**执行 PRAGMA；
- 多进程部署时 PostgreSQL 才是正确选择：SQLite 单写者，Worker 一多就在等锁。

把差异集中在 `create_app_engine()` 里，业务代码就不必到处写 `if is_sqlite`。
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

from app.core.config import settings

logger = logging.getLogger(__name__)


def describe_database_url(url: str | None = None) -> str:
    """把连接串脱敏成可安全写进日志/接口的形式（去掉密码）。"""
    raw = url if url is not None else settings.database_url
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        if parts.password:
            netloc = f"{parts.username}:***@{parts.hostname}"
            if parts.port:
                netloc += f":{parts.port}"
            parts = parts._replace(netloc=netloc)
        return parts.geturl()
    except Exception:
        return raw.split("@")[-1]


def create_app_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    """按方言构造引擎。"""
    target = url or settings.database_url
    backend = settings.db_backend if url is None else (
        "postgresql" if str(target).lower().startswith(("postgresql", "postgres"))
        else ("sqlite" if str(target).lower().startswith("sqlite") else "unknown")
    )

    kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True, "echo": echo}

    if backend == "sqlite":
        # timeout：锁等待上限（秒）。作业引擎与 API 并发写同一文件库时必需。
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 60}
    elif backend == "postgresql":
        kwargs.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
            # PG 的连接池预检测用 rollback 更轻，避免每次借连接都发一条 SELECT
            pool_pre_ping=False,
        )
        connect_args: dict[str, Any] = {
            "application_name": settings.app_short_name,
        }
        if settings.db_statement_timeout_ms > 0:
            connect_args["options"] = f"-c statement_timeout={settings.db_statement_timeout_ms}"
        kwargs["connect_args"] = connect_args

    engine = create_engine(target, **kwargs)

    if backend == "sqlite":
        _install_sqlite_pragmas(engine)
    else:
        _install_session_guards(engine, backend)

    logger.info("数据库引擎已就绪：backend=%s url=%s", backend, describe_database_url(target))
    return engine


def _install_sqlite_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection, _record):  # pragma: no cover - 环境相关
        """WAL 让读写并发不再互相阻塞；busy_timeout 让写锁竞争自动重试。

        没有这两项，作业 Worker 与 API 请求同时写库时会频繁出现
        「database is locked」——演示环境看不出问题，上生产立刻暴露。
        """
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=60000")
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


def _install_session_guards(engine: Engine, backend: str) -> None:
    """PostgreSQL 会话级保护：语句超时 + 空闲事务不无限挂起。"""
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, _record):  # pragma: no cover - 环境相关
        try:
            with dbapi_connection.cursor() as cur:
                if settings.db_statement_timeout_ms > 0:
                    cur.execute(f"SET statement_timeout = {int(settings.db_statement_timeout_ms)}")
                    # 空闲事务超过 5 分钟自动回滚，避免 Worker 卡住时长期持有锁
                    cur.execute("SET idle_in_transaction_session_timeout = 300000")
                cur.execute("SET TIME ZONE 'UTC'")
            dbapi_connection.commit()
        except Exception as exc:
            logger.warning("会话参数设置失败（不影响主流程）：%s", exc)


def ping(engine: Engine | None = None) -> dict[str, Any]:
    """数据库连通性与版本自省。供 /readyz 与 doctor 使用。"""
    from app.core.database import engine as default_engine

    eng = engine or default_engine
    result: dict[str, Any] = {"backend": settings.db_backend, "ok": False}
    try:
        with eng.connect() as conn:
            if settings.db_backend == "sqlite":
                result["version"] = conn.execute(text("select sqlite_version()")).scalar()
                result["journal_mode"] = conn.execute(text("PRAGMA journal_mode")).scalar()
            elif settings.db_backend == "postgresql":
                result["version"] = conn.execute(text("select version()")).scalar()
                result["server_version"] = conn.execute(text("show server_version")).scalar()
                result["max_connections"] = conn.execute(text("show max_connections")).scalar()
                result["current_db"] = conn.execute(text("select current_database()")).scalar()
            else:
                result["version"] = "unknown"
        result["ok"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"[:300]
    return result


def pool_status(engine: Engine | None = None) -> dict[str, Any]:
    """连接池状态。多 Worker 部署下这是最该盯的指标之一：
    池被占满时表现为"接口变慢"，而不是报错，不主动暴露就很难发现。"""
    from app.core.database import engine as default_engine

    eng = engine or default_engine
    pool = eng.pool
    info: dict[str, Any] = {"class": type(pool).__name__}
    try:
        info["size"] = pool.size()          # type: ignore[attr-defined]
        info["checked_out"] = pool.checkedout()  # type: ignore[attr-defined]
        info["overflow"] = pool.overflow()  # type: ignore[attr-defined]
        info["max_overflow"] = getattr(pool, "_max_overflow", None)
    except Exception:
        info["note"] = "该方言的连接池不提供统计（SQLite 默认使用 QueuePool，通常可用）"
    return info


def supports_skip_locked(engine: Engine | None = None) -> bool:
    """是否支持 SELECT ... FOR UPDATE SKIP LOCKED。

    PostgreSQL 9.5+ 支持；SQLite 不支持（它是单写者，用条件 UPDATE 即可）。
    这是作业队列领取策略的分岔点。
    """
    from app.core.database import engine as default_engine

    eng = engine or default_engine
    return eng.dialect.name in ("postgresql", "mysql")
