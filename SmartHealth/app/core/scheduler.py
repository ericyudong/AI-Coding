"""周期任务调度（APScheduler）。

为什么商用系统必须有这一层：
演示系统只需要人点按钮；生产系统需要在无人值守时保住数据与服务的正确性 ——
边缘节点掉线要能自己发现、KPI 要能自己沉淀、令牌要能自己过期、队列积压要能自己报警。
这些都不该依赖「某个同事记得每天点一下」。

设计原则：
- **幂等**：周期任务可能因为进程重启而被重复触发，每个任务都必须可重复执行。
- **单实例执行（leader-only）**：多进程/多实例部署时，同一任务必须有且只有一个执行者。
  否则「清理过期令牌」会并发删除、「KPI 快照」会重复写、告警会重复响。
  实现方式不是选主，而是**每个任务各自抢一把分布式锁**（粒度更细、无需协调者，
  某台机器卡住也不影响其它任务的执行）。抢不到锁的实例安静跳过，属于正常路径。
- **不阻塞**：任务内含全表扫描时限制批量，避免长事务锁库。
- **可降级**：APScheduler 缺失时仅告警，不影响主服务启动（现场环境依赖不齐是常态）。
- **可观测**：每个任务的执行结果都落日志，异常不吞；跳过次数单独计数便于诊断。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select, update

from app.core.config import settings
from app.core.database import SessionLocal

logger = logging.getLogger("smarthealth.scheduler")

_scheduler = None


# ------------------------------------------------------------------ 任务实现
def task_edge_heartbeat() -> str:
    """边缘节点心跳检测：心跳超时的在线节点标记为 offline。

    没有这个任务，节点宕机后看板会一直显示「在线」——
    这类「假在线」在演示里无害，在交付现场会直接导致误判。
    """
    from app.models.edge import EdgeNode

    cutoff = (datetime.now() - timedelta(minutes=10)).isoformat(timespec="seconds")
    changed = 0
    with SessionLocal() as db:
        nodes = list(db.execute(
            select(EdgeNode).where(EdgeNode.status == "online")
        ).scalars())
        for node in nodes:
            if not node.last_heartbeat:
                continue
            if node.last_heartbeat < cutoff:
                node.status = "offline"
                node.note = (node.note or "")[:300] + f" [自动检测：心跳于 {cutoff} 前失联]"
                changed += 1
        if changed:
            db.commit()
    if changed:
        logger.warning("边缘节点心跳检测：%d 个节点超时已标记离线", changed)
    return f"offline_marked={changed}"


def task_kpi_snapshot() -> str:
    """每日 KPI 快照。按「当天已有则覆盖、没有则新增」保证幂等。"""
    from app.services import ops_service

    today = datetime.now().strftime("%Y-%m-%d")
    with SessionLocal() as db:
        row = ops_service.snapshot_kpi(db, snapshot_date=today)
        db.commit()
        return f"snapshot_date={row.snapshot_date} auroc={row.model_auroc}"


def task_queue_alert() -> str:
    """队列积压告警。积压意味着「用户在等」，必须被看见。"""
    from app.models.job import AsyncJob

    with SessionLocal() as db:
        queued = int(db.execute(
            select(func.count(AsyncJob.id)).where(AsyncJob.status == "queued")
        ).scalar() or 0)
        running = int(db.execute(
            select(func.count(AsyncJob.id)).where(AsyncJob.status == "running")
        ).scalar() or 0)
        oldest = db.execute(
            select(AsyncJob).where(AsyncJob.status == "queued").order_by(AsyncJob.id.asc()).limit(1)
        ).scalar_one_or_none()
    backlog_warn = max(1, int(settings.job_workers) * 4)
    if queued >= backlog_warn:
        logger.warning("作业队列积压：排队 %d、执行中 %d（Worker %d）。最旧作业：%s",
                       queued, running, settings.job_workers,
                       oldest.code if oldest else "-")
    return f"queued={queued} running={running}"


def task_cleanup_tokens() -> str:
    """清理过期刷新令牌与陈旧登录记录。保留窗口 7 天，避免表无限增长。"""
    from app.models.system import LoginAttempt, RefreshSession

    keep_after = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
    removed_sessions = 0
    removed_attempts = 0
    with SessionLocal() as db:
        expired = list(db.execute(
            select(RefreshSession).where(RefreshSession.expires_at != "",
                                         RefreshSession.expires_at < keep_after)
        ).scalars())
        for row in expired:
            db.delete(row)
            removed_sessions += 1
        old_attempts = list(db.execute(
            select(LoginAttempt).where(LoginAttempt.at != "", LoginAttempt.at < keep_after)
        ).scalars())
        for row in old_attempts:
            db.delete(row)
            removed_attempts += 1
        if removed_sessions or removed_attempts:
            db.commit()
    return f"sessions={removed_sessions} attempts={removed_attempts}"


def task_cleanup_jobs() -> str:
    """归档清理：终态作业的事件流只保留最近 5000 条，避免事件表无界增长。"""
    from app.models.job import AsyncJobEvent

    removed = 0
    with SessionLocal() as db:
        total = int(db.execute(select(func.count(AsyncJobEvent.id))).scalar() or 0)
        if total > 6000:
            cutoff_id = db.execute(
                select(AsyncJobEvent.id).order_by(AsyncJobEvent.id.desc())
                .offset(4000).limit(1)
            ).scalar()
            if cutoff_id:
                result = db.execute(
                    AsyncJobEvent.__table__.delete().where(AsyncJobEvent.id < int(cutoff_id))
                )
                removed = int(result.rowcount or 0)
                db.commit()
    return f"events_removed={removed}"


def task_stale_job_sweep() -> str:
    """回收心跳过期的执行中作业（跨进程场景；同进程的僵死由引擎自带 sweeper 处理）。"""
    from app.core.tasks import TASKS

    threshold = max(60, int(settings.job_heartbeat_stale_sec))
    cutoff = (datetime.now() - timedelta(seconds=threshold)).isoformat(timespec="seconds")
    engine_worker = TASKS.worker_id
    recovered = 0
    with SessionLocal() as db:
        result = db.execute(
            update(__job_table())
            .where(__job_table().c.status == "running",
                   __job_table().c.worker_id != engine_worker,
                   __job_table().c.heartbeat_at != "",
                   __job_table().c.heartbeat_at < cutoff)
            .values(status="failed",
                    error_text=f"心跳超过 {threshold}s 未更新，判定 Worker 失联并回收",
                    stage_text="已回收：Worker 失联",
                    finished_at=datetime.now().isoformat(timespec="seconds"),
                    cancel_requested=False)
        )
        recovered = int(result.rowcount or 0)
        if recovered:
            db.commit()
    if recovered:
        logger.warning("回收 %d 个心跳失联的执行中作业", recovered)
    return f"recovered={recovered}"


def _job_table():
    from app.models.job import AsyncJob

    return AsyncJob.__table__


# ------------------------------------------------------------------ 注册与生命周期
def _register(sched) -> None:
    from apscheduler.triggers.interval import IntervalTrigger

    jobs = [
        ("edge_heartbeat", task_edge_heartbeat, 120, "边缘节点心跳检测"),
        ("queue_alert", task_queue_alert, 60, "作业队列积压监测"),
        ("stale_job_sweep", task_stale_job_sweep, 90, "失联作业回收"),
        ("cleanup_tokens", task_cleanup_tokens, 3600, "过期令牌清理"),
        ("cleanup_jobs", task_cleanup_jobs, 1800, "作业事件归档"),
        ("kpi_snapshot", task_kpi_snapshot, 1800, "KPI 快照沉淀"),
    ]
    for job_id, func_, seconds, name in jobs:
        sched.add_job(
            _wrap(func_, name, job_id), trigger=IntervalTrigger(seconds=seconds),
            id=job_id, name=name, replace_existing=True,
            max_instances=1, coalesce=True, misfire_grace_time=60,
        )


def _wrap(func_, name, job_id: str = ""):
    """包装成「单实例执行」的周期任务。

    每个 tick 先抢 `smarthealth:scheduler:<job_id>` 的分布式锁：
    - 抢到 → 执行（多进程下只有一个实例能抢到，天然 leader-only）。
    - 抢不到 → 跳过本次，记 debug。**这不是异常**，是正常的多实例行为，
      所以不能打 warning 刷屏，否则多进程环境日志会被"跳过"淹没。
    """
    key = f"smarthealth:scheduler:{job_id or name}"

    def _runner():
        from app.core.locks import exclusive

        started = datetime.now()
        # 租约略大于最大可能执行时间；任务若真的执行超时，租约到期后下个 tick 由别人接手
        with exclusive(key, lease_seconds=max(120, settings.lock_lease_seconds),
                       note=f"scheduler:{job_id or name}") as got:
            if not got:
                _SKIP_COUNTER[job_id or name] = _SKIP_COUNTER.get(job_id or name, 0) + 1
                logger.debug("[周期任务] %s 本次跳过（其它实例持有执行权）", name)
                return
            try:
                detail = func_()
                logger.info("[周期任务] %s 完成：%s（%.2fs）",
                            name, detail, (datetime.now() - started).total_seconds())
            except Exception:
                logger.exception("[周期任务] %s 执行失败", name)
    return _runner


# 各任务被跳过的累计次数（多实例部署时用于确认 leader-only 生效）
_SKIP_COUNTER: dict[str, int] = {}


def start_scheduler() -> bool:
    """启动调度器。失败只告警，不阻断主服务（现场依赖不齐是常态）。"""
    global _scheduler
    if _scheduler is not None:
        return True
    if not getattr(settings, "scheduler_enabled", True):
        logger.info("周期任务调度已按配置关闭")
        return False
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        sched = BackgroundScheduler(timezone="Asia/Shanghai", daemon=True)
        _register(sched)
        sched.start()
        _scheduler = sched
        logger.info("周期任务调度已启动：%d 个任务", len(sched.get_jobs()))
        return True
    except Exception as exc:  # pragma: no cover - 环境相关
        logger.warning("周期任务调度启动失败（不影响主服务）：%s", exc)
        return False


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:  # pragma: no cover
            pass
        _scheduler = None
        logger.info("周期任务调度已停止")


def scheduler_status() -> dict:
    """返回形状恒定，不随运行状态变化。

    如果"未启动"时少返回 job_count，"已启动"时才返回，所有消费方都得写分支 ——
    这正是运维脚本最容易踩空的地方。
    """
    from app.core.locks import lock_status

    lock_info = lock_status()
    if _scheduler is None:
        return {"running": False, "job_count": 0, "jobs": [],
                "execution_mode": "leader-only",
                "lock_backend": lock_info["backend"],
                "skipped_by_others": dict(_SKIP_COUNTER),
                "note": "调度器未启动（可能是 lifespan 未执行，或 scheduler_enabled=false）"}
    try:
        jobs = [{"id": j.id, "name": j.name,
                 "next_run": j.next_run_time.isoformat(timespec="seconds") if j.next_run_time else None}
                for j in _scheduler.get_jobs()]
    except Exception:  # pragma: no cover
        jobs = []
    return {"running": True, "job_count": len(jobs), "jobs": jobs,
            "execution_mode": "leader-only",
            "lock_backend": lock_info["backend"],
            "skipped_by_others": dict(_SKIP_COUNTER),
            "note": ("多实例部署时每个任务仅由抢到锁的实例执行；"
                     "skipped_by_others 增长说明 leader-only 正在生效。")}


def run_now(job_id: str) -> str:
    """手工触发一个周期任务（排障与运维用）。"""
    mapping = {
        "edge_heartbeat": (task_edge_heartbeat, "边缘节点心跳检测"),
        "queue_alert": (task_queue_alert, "作业队列积压监测"),
        "stale_job_sweep": (task_stale_job_sweep, "失联作业回收"),
        "cleanup_tokens": (task_cleanup_tokens, "过期令牌清理"),
        "cleanup_jobs": (task_cleanup_jobs, "作业事件归档"),
        "kpi_snapshot": (task_kpi_snapshot, "KPI 快照沉淀"),
    }
    entry = mapping.get(job_id)
    if entry is None:
        raise ValueError(f"未知周期任务：{job_id}（可选：{', '.join(mapping)}）")
    func_, name = entry
    # 手工触发同样抢锁：避免运维点按钮时正好和自动 tick 撞车导致重复执行
    from app.core.locks import exclusive

    with exclusive(f"smarthealth:scheduler:{job_id}", lease_seconds=300,
                   wait_seconds=5.0, note="manual-run") as got:
        if not got:
            return f"{name}：未取得执行权（另一个实例正在执行，已跳过）"
        return func_()
