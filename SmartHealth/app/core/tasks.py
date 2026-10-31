"""异步作业引擎。

职责边界（刻意保持单一）：
- 只负责「调度、执行、进度、取消、重试、超时、恢复」
- 不包含任何业务逻辑：业务通过 register() 注册 handler 接入

关键工程性质（这些是生产可用与否的分水岭）：
1. **持久化队列**：作业落库。进程重启后排队作业不丢，执行中的作业被识别为孤儿并标记失败可重试。
2. **原子领取**：`UPDATE ... WHERE id=? AND status='queued'` 保证多 Worker/多进程下不重复执行。
3. **请求式取消**：cancel 只置标志，Worker 在安全检查点响应，避免落库到一半被硬杀导致脏数据。
4. **心跳**：执行中定期续心跳，调度线程据此回收僵死作业（Worker 崩溃时）。
5. **进度节流**：进度写库按「变化 ≥1% 或间隔 ≥0.5s」节流，避免高频写放大。
6. **事件流**：每次状态变化落一条事件，可回放「这个任务到底发生了什么」。
7. **优雅关闭**：停止接单 → 请求在跑作业取消 → 等待落地 → 退出。

用法：
    from app.core.tasks import TASKS
    TASKS.register("train", handler, default_timeout=7200)
    job = TASKS.submit(db, job_type="train", payload={...}, title="...", created_by="algo01")
"""

from __future__ import annotations

import json
import logging
import os
import random
import threading
import time
import traceback
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import OperationalError

from app.core.database import SessionLocal, WriterSessionLocal
from app.models.job import TERMINAL_STATUSES, AsyncJob, AsyncJobEvent

logger = logging.getLogger("smarthealth.tasks")


def settings_workers() -> int:
    """Worker 数量。IO 与纯数值计算混合负载下，2—4 个是合理默认。"""
    from app.core.config import settings

    return max(1, int(getattr(settings, "job_workers", 2)))


# ------------------------------------------------------------------ 异常与上下文
class JobCancelled(Exception):
    """作业被取消。handler 无需捕获，引擎会正确处理。"""


class JobTimeout(Exception):
    """作业超时。"""


class NonRetryableJobError(Exception):
    """业务规则类失败：重试不会改变结果（如「评测集缺少预测结果」「训练集为空」）。

    handler 抛出它的子类（或把异常标记 non_retryable=True）时，引擎不会自动重试，
    直接落 failed。否则用户会看到「同一个业务错误被重试 2 次」的噪音。
    """

    non_retryable = True


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_code(job_type: str) -> str:
    prefix = {
        "feature_precompute": "FP", "train": "TR", "inference": "IN", "evaluate": "EV",
        "mrmc": "MC", "federated": "FD", "import_slides": "IM", "qc_recompute": "QC",
        "explainability": "EX", "boundary_check": "BC",
    }.get(job_type, "JB")
    return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"


def _publish_event_hint(job_id: int, event: str = "") -> None:
    """发布事件提示。**失败必须被吞掉** —— 它是加速手段，不是正确性依赖。"""
    try:
        from app.core.events import publish_job_hint

        publish_job_hint(job_id, event)
    except Exception:  # pragma: no cover
        logger.debug("事件提示发布失败（已忽略）", exc_info=True)


