"""分布式锁：Redis 优先，数据库兜底。

为什么必须有：
多进程/多实例部署后，「只能有一个执行者」的事情会突然变多：
- 启动时的数据库迁移（两个进程同时迁移 = 迁移冲突）
- 周期任务（心跳检测、KPI 快照）在多进程下会被执行 N 次
- 未来的缓存刷新、对账任务

实现要点（这些是分布式锁最容易写错的地方）：
1. **可用性不等于正确性**：抢锁必须原子（Redis `SET NX PX`；DB 靠主键冲突/条件更新）。
2. **释放必须校验持有者**：否则 A 超时后 B 抢到锁，A 释放时把 B 的锁删了。
   Redis 用 Lua 脚本比对 token 再删；DB 用 `WHERE owner=?`。
3. **租约 + 续期**：进程崩溃不能让锁永久占用。租约到期自动失效。
4. **降级要有明确语义**：Redis 不可用时退化为 DB 锁；DB 也不可用时**不允许**"默默放行"
   ——宁可任务不执行，也不要重复执行（迁移重复执行是会丢数据的）。
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from sqlalchemy import text

from app.core.config import settings

logger = logging.getLogger(__name__)

_REDIS_CLIENT: Any = None
_REDIS_TRIED = False
_REDIS_LOCK = threading.Lock()

# 释放锁的 Lua 脚本：比对 token 后再删，保证"只删自己持有的锁"
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""

_RENEW_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('pexpire', KEYS[1], ARGV[2])
else
    return 0
end
"""


def redis_client() -> Any:
    """惰性创建 Redis 客户端。未配置或不可用时返回 None（不抛异常）。"""
    global _REDIS_CLIENT, _REDIS_TRIED
    if not settings.redis_url:
        return None
    with _REDIS_LOCK:
        if _REDIS_CLIENT is not None:
            return _REDIS_CLIENT
        if _REDIS_TRIED:
            return None
        _REDIS_TRIED = True
        try:
            import redis

            client = redis.Redis.from_url(
                settings.redis_url, socket_timeout=3, socket_connect_timeout=3,
                health_check_interval=30, decode_responses=True,
            )
            client.ping()
            _REDIS_CLIENT = client
            logger.info("Redis 已接入：%s（分布式锁与事件推送走 Redis）",
                        settings.redis_url.rsplit("@", 1)[-1])
        except Exception as exc:
            logger.warning("Redis 不可用（将退化为数据库锁与数据库轮询）：%s", exc)
            _REDIS_CLIENT = None
        return _REDIS_CLIENT


def redis_status() -> dict:
    client = redis_client()
    if client is None:
        return {"configured": bool(settings.redis_url), "connected": False}
    try:
        info = client.info("server")
        return {"configured": True, "connected": True,
                "version": info.get("redis_version"),
                "mode": info.get("redis_mode", "standalone")}
    except Exception as exc:
        return {"configured": True, "connected": False, "error": str(exc)[:200]}


def backend_name() -> str:
    return "redis" if redis_client() is not None else "database"


