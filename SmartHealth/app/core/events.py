"""作业事件总线：数据库为准 + Redis 为快。

设计文档依据：第五章（Agent 与作业的可观测性）。

要解决的核心问题：前端怎么知道「作业跑到哪一步了」。

三种做法的取舍（这里写清楚，因为它决定了正确性与运维成本）：

| 做法 | 延迟 | 断线续传 | 跨进程 | 额外依赖 |
|---|---|---|---|---|
| 前端轮询 REST | 等于轮询间隔 | 天然支持（每次拿全量） | 支持 | 无 |
| Redis pub/sub | 毫秒级 | **不支持**（消息即焚） | 支持 | Redis |
| **数据库 tail + Redis 唤醒（本实现）** | 毫秒级（有 Redis）/ 亚秒级（无） | **支持** | **支持** | 无（Redis 可选） |

为什么不只用 Redis pub/sub：pub/sub 是"发出即忘"。客户端断线 3 秒，这 3 秒的事件
就永远丢了；而作业进度是**有状态**的，用户重连后必须看到"我已经到 60% 了"，
而不是从 0 重新开始。所以事件的**权威来源必须是数据库**（`sys_async_job_event`
表的自增 id 天然就是 SSE 的 Last-Event-ID）。

Redis 在这里只承担一件事：**唤醒**。轮询间隔设 1 秒时，作业进度最多滞后 1 秒；
用 Redis pub/sub 收到 "有新事件" 的信号就立刻去数据库取，延迟降到毫秒级，
且不改变任何正确性语义 —— Redis 挂了只是慢一点，不会丢事件。

这个设计让「无 Redis 的小院内环境」与「有 Redis 的多实例生产」跑同一份代码路径，
现场排障时不需要两套心智模型。
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.job import AsyncJob, AsyncJobEvent

logger = logging.getLogger(__name__)

# Redis 频道名。多实例下所有进程都往同一频道发"有新事件"的提示。
CHANNEL = "smarthealth:jobs:events"

# 无 Redis 时的轮询间隔。1.0s 是"用户可感知延迟"与"数据库负载"的平衡点：
# 前端看到进度条每秒动一次不觉得卡，而每秒一次轻量 SELECT id 对库里几乎无压力。
DB_POLL_INTERVAL = 1.0

# 有 Redis 时的兜底轮询间隔。即使订阅正常也保持低频轮询，
# 避免"Redis 连接还在但提示丢了"这类静默故障把事件流永久卡住。
#
# 为什么是 2s 而不是 10s：Redis 提示只负责把延迟压到毫秒级；一旦提示链路
# 失效（订阅线程崩了、消息被丢），最坏延迟就等于这个兜底间隔。
# 10s 意味着"排障时前端进度条卡 10 秒才动一下"，容易被误判成系统挂了。
# 2s 兼顾了"提示失效仍可用"与"轻量"（每 2s 一条 SELECT max(id)）。
REDIS_FALLBACK_POLL_INTERVAL = 2.0


@dataclass
class JobEvent:
    """一条作业事件。id 与 `sys_async_job_event.id` 一致，可直接用作 SSE 的 Last-Event-ID。"""

    id: int
    job_id: int
    seq: int
    event: str
    message: str = ""
    progress: float = 0.0
    actor: str = ""
    at: str = ""
    # 冗余少量作业级字段：前端收到事件即可更新行，不必为每条事件再查一次作业
    job_code: str = ""
    job_type: str = ""
    job_title: str = ""
    job_status: str = ""
    stage_text: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "job_id": self.job_id, "seq": self.seq,
            "event": self.event, "message": self.message, "progress": self.progress,
            "actor": self.actor, "at": self.at,
            "job_code": self.job_code, "job_type": self.job_type,
            "job_title": self.job_title, "job_status": self.job_status,
            "stage_text": self.stage_text,
        }

    def to_sse(self, *, event_name: str = "job") -> str:
        """序列化成 SSE 帧。

        必须带 `id:`：客户端断线重连时浏览器会自动发 `Last-Event-ID` 头，
        服务端据此续传。省掉这一行，SSE 就退化成"断了就丢"。
        """
        return (f"id: {self.id}\n"
                f"event: {event_name}\n"
                f"data: {json.dumps(self.to_dict(), ensure_ascii=False)}\n\n")


class EventBus:
    """作业事件总线。数据库是权威来源，Redis 只做低延迟唤醒。"""

    def __init__(self) -> None:
        self._redis = None
        self._redis_tried = False
        self._wakeup = threading.Condition()
        self._wakeup_seq = 0
        self._subscribers = 0
        self._lock = threading.Lock()

    # -------------------------------------------------------------- Redis
    def _client(self):
        if self._redis_tried:
            return self._redis
        with self._lock:
            if self._redis_tried:
                return self._redis
            self._redis_tried = True
            from app.core.locks import redis_client

            self._redis = redis_client()
            return self._redis

    def publish_hint(self, *, job_id: int = 0, event: str = "") -> None:
        """发布"有新事件"的提示。

        **不携带事件内容**：内容以数据库为准。携带内容会诱使客户端直接用
        消息体渲染，一旦某条提示丢了，界面就与库不一致了。提示只负责"快去看"。
        """
        self._notify_local()
        client = self._client()
        if client is None:
            return
        try:
            client.publish(CHANNEL, json.dumps({"job_id": job_id, "event": event,
                                                "ts": time.time()}, ensure_ascii=False))
        except Exception as exc:  # pragma: no cover - 网络/Redis 抖动
            logger.debug("事件提示发布失败（不影响正确性，退化为轮询）：%s", exc)

    def _notify_local(self) -> None:
        with self._wakeup:
            self._wakeup_seq += 1
            self._wakeup.notify_all()

    def _wait_for_hint(self, timeout: float) -> None:
        """等待唤醒信号或超时。超时是正常路径（保证即使没有任何提示也会去查库）。"""
        with self._wakeup:
            self._wakeup.wait(timeout=max(0.05, timeout))

    # -------------------------------------------------------------- 查询
    @staticmethod
    def fetch_events(*, after_id: int = 0, job_id: int | None = None,
                     job_type: str = "", limit: int = 200,
                     terminal_only: bool = False) -> list[JobEvent]:
        """按 id 升序取事件。`after_id` 就是断点续传的游标。"""
        with SessionLocal() as db:
            stmt = (select(AsyncJobEvent, AsyncJob)
                    .join(AsyncJob, AsyncJob.id == AsyncJobEvent.job_id)
                    .where(AsyncJobEvent.id > int(after_id))
                    .order_by(AsyncJobEvent.id.asc())
                    .limit(max(1, min(int(limit), 1000))))
            if job_id:
                stmt = stmt.where(AsyncJobEvent.job_id == int(job_id))
            if job_type:
                stmt = stmt.where(AsyncJob.job_type == job_type)
            if terminal_only:
                stmt = stmt.where(AsyncJob.status.in_(("succeeded", "failed",
                                                       "cancelled", "timeout", "dead")))
            rows = db.execute(stmt).all()
            events: list[JobEvent] = []
            for event_row, job_row in rows:
                events.append(JobEvent(
                    id=int(event_row.id), job_id=int(event_row.job_id),
                    seq=int(event_row.seq or 0), event=str(event_row.event or ""),
                    message=str(event_row.message or ""),
                    progress=float(event_row.progress or 0.0),
                    actor=str(event_row.actor or ""), at=str(event_row.at or ""),
                    job_code=str(job_row.code or ""), job_type=str(job_row.job_type or ""),
                    job_title=str(job_row.title or ""), job_status=str(job_row.status or ""),
                    stage_text=str(job_row.stage_text or ""),
                ))
            return events

    @staticmethod
    def latest_event_id() -> int:
        from sqlalchemy import func

        with SessionLocal() as db:
            return int(db.execute(select(func.max(AsyncJobEvent.id))).scalar() or 0)

    # -------------------------------------------------------------- 服务端推送
    def stream(self, *, after_id: int = 0, job_id: int | None = None,
               job_type: str = "", poll_interval: float | None = None,
               batch_limit: int = 200) -> Iterator[dict[str, Any]]:
        """产出事件字典流。调用方（SSE/WS 端点）负责编码与心跳。

        产出项有两种：
        - `{"type": "event", "event": JobEvent}`  —— 真实事件
        - `{"type": "idle", "cursor": int}`       —— 无新事件（调用方据此发注释心跳）

        为什么把"空闲"也产出：SSE 连接若长时间没有字节流动，中间的代理/防火墙
        会判定连接空闲并掐断（常见阈值 30—60s）。让调用方有稳定的心跳节拍，
        是长连接能否活过 1 分钟的关键。
        """
        interval = float(poll_interval if poll_interval is not None
                         else (REDIS_FALLBACK_POLL_INTERVAL if self._client() else DB_POLL_INTERVAL))
        cursor = int(after_id)
        with self._lock:
            self._subscribers += 1
        try:
            while True:
                events = self.fetch_events(after_id=cursor, job_id=job_id,
                                           job_type=job_type, limit=batch_limit)
                if events:
                    for event in events:
                        cursor = max(cursor, event.id)
                        yield {"type": "event", "event": event}
                    continue      # 有积压就继续追，尽快把滞后补齐
                yield {"type": "idle", "cursor": cursor}
                self._wait_for_hint(interval)
        finally:
            with self._lock:
                self._subscribers -= 1

    def redis_subscriber(self, *, after_id: int = 0, job_id: int | None = None,
                         job_type: str = ""):
        """Redis 订阅（若可用）与 DB tail 的组合流。

        返回 (events_iterator, mode)。mode 用于在首帧告知客户端"快通道是否在用"，
        让前端/运维知道当前延迟特性，而不是靠猜。

        **`after_id` 必须由调用方传入**（通常是首帧要告诉客户端的那个游标）。
        踩过的坑：调用方算了游标只用于 ready 帧、却没传进来，结果生成器从 0 开始，
        每个新连接都把**全部历史事件**重放一遍 —— 前端一打开任务中心就被几百条
        历史事件刷屏，且看上去"流量很大"。游标是一处定义、两处使用，必须一起传。
        """
        client = self._client()
        if client is None:
            return self.stream(after_id=after_id, job_id=job_id, job_type=job_type,
                               poll_interval=DB_POLL_INTERVAL), "database"

        # 有 Redis：起一个订阅线程，收到提示就唤醒本地等待者
        stop = threading.Event()

        def _listen() -> None:  # pragma: no cover - 依赖 Redis 运行时
            try:
                pubsub = client.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(CHANNEL)
                while not stop.is_set():
                    message = pubsub.get_message(timeout=1.0)
                    if message is not None:
                        self._notify_local()
            except Exception as exc:
                logger.warning("Redis 事件订阅中断（退化为轮询，不影响正确性）：%s", exc)
            finally:
                try:
                    pubsub.close()
                except Exception:
                    pass

        thread = threading.Thread(target=_listen, name="job-event-subscriber", daemon=True)
        thread.start()
        return self.stream(after_id=after_id, job_id=job_id, job_type=job_type,
                           poll_interval=REDIS_FALLBACK_POLL_INTERVAL), "redis"

    def stats(self) -> dict:
        return {
            "channel": CHANNEL,
            "transport": "redis+db" if self._client() is not None else "db-poll",
            "db_poll_interval": DB_POLL_INTERVAL,
            "redis_fallback_poll_interval": REDIS_FALLBACK_POLL_INTERVAL,
            "subscribers": self._subscribers,
            "db_bytes": None,
            "note": ("数据库是事件权威来源（支持断线续传）；"
                     "Redis 仅用于把延迟从约 1s 降到毫秒级，缺失不影响正确性。"),
        }


EVENTS = EventBus()


def publish_job_hint(job_id: int, event: str = "") -> None:
    """在作业状态变化处调用。**绝不能让提示发布失败影响作业本体。**"""
    try:
        EVENTS.publish_hint(job_id=job_id, event=event)
    except Exception:  # pragma: no cover
        logger.debug("作业事件提示发布异常（已忽略）", exc_info=True)