class JobContext:
    """handler 的运行时上下文。

    handler 拿到 ctx 后可以：
        ctx.payload          入队时传入的参数
        ctx.progress(0.4, "已抽取 1200/3000 个图块")   上报进度
        ctx.log("命中 3 个可疑区域")                   追加事件
        ctx.check_cancel()   在安全检查点响应取消（取消时抛 JobCancelled）
        with ctx.db() as db: 获取一个会话（用完自动关闭，避免长连接）
    """

    def __init__(self, job_id: int, worker_id: str) -> None:
        self.job_id = job_id
        self.worker_id = worker_id
        self._lock = threading.Lock()
        self._last_write = 0.0
        self._last_progress = -1.0
        self._cancel_flag = False
        self._seq = 0
        self._session = None          # handler 正在使用的会话（见 attach/detach）
        self._session_depth = 0
        self.payload: dict[str, Any] = {}
        self.started_monotonic = time.monotonic()

    # -------------------------------------------------------------- 会话
    @contextmanager
    def db(self):
        """handler 的数据库会话。进入时把它绑定给 ctx，使进度/事件写复用同一连接。

        为什么必须复用同一连接：SQLite 是单写者数据库。handler 一旦写入（如落 EvalRun），
        它的连接就持有写锁；此时 ctx.progress 若另开连接写事件，会等待 handler 自己持有的锁，
        形成**自死锁**，直到 busy_timeout 到期报 "database is locked"。
        复用同一连接后，进度写退化为 SAVEPOINT（子事务），既立即生效又不提交业务事务。
        """
        # 用写事务会话：handler 会在同一事务里读切片、写特征、报进度，
        # 用普通会话会踩 SQLite 锁升级的"立即失败"。见 database.WriterSessionLocal。
        session = WriterSessionLocal() if self._session is None else None
        active = session or self._session
        if session is not None:
            self.attach(session)
        self._session_depth += 1
        try:
            yield active
            if session is not None:
                session.commit()
        except Exception:
            if session is not None:
                session.rollback()
            raise
        finally:
            self._session_depth -= 1
            if session is not None:
                self.detach()
                session.close()

    def attach(self, session) -> None:
        self._session = session

    def detach(self) -> None:
        self._session = None

    # -------------------------------------------------------------- 进度
    def refresh_cancel_flag(self, flag: bool) -> None:
        self._cancel_flag = flag

    def check_cancel(self, force_db_check: bool = False) -> None:
        """安全检查点。handler 应在每个耗时循环迭代处调用。"""
        if self._cancel_flag:
            raise JobCancelled("作业已被取消")
        if force_db_check:
            with self.db() as db:
                row = db.get(AsyncJob, self.job_id)
                if row is not None and row.cancel_requested:
                    self._cancel_flag = True
                    raise JobCancelled("作业已被取消")

    def progress(self, pct: float, stage: str = "", *, force: bool = False) -> None:
        """上报进度（0—1）。内部按变化幅度与时间双重节流。"""
        pct = max(0.0, min(1.0, float(pct)))
        now = time.monotonic()
        with self._lock:
            changed = abs(pct - self._last_progress) >= 0.01
            elapsed = (now - self._last_write) >= 0.5
            if not force and not (changed and elapsed):
                return
            self._last_progress = pct
            self._last_write = now
        self._write(progress=pct, stage=stage)

    def log(self, message: str, progress: float | None = None) -> None:
        self._write(progress=progress, stage=None, event="log", message=message)

    def _write(self, *, progress: float | None, stage: str | None,
               event: str = "progress", message: str = "",
               _retries: int = 3) -> None:
        """写进度与事件。

        硬性要求：**进度写失败绝不能影响作业本体**。因此：
        - 复用 handler 的会话（SAVEPOINT）以避免 SQLite 自死锁；
        - 遇到写锁竞争时退避重试，最终仍失败则降级为日志，不抛出。
        """
        for attempt in range(_retries):
            try:
                bound = self._session
                if bound is not None:
                    self._write_with(bound, progress, stage, event, message, savepoint=True)
                else:
                    with SessionLocal() as db:
                        self._write_with(db, progress, stage, event, message, savepoint=False)
                        db.commit()
                return
            except Exception as exc:  # pragma: no cover - 环境相关
                locked = "locked" in str(exc).lower()
                if attempt == _retries - 1:
                    logger.warning("作业 %s 进度写库失败（已降级为日志）：%s", self.job_id, exc)
                    return
                time.sleep(0.2 * (attempt + 1) if locked else 0.05)
                # 会话可能已进入 failed 状态，解绑后走独立连接重试
                if self._session is not None:
                    try:
                        self._session.rollback()
                    except Exception:
                        pass
                    self._session = None

    def _write_with(self, db, progress: float | None, stage: str | None,
                    event: str, message: str, *, savepoint: bool) -> None:
        ctx_manager = db.begin_nested() if savepoint else None
        if ctx_manager is None:
            self._apply(db, progress, stage, event, message)
            return
        with ctx_manager:
            self._apply(db, progress, stage, event, message)

    def _apply(self, db, progress: float | None, stage: str | None,
               event: str, message: str) -> None:
        row = db.get(AsyncJob, self.job_id)
        if row is None:
            return
        if progress is not None:
            row.progress = progress
        if stage:
            row.stage_text = stage
        row.heartbeat_at = _now()
        if event != "progress" or message:
            # 序号惰性对齐：首次写事件时读一次已有最大 seq，之后本地自增。
            # 从 0 重新计数会与「入队/开始」事件撞号，事件流的先后顺序就不可信了。
            # 惰性而非预读，是为了不依赖调用时机（进度可能在 handler 内外任意位置上报）。
            if self._seq == 0:
                self._seq = int(db.execute(
                    select(func.max(AsyncJobEvent.seq))
                    .where(AsyncJobEvent.job_id == self.job_id)
                ).scalar() or 0)
            self._seq += 1
            db.add(AsyncJobEvent(
                job_id=self.job_id, seq=self._seq, event=event, message=message[:500],
                progress=row.progress, actor=self.worker_id, at=_now(),
            ))
        db.flush()
        # 通知订阅者「有新事件」（数据库已写入，这里只做低延迟唤醒）。
        # 放在 flush 之后：先保证事件可见，再提示去读 —— 反序会让客户端读到空。
        _publish_event_hint(self.job_id, event)