# ------------------------------------------------------------------ 数据库锁表
_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS sys_distributed_lock (
    lock_key   VARCHAR(160) PRIMARY KEY,
    owner      VARCHAR(160) NOT NULL,
    acquired_at VARCHAR(32) NOT NULL,
    expires_at  VARCHAR(32) NOT NULL,
    note       VARCHAR(300) DEFAULT ''
)
"""

_DDL_PG = """
CREATE TABLE IF NOT EXISTS sys_distributed_lock (
    lock_key    VARCHAR(160) PRIMARY KEY,
    owner       VARCHAR(160) NOT NULL,
    acquired_at VARCHAR(32) NOT NULL,
    expires_at  VARCHAR(32) NOT NULL,
    note        VARCHAR(300) DEFAULT ''
)
"""


def ensure_lock_table(engine) -> None:
    ddl = _DDL_PG if engine.dialect.name == "postgresql" else _DDL_SQLITE
    with engine.begin() as conn:
        conn.execute(text(ddl))


class Lock:
    """锁句柄。支持 with 与显式 acquire/release。"""

    def __init__(self, key: str, *, lease_seconds: int | None = None,
                 wait_seconds: float = 0.0, note: str = "") -> None:
        self.key = key
        self.lease = int(lease_seconds or settings.lock_lease_seconds)
        self.wait_seconds = float(wait_seconds)
        self.note = note
        self.token = f"{os.getpid()}-{uuid.uuid4().hex[:10]}"
        self.backend = backend_name()
        self.acquired = False

    # -------------------------------------------------------------- 获取
    def acquire(self) -> bool:
        deadline = time.monotonic() + max(0.0, self.wait_seconds)
        while True:
            ok = self._try_acquire()
            if ok or time.monotonic() >= deadline:
                self.acquired = ok
                return ok
            time.sleep(0.2)

    def _try_acquire(self) -> bool:
        client = redis_client()
        if client is not None:
            try:
                return bool(client.set(self.key, self.token, nx=True, px=self.lease * 1000))
            except Exception as exc:
                logger.warning("Redis 抢锁失败，降级尝试数据库锁：%s", exc)
        return self._try_acquire_db()

    def _try_acquire_db(self) -> bool:
        from app.core.database import engine

        ensure_lock_table(engine)
        now = datetime.now()
        expires = now.timestamp() + self.lease
        expires_at = datetime.fromtimestamp(expires).isoformat(timespec="seconds")
        acquired_at = now.isoformat(timespec="seconds")
        try:
            with engine.begin() as conn:
                # 先用条件更新抢占「已过期」的锁
                updated = conn.execute(text(
                    "UPDATE sys_distributed_lock SET owner=:owner, acquired_at=:acq,"
                    " expires_at=:exp, note=:note WHERE lock_key=:key AND expires_at < :now"
                ), {"owner": self.token, "acq": acquired_at, "exp": expires_at,
                    "note": self.note[:300], "key": self.key, "now": acquired_at})
                if updated.rowcount == 1:
                    return True
                try:
                    conn.execute(text(
                        "INSERT INTO sys_distributed_lock (lock_key, owner, acquired_at,"
                        " expires_at, note) VALUES (:key, :owner, :acq, :exp, :note)"
                    ), {"key": self.key, "owner": self.token, "acq": acquired_at,
                        "exp": expires_at, "note": self.note[:300]})
                    return True
                except Exception:
                    return False  # 主键冲突 = 别人持有
        except Exception as exc:
            logger.error("数据库锁获取异常：%s", exc)
            return False

    # -------------------------------------------------------------- 释放与续期
    def release(self) -> bool:
        if not self.acquired:
            return False
        self.acquired = False
        client = redis_client()
        if client is not None:
            try:
                # Lua：只有持有者才能释放。若直接 DEL，A 超时后 B 抢到锁，A 会误删 B 的锁
                released = bool(client.eval(_RELEASE_LUA, 1, self.key, self.token))
                if released:
                    return True
            except Exception as exc:
                logger.warning("Redis 释放锁失败：%s", exc)
        return self._release_db()

    def _release_db(self) -> bool:
        from app.core.database import engine

        with engine.begin() as conn:
            result = conn.execute(text(
                "DELETE FROM sys_distributed_lock WHERE lock_key=:key AND owner=:owner"
            ), {"key": self.key, "owner": self.token})
        return result.rowcount == 1

    def renew(self, seconds: int | None = None) -> bool:
        """续期。长任务持有锁时必须定期调用，否则租约到期会被别人抢走。"""
        lease = int(seconds or self.lease)
        client = redis_client()
        if client is not None:
            try:
                return bool(client.eval(_RENEW_LUA, 1, self.key, self.token, lease * 1000))
            except Exception:
                return False
        from app.core.database import engine

        expires_at = datetime.fromtimestamp(datetime.now().timestamp() + lease).isoformat(timespec="seconds")
        with engine.begin() as conn:
            result = conn.execute(text(
                "UPDATE sys_distributed_lock SET expires_at=:exp WHERE lock_key=:key AND owner=:owner"
            ), {"exp": expires_at, "key": self.key, "owner": self.token})
        return result.rowcount == 1

    # -------------------------------------------------------------- 语法糖
    def __enter__(self) -> "Lock":
        if not self.acquire():
            raise LockNotAcquired(f"未能获取锁：{self.key}（backend={self.backend}）")
        return self

    def __exit__(self, *exc) -> None:
        self.release()

    def try_with(self):
        """with 用法但失败不抛异常：`with lock.try_with() as got: if got: ...`"""
        return _TryLock(self)


class _TryLock:
    def __init__(self, lock: Lock) -> None:
        self.lock = lock

    def __enter__(self) -> bool:
        return self.lock.acquire()

    def __exit__(self, *exc) -> None:
        self.lock.release()


class LockNotAcquired(RuntimeError):
    pass


@contextmanager
def exclusive(key: str, *, lease_seconds: int | None = None, wait_seconds: float = 0.0,
              note: str = ""):
    """便捷上下文：抢到锁才执行，抢不到直接跳过（yield False）。"""
    lock = Lock(key, lease_seconds=lease_seconds, wait_seconds=wait_seconds, note=note)
    got = lock.acquire()
    try:
        yield got
    finally:
        if got:
            lock.release()


def lock_status() -> dict:
    return {"backend": backend_name(), "redis": redis_status(),
            "lease_seconds": settings.lock_lease_seconds}


def self_test(key_prefix: str = "smarthealth:selftest") -> dict:
    """对分布式锁做一次**真实的功能往返**，而不是只 ping 一下。

    为什么必须测语义而不能只测连通性：
    锁的正确性依赖三个能力 —— 原子抢锁（`SET NX PX`）、**只有持有者能释放**（Lua EVAL）、
    租约续期（Lua EVAL）。而 Redis 的 ACL 可以只给 `+set` 而不给 `+eval`，
    托管 Redis 集群也可能对 EVAL 有限制。这类环境下 ping 完全正常、分布式锁却会在
    "释放"这一步静默失败 —— 后果是锁**永不释放**，直到租约到期，周期任务与迁移
    在租约窗口内被彻底阻塞，而且报错信息只会是"未能获取锁"，让人往错的方向查。

    所以这里模拟真实使用方式跑一遍：
        抢锁 → 用**别人的 token**释放（必须失败）→ 自己释放 → 确认可再抢 → 释放
    """
    import uuid as _uuid

    key = f"{key_prefix}:{_uuid.uuid4().hex[:8]}"
    steps: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        steps.append({"step": name, "ok": bool(ok), "detail": detail})

    first = Lock(key, lease_seconds=10, note="self-test")
    second = Lock(key, lease_seconds=10, note="self-test-contender")

    got_first = first.acquire()
    add("抢锁成功", got_first, f"backend={first.backend}")

    if not got_first:
        return {"ok": False, "key": key, "backend": backend_name(), "steps": steps}

    # 竞争者必须抢不到 —— 这是"互斥"的核心语义
    got_second = second.acquire()
    add("竞争方被正确拒绝（互斥生效）", not got_second)

    # 用竞争方的 token 去释放：必须失败。这一条专门验证"释放校验持有者"
    # 的实现有没有退化成一个裸 DEL。
    foreign_release = False
    client = redis_client()
    if client is not None:
        try:
            foreign_release = bool(client.eval(_RELEASE_LUA, 1, key, second.token))
        except Exception as exc:
            add("非持有者释放被拒（需 EVAL 权限）", False,
                f"Lua 执行失败：{type(exc).__name__}: {exc}")
        else:
            add("非持有者释放被拒（需 EVAL 权限）", not foreign_release,
                "裸 DEL 会让 A 超时后误删 B 的锁")
    else:
        # DB 锁：用错误 owner 删除，rowcount 必须为 0
        from app.core.database import engine as _engine

        ensure_lock_table(_engine)
        with _engine.begin() as conn:
            result = conn.execute(text(
                "DELETE FROM sys_distributed_lock WHERE lock_key=:k AND owner=:o"
            ), {"k": key, "o": second.token})
        add("非持有者释放被拒", result.rowcount == 0)

    add("持有者释放成功", first.release())

    # 释放后必须能重新抢到（否则说明锁泄漏，租约到期前谁也用不了）
    reacquired = Lock(key, lease_seconds=5).acquire()
    add("释放后可重新抢到（无锁泄漏）", reacquired)
    if reacquired:
        Lock(key, lease_seconds=5).release()
        # 上面用的是新实例，release 需要同实例；这里直接清掉以免残留
        from app.core.database import engine as _engine2

        if redis_client() is not None:
            try:
                redis_client().delete(key)
            except Exception:
                pass
        else:
            with _engine2.begin() as conn:
                conn.execute(text("DELETE FROM sys_distributed_lock WHERE lock_key=:k"),
                             {"k": key})

    # 续期能力（长任务迁移/联邦训练需要）
    renew_probe = Lock(key, lease_seconds=10)
    if renew_probe.acquire():
        add("租约续期可用", renew_probe.renew(30), "长任务必需")
        renew_probe.release()

    ok_all = all(step["ok"] for step in steps)
    return {"ok": ok_all, "key": key, "backend": backend_name(), "steps": steps}