# ------------------------------------------------------------------ 引擎
class TaskEngine:
    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[JobContext], Any]] = {}
        self._defaults: dict[str, dict[str, Any]] = {}
        self._pool: ThreadPoolExecutor | None = None
        self._dispatcher: threading.Thread | None = None
        self._sweeper: threading.Thread | None = None
        self._stop = threading.Event()
        self._claim_lock = threading.Lock()
        self._inflight: set[int] = set()
        self._inflight_lock = threading.Lock()
        self.worker_id = f"{os.getpid()}-{uuid.uuid4().hex[:4]}"
        self.started = False

    # ------------------------------------------------------------ 注册
    def register(self, job_type: str, handler: Callable[[JobContext], Any], *,
                 default_timeout: int = 0, default_max_attempts: int = 2,
                 description: str = "") -> None:
        self._handlers[job_type] = handler
        self._defaults[job_type] = {
            "timeout": default_timeout,
            "max_attempts": default_max_attempts,
            "description": description,
        }

    def registered_types(self) -> list[str]:
        return sorted(self._handlers)

    # ------------------------------------------------------------ 生命周期
    def ensure_started(self) -> None:
        """幂等启动。人生的第一次 submit 会自动拉起引擎。"""
        if not self.started:
            self.start(workers=settings_workers())

    def start(self, workers: int = 2) -> None:
        if self.started:
            return
        self._stop.clear()
        self._pool = ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="sh-job")
        self.recover_orphans()
        self._dispatcher = threading.Thread(target=self._dispatch_loop, name="sh-dispatch", daemon=True)
        self._dispatcher.start()
        self._sweeper = threading.Thread(target=self._sweep_loop, name="sh-sweep", daemon=True)
        self._sweeper.start()
        self.started = True
        logger.info("作业引擎启动：%d 个 Worker，已注册 %d 类作业（%s）",
                    workers, len(self._handlers), ", ".join(self.registered_types()))

    def shutdown(self, grace_sec: float = 10.0) -> None:
        if not self.started:
            return
        logger.info("作业引擎关闭中：停止接单，请求在跑作业取消…")
        self._stop.set()
        # 请求取消所有在跑作业（抢占式终止会导致脏数据，故走请求式取消）
        try:
            with SessionLocal() as db:
                db.execute(update(AsyncJob).where(AsyncJob.status == "running")
                           .values(cancel_requested=True, stage_text="服务关闭，作业已请求取消"))
                db.commit()
        except Exception:  # pragma: no cover
            logger.warning("关闭时请求取消在跑作业失败", exc_info=True)

        deadline = time.monotonic() + grace_sec
        while time.monotonic() < deadline:
            with self._inflight_lock:
                pending = len(self._inflight)
            if pending == 0:
                break
            time.sleep(0.2)
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
        self.started = False
        logger.info("作业引擎已关闭")

    # ------------------------------------------------------------ 提交
    def submit(self, db, *, job_type: str, payload: dict[str, Any] | None = None,
               title: str = "", priority: int = 50, dedup_key: str = "",
               ref_type: str = "", ref_id: int | None = None, ref_label: str = "",
               created_by: str = "", created_by_name: str = "",
               org_code: str = "", site_code: str = "",
               timeout_sec: int | None = None, max_attempts: int | None = None,
               note: str = "") -> AsyncJob:
        if job_type not in self._handlers:
            raise ValueError(f"未注册的作业类型：{job_type}（可用：{', '.join(self.registered_types())}）")
        defaults = self._defaults.get(job_type, {})
        # 兜底自启动：即使应用未走 lifespan（例如某些 ASGI 部署方式或测试客户端），
        # 也能保证「提交的作业一定有人执行」，避免作业静默堆积在队列里。
        self.ensure_started()

        # 幂等：同一 dedup_key 已有未终态作业 → 直接复用
        if dedup_key:
            existing = db.execute(
                select(AsyncJob).where(
                    AsyncJob.dedup_key == dedup_key,
                    AsyncJob.status.notin_(TERMINAL_STATUSES),
                ).order_by(AsyncJob.id.desc()).limit(1)
            ).scalar_one_or_none()
            if existing is not None:
                logger.info("作业幂等命中：dedup_key=%s → 复用 %s", dedup_key, existing.code)
                return existing

        job = AsyncJob(
            code=_new_code(job_type),
            job_type=job_type,
            title=title or defaults.get("description") or job_type,
            status="queued",
            priority=priority,
            payload_json=json.dumps(payload or {}, ensure_ascii=False, default=str),
            ref_type=ref_type,
            ref_id=ref_id,
            ref_label=ref_label,
            dedup_key=dedup_key,
            timeout_sec=int(timeout_sec if timeout_sec is not None else defaults.get("timeout", 0)),
            max_attempts=int(max_attempts if max_attempts is not None else defaults.get("max_attempts", 2)),
            created_by=created_by,
            created_by_name=created_by_name,
            org_code=org_code,
            site_code=site_code,
            queued_at=_now(),
            stage_text="已入队，等待调度",
            note=note,
        )
        db.add(job)
        db.flush()
        db.add(AsyncJobEvent(job_id=job.id, seq=1, event="queued",
                             message=f"作业入队（{job.type_label}，优先级 {priority}）",
                             actor=created_by or "system", at=_now()))
        db.commit()
        _publish_event_hint(job.id, "queued")
        return job

    # ------------------------------------------------------------ 取消 / 重试
    def cancel(self, db, job_id: int, actor: str = "") -> AsyncJob:
        job = db.get(AsyncJob, job_id)
        if job is None:
            raise ValueError("作业不存在")
        if job.is_terminal:
            raise ValueError(f"作业已是终态（{job.status_label}），无法取消")
        job.cancel_requested = True
        if job.status == "queued":
            job.status = "cancelled"
            job.finished_at = _now()
            job.stage_text = "已取消（尚未开始执行）"
        else:
            job.stage_text = "取消请求已提交，等待安全检查点响应"
        db.add(AsyncJobEvent(job_id=job.id, seq=self._next_seq(db, job.id), event="cancel_requested",
                             message=f"取消请求（{actor or 'system'}）", actor=actor, at=_now(),
                             progress=job.progress))
        db.commit()
        return job

    def retry(self, db, job_id: int, actor: str = "") -> AsyncJob:
        job = db.get(AsyncJob, job_id)
        if job is None:
            raise ValueError("作业不存在")
        if not job.is_terminal:
            raise ValueError("作业尚未结束，无需重试")
        if job.status == "succeeded":
            raise ValueError("作业已成功，无需重试")
        if job.attempts >= job.max_attempts:
            # 允许人工显式提升重试上限（排障后手动重跑的场景）
            job.max_attempts = job.attempts + 1
        job.status = "queued"
        job.progress = 0.0
        job.stage_text = "已重新入队"
        job.error_text = ""
        job.error_detail = ""
        job.cancel_requested = False
        job.worker_id = ""
        job.started_at = ""
        job.finished_at = ""
        job.duration_sec = 0.0
        job.queued_at = _now()
        db.add(AsyncJobEvent(job_id=job.id, seq=self._next_seq(db, job.id), event="retry",
                             message=f"人工重试（第 {job.attempts + 1} 次尝试，操作人 {actor or 'system'}）",
                             actor=actor, at=_now()))
        db.commit()
        return job

    @staticmethod
    def _next_seq(db, job_id: int) -> int:
        cur = db.execute(select(func.max(AsyncJobEvent.seq)).where(AsyncJobEvent.job_id == job_id)).scalar()
        return int(cur or 0) + 1

    # ------------------------------------------------------------ 调度
    def _claim_next(self) -> int | None:
        """原子领取一个排队作业。返回作业 id。

        两种策略按方言切换，原因是它们的并发语义不同：

        - **PostgreSQL**：用 `SELECT ... FOR UPDATE SKIP LOCKED`。
          数据库帮我们"锁住这一行且跳过别人已锁的行"，多个 Worker 天然不撞车，
          也不需要本地锁配合 —— 这是 PG 上领取队列的标准做法。
        - **SQLite**：没有 SKIP LOCKED，改用「先查候选，再条件更新」的乐观并发。
          `UPDATE ... WHERE id=? AND status='queued'` 靠行级写锁把竞争收敛为
          rowcount=0/1；抢输的 Worker 下一轮重试即可。

        之所以不统一用乐观更新：在 PG 上，高并发时所有 Worker 都会读到同一行、
        再互相把 UPDATE 打回，形成无谓的写竞争；SKIP LOCKED 直接消除了这一现象。
        """
        with self._claim_lock:
            with SessionLocal() as db:
                if db.bind.dialect.name == "postgresql":
                    return self._claim_next_pg(db)
                return self._claim_next_generic(db)

    def _claim_next_pg(self, db) -> int | None:
        """PostgreSQL：FOR UPDATE SKIP LOCKED 原子领取。"""
        row = db.execute(
            select(AsyncJob.id)
            .where(AsyncJob.status == "queued")
            .order_by(AsyncJob.priority.asc(), AsyncJob.id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        ).scalar_one_or_none()
        if row is None:
            db.rollback()
            return None
        now = _now()
        db.execute(
            update(AsyncJob)
            .where(AsyncJob.id == row)
            .values(status="running", worker_id=self.worker_id,
                    started_at=now, heartbeat_at=now,
                    attempts=AsyncJob.attempts + 1,
                    stage_text="已领取，开始执行")
        )
        db.add(AsyncJobEvent(job_id=row, seq=self._next_seq(db, row), event="started",
                             message=f"Worker {self.worker_id} 开始执行（SKIP LOCKED 领取）",
                             actor=self.worker_id, at=now))
        db.commit()
        _publish_event_hint(row, "started")
        return int(row)

    def _claim_next_generic(self, db) -> int | None:
        """SQLite 等无 SKIP LOCKED 的方言：**读写分离**的乐观条件更新。

        这里有一个非常容易踩、且只在多进程并发下才暴露的 SQLite 陷阱：

        **不要在同一个事务里"先 SELECT 再 UPDATE"。**
        SQLAlchemy 的 Session 在执行第一条 SELECT 时就隐式开启事务（autobegin），
        此时 SQLite 处于 DEFERRED 模式（已持有读锁但要写时才申请写锁）。
        当另一个进程正好持有写锁时，这次"锁升级"会**立刻**返回 SQLITE_BUSY，
        而且**故意不等待 busy_timeout** —— SQLite 认为立即报错比死等更能避免死锁。
        现象就是：配了 busy_timeout=60s，却仍然秒失败 "database is locked"，
        4 个 Worker 并发领取时 5/16 的作业直接判失败。

        正确做法是把两个动作拆到**不同会话**：
        1) 用只读会话查候选（读完即结束，不持有写意图）；
        2) 用新会话执行 UPDATE —— 该事务的第一条语句就是写语句，
           写锁在语句开始时申请，此时 busy_timeout 正常生效，会等而不是立刻失败。

        另外加一层有限重试 + 抖动：即使仍偶发 BUSY，也只是稍后重试，
        不会把"基础设施争用"升级成"作业失败"。
        """
        candidate_id = None
        with SessionLocal() as reader:
            candidate_id = reader.execute(
                select(AsyncJob.id)
                .where(AsyncJob.status == "queued")
                .order_by(AsyncJob.priority.asc(), AsyncJob.id.asc())
                .limit(1)
            ).scalar_one_or_none()
        if candidate_id is None:
            return None

        last_error: Exception | None = None
        for attempt in range(5):
            now = _now()
            try:
                with WriterSessionLocal() as claim_db:
                    # 本事务的第一条语句就是 UPDATE：写锁申请会正常等待 busy_timeout
                    result = claim_db.execute(
                        update(AsyncJob)
                        .where(AsyncJob.id == int(candidate_id),
                               AsyncJob.status == "queued")
                        .values(status="running", worker_id=self.worker_id,
                                started_at=now, heartbeat_at=now,
                                attempts=AsyncJob.attempts + 1,
                                stage_text="已领取，开始执行")
                    )
                    if result.rowcount != 1:
                        claim_db.rollback()
                        return None      # 被别人抢走了：正常竞争结果
                    claim_db.add(AsyncJobEvent(
                        job_id=int(candidate_id),
                        seq=self._next_seq(claim_db, int(candidate_id)),
                        event="started",
                        message=f"Worker {self.worker_id} 开始执行",
                        actor=self.worker_id, at=now))
                    claim_db.commit()
                _publish_event_hint(int(candidate_id), "started")
                return int(candidate_id)
            except OperationalError as exc:
                last_error = exc
                if "locked" not in str(exc).lower():
                    raise
                # 抖动退避：多个 Worker 同时退避同一时长会再次撞车
                time.sleep(0.05 * (attempt + 1) + random.random() * 0.05)
            except Exception as exc:
                last_error = exc
                break
        if last_error is not None:
            logger.warning("领取作业失败（%d 次重试后放弃，本轮跳过）：%s",
                           attempt + 1, str(last_error)[:160])
        return None

    def _dispatch_loop(self) -> None:
        while not self._stop.is_set():
            try:
                with self._inflight_lock:
                    capacity = (self._pool._max_workers - len(self._inflight)) if self._pool else 0
                job_id = self._claim_next() if capacity > 0 else None
                if job_id is None:
                    self._stop.wait(0.4)
                    continue
                with self._inflight_lock:
                    self._inflight.add(job_id)
                self._pool.submit(self._run_wrapper, job_id)
            except Exception:  # pragma: no cover
                logger.exception("调度循环异常")
                self._stop.wait(1.0)

    def _sweep_loop(self) -> None:
        """回收僵死作业：心跳超过阈值仍在 running 的，标记为 failed（可重试）。"""
        while not self._stop.is_set():
            self._stop.wait(30.0)
            if self._stop.is_set():
                break
            try:
                with SessionLocal() as db:
                    stale = list(db.execute(
                        select(AsyncJob).where(AsyncJob.status == "running")
                    ).scalars())
                    now = datetime.now()
                    for job in stale:
                        if job.worker_id in ("", self.worker_id):
                            continue
                        if not job.heartbeat_at:
                            continue
                        try:
                            beat = datetime.fromisoformat(job.heartbeat_at)
                        except ValueError:
                            continue
                        if (now - beat).total_seconds() > 180:
                            job.status = "failed"
                            job.error_text = "Worker 心跳丢失（进程可能异常退出），作业已回收"
                            job.finished_at = _now()
                            job.stage_text = "已回收：Worker 失联"
                            db.add(AsyncJobEvent(job_id=job.id, seq=self._next_seq(db, job.id),
                                                 event="error",
                                                 message="心跳超时，判定 Worker 失联并回收作业",
                                                 actor="sweeper", at=_now()))
                            logger.warning("回收僵死作业 %s（worker=%s）", job.code, job.worker_id)
                    db.commit()
            except Exception:  # pragma: no cover
                logger.exception("僵尸作业回收异常")

    # ------------------------------------------------------------ 恢复
    def recover_orphans(self, *, force: bool = False) -> dict[str, int]:
        """启动时恢复：回收「确实已经死掉」的 running 作业。

        **判定依据是心跳，而不是"处于 running"**。这是一个很容易写错、
        且只在多进程下暴露的缺陷：

        - 错误写法（无脑回收所有 running）：Worker B 启动时会把 Worker A
          正在执行的作业一起标成失败 —— A 白跑一遍、B 拿到脏状态，
          用户看到"作业莫名失败又重跑了"。
        - 正确写法：只有 `heartbeat_at` 超过 `job_heartbeat_stale_sec` 的
          running 作业才判定为失联（说明执行它的进程已经死了）。
          心跳新鲜的作业属于**活着**的兄弟进程，必须放过。

        `force=True` 仅用于「确定没有其它实例在跑」的场景（单进程测试、维护窗口）。

        返回 {"recovered": 回收数, "pending": 排队数, "skipped_live": 放过的活作业数}。
        """
        from app.core.config import settings as _settings

        threshold = max(60, int(_settings.job_heartbeat_stale_sec))
        cutoff = (datetime.now() - timedelta(seconds=threshold)).isoformat(timespec="seconds")
        recovered = 0
        skipped_live = 0
        # 多进程同时启动时，多个进程会并发回收孤儿作业 —— 必须用写事务会话，
        # 否则"读 running 列表 + 逐个改状态"会互相锁升级失败，回收结果残缺。
        with WriterSessionLocal() as db:
            running = list(db.execute(
                select(AsyncJob).where(AsyncJob.status == "running")
            ).scalars())
            for job in running:
                if not force:
                    hb = job.heartbeat_at or ""
                    # 心跳新鲜 = 执行它的进程还活着，不能碰
                    if hb and hb >= cutoff:
                        skipped_live += 1
                        continue
                    # 心跳为空说明是旧版本写入的历史数据，按失联处理
                job.status = "failed"
                job.error_text = (
                    "执行该作业的进程已失联（心跳超时），作业被回收，可重试"
                    if not force else "维护模式强制回收（作业执行期间进程被重启）"
                )
                job.stage_text = "已回收：执行进程失联，可重试"
                job.finished_at = _now()
                db.add(AsyncJobEvent(job_id=job.id, seq=self._next_seq(db, job.id),
                                     event="error",
                                     message=job.error_text[:200], actor="recovery", at=_now()))
                recovered += 1
            queued = int(db.execute(
                select(func.count(AsyncJob.id)).where(AsyncJob.status == "queued")
            ).scalar() or 0)
            db.commit()
        if recovered:
            logger.warning("启动恢复：%d 个失联作业已回收（可重试）", recovered)
        if skipped_live:
            logger.info("启动恢复：跳过 %d 个 running 作业（心跳新鲜，属于存活实例，未回收）",
                        skipped_live)
        if queued:
            logger.info("启动恢复：%d 个排队作业将自动继续调度", queued)
        return {"recovered": recovered, "pending": queued, "skipped_live": skipped_live}

    # ------------------------------------------------------------ 执行
    def _run_wrapper(self, job_id: int) -> None:
        try:
            self._execute(job_id)
        finally:
            with self._inflight_lock:
                self._inflight.discard(job_id)

    def _execute(self, job_id: int) -> None:
        with SessionLocal() as db:
            job = db.get(AsyncJob, job_id)
            if job is None:
                return
            job_type = job.job_type
            timeout_sec = job.timeout_sec
            attempts = job.attempts
            max_attempts = job.max_attempts
            code = job.code
            payload_raw = job.payload_json
        ctx = JobContext(job_id, self.worker_id)
        try:
            ctx.payload = json.loads(payload_raw or "{}")
        except Exception:
            ctx.payload = {}

        handler = self._handlers.get(job_type)
        started = time.monotonic()
        watchdog: threading.Timer | None = None
        timed_out = threading.Event()

        if timeout_sec and timeout_sec > 0:
            def _on_timeout() -> None:
                timed_out.set()
                # 请求式取消：让 handler 在检查点退出，而不是硬杀线程
                try:
                    with SessionLocal() as db:
                        row = db.get(AsyncJob, job_id)
                        if row is not None:
                            row.cancel_requested = True
                            row.stage_text = f"已超过超时上限 {timeout_sec}s，请求中止"
                            db.commit()
                except Exception:  # pragma: no cover
                    pass
            watchdog = threading.Timer(timeout_sec, _on_timeout)
            watchdog.daemon = True
            watchdog.start()

        ctx.progress(0.01, "开始执行", force=True)
        result: Any = None
        status = "succeeded"
        error_text = ""
        error_detail = ""
        non_retryable = False
        try:
            if handler is None:
                raise RuntimeError(f"未注册的作业类型：{job_type}")
            result = handler(ctx)
            if timed_out.is_set():
                status, error_text = "timeout", f"作业超过超时上限 {timeout_sec}s"
            elif ctx._cancel_flag:
                status, error_text = "cancelled", "作业被取消"
        except JobCancelled as exc:
            status, error_text = "cancelled", str(exc) or "作业被取消"
        except JobTimeout as exc:
            status, error_text = "timeout", str(exc) or "作业超时"
        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}"
            error_detail = traceback.format_exc()[-4000:]
            status = "failed"
            non_retryable = bool(getattr(exc, "non_retryable", False))
            logger.exception("作业 %s 执行失败%s", code, "（业务规则失败，不重试）" if non_retryable else "")
        finally:
            if watchdog is not None:
                watchdog.cancel()

        duration = round(time.monotonic() - started, 3)

        # 失败自动重试：仅在「未达上限 + 非取消/超时 + 错误本身可重试」时进行
        auto_retry = False
        if status == "failed" and attempts < max_attempts and not non_retryable:
            auto_retry = True

        # 终态回写用写事务会话：这里同样是"先读行再改状态"，普通会话会踩
        # SQLite 锁升级的立即失败，导致作业明明跑完了却写不回终态。
        with WriterSessionLocal() as db:
            row = db.get(AsyncJob, job_id)
            if row is None:
                return
            if auto_retry:
                row.status = "queued"
                row.progress = 0.0
                row.stage_text = f"第 {attempts} 次尝试失败，自动重试中（上限 {max_attempts}）"
                row.error_text = error_text
                row.error_detail = error_detail
                row.queued_at = _now()
                db.add(AsyncJobEvent(job_id=job_id, seq=self._next_seq(db, job_id),
                                     event="retry",
                                     message=f"自动重试：{error_text}", actor="engine",
                                     at=_now(), progress=0.0))
                logger.warning("作业 %s 第 %d 次尝试失败，自动重试：%s", code, attempts, error_text)
            else:
                if status == "failed" and attempts >= max_attempts:
                    row.status = "dead"
                else:
                    row.status = status
                row.progress = 1.0 if status == "succeeded" else row.progress
                row.finished_at = _now()
                row.duration_sec = duration
                row.error_text = error_text
                row.error_detail = error_detail
                row.stage_text = {
                    "succeeded": "执行完成",
                    "failed": "执行失败",
                    "dead": f"重试次数已耗尽（{attempts}/{max_attempts}）",
                    "cancelled": "已取消",
                    "timeout": "已超时",
                }.get(row.status, row.status)
                if result is not None:
                    try:
                        row.result_json = json.dumps(result, ensure_ascii=False, default=str)[:200000]
                    except Exception:
                        row.result_json = "{}"
                db.add(AsyncJobEvent(job_id=job_id, seq=self._next_seq(db, job_id),
                                     event="finished" if row.status == "succeeded" else "error",
                                     message=f"{row.stage_text}（耗时 {duration}s）" + (f" · {error_text}" if error_text else ""),
                                     actor=self.worker_id, at=_now(), progress=row.progress))
            db.commit()
            # 终态是前端最关心的一次状态变化：必须立刻推送，不能等下次轮询
            _publish_event_hint(job_id, row.status)

    # ------------------------------------------------------------ 查询辅助
    def stats(self) -> dict[str, Any]:
        with SessionLocal() as db:
            rows = db.execute(
                select(AsyncJob.status, func.count(AsyncJob.id)).group_by(AsyncJob.status)
            ).all()
        by_status = {str(s): int(c) for s, c in rows}
        with self._inflight_lock:
            inflight = len(self._inflight)
        return {
            "by_status": by_status,
            "queued": by_status.get("queued", 0),
            "running": by_status.get("running", 0),
            "inflight_in_process": inflight,
            "workers": self._pool._max_workers if self._pool else 0,
            "registered_types": self.registered_types(),
            "worker_id": self.worker_id,
            "started": self.started,
        }

    def wait(self, job_id: int, timeout: float = 300.0, poll: float = 0.15) -> AsyncJob:
        """阻塞等待作业结束。仅测试与脚本使用，禁止在请求路径中调用。"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with SessionLocal() as db:
                job = db.get(AsyncJob, job_id)
                if job is None:
                    raise ValueError("作业不存在")
                if job.is_terminal:
                    db.expunge(job)
                    return job
            time.sleep(poll)
        raise TimeoutError(f"等待作业 {job_id} 超时（{timeout}s）")


TASKS = TaskEngine()
