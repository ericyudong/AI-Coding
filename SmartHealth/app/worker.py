"""独立作业 Worker 进程入口。

用法：

    # 单进程（一个进程里 4 个并发作业）
    python -m app.worker

    # 指定并发度
    python -m app.worker --concurrency 8

    # 起 3 个进程各 4 并发（生产常见：进程隔离 + 独立扩缩）
    python -m app.worker --processes 3

为什么需要独立 Worker 进程（而不是全靠 API 进程内跑）：
1. **隔离**：训练/推理吃满 CPU 会让 API 响应变慢甚至超时。进程隔离后 API 的
   P99 不再受作业负载影响 —— 这在临床上不是"优化"，是"能不能用"的问题。
2. **可独立扩缩**：忙时只加 Worker 副本，API 副本数不动。
3. **生命周期对齐**：Worker 需要长生命周期以复用特征缓存与模型权重；
   API 进程要能随时滚动重启。两者的重启节奏天然不同。

一个必须知道的坑：
Worker 进程**不启动**周期任务调度（那由 API 进程负责），否则多进程会让
每个周期任务被触发 N 次。即使调度器有 leader-only 锁兜底，也没必要浪费这次竞争。
本入口通过 `scheduler_enabled` 的进程内禁用（`start_scheduler` 不被调用）来体现。
"""

from __future__ import annotations

import argparse
import logging
import multiprocessing
import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | worker[%(process)d] | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("smarthealth.worker")


def _install_signal_handlers(stop_flag: dict) -> None:
    """优雅关闭：收到 SIGTERM/SIGINT 时置标志，交由主循环 drain。

    不能直接 `os._exit`：正在执行的作业落库到一半被硬杀会产生脏数据
    （作业停在 running、事件流断在半截）。必须给引擎一个"停单 + 等在跑作业"的窗口。
    """

    def _handler(signum, _frame):
        if stop_flag.get("stopping"):
            logger.warning("再次收到信号 %s，强制退出", signum)
            os._exit(1)
        stop_flag["stopping"] = True
        logger.info("收到信号 %s，开始优雅关闭（停止领取新作业，等待在跑作业结束）…", signum)

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _handler)
        except (ValueError, OSError):  # pragma: no cover - Windows/非主线程
            pass


def run_worker(*, concurrency: int, drain_seconds: int, once: bool = False) -> int:
    """启动一个 Worker 进程并阻塞直到收到停止信号。"""
    from app.core.config import settings
    from app.core.database import init_db
    from app.core.locks import lock_status
    from app.core.tasks import TASKS
    from app.services import job_service  # noqa: F401 —— 导入即注册全部作业 handler

    started = time.time()
    migration = init_db()

    logger.info("Worker 启动：pid=%d concurrency=%d backend=%s",
                os.getpid(), concurrency, settings.db_backend)
    if migration.get("applied"):
        logger.info("Worker 抢到迁移权并应用了 %d 条迁移（说明本进程先于 API 启动）",
                    len(migration["applied"]))
    lock_info = lock_status()
    logger.info("分布式锁后端：%s（Redis %s）", lock_info["backend"],
                "已接入" if lock_info["redis"].get("connected") else "未接入/不可用")

    recovery = TASKS.recover_orphans()
    if recovery.get("recovered") or recovery.get("pending"):
        logger.info("启动恢复：回收中断 %d 个、待继续排队 %d 个",
                    recovery.get("recovered", 0), recovery.get("pending", 0))

    TASKS.start(workers=concurrency)
    logger.info("作业引擎就绪（worker_id=%s，P95 领取延迟取决于队列扫描间隔）",
                TASKS.worker_id)

    if once:
        # --once：把当前队列跑到空就退出。CI / 批处理 / 补跑场景用。
        logger.info("--once 模式：将把队列跑到空后退出")
        idle_since = time.time()
        while time.time() - idle_since < 5.0:
            stats = TASKS.stats()
            if (stats.get("queued") or 0) == 0 and (stats.get("running") or 0) == 0:
                if time.time() - idle_since > 2.0:
                    break
            else:
                idle_since = time.time()
            time.sleep(0.5)
        TASKS.shutdown(grace_sec=float(drain_seconds))
        logger.info("--once 模式完成，退出")
        return 0

    stop_flag: dict = {}
    _install_signal_handlers(stop_flag)
    logger.info("Worker 进入常驻状态（%.2fs 就绪）。发送 SIGTERM/SIGINT 可优雅停止。",
                time.time() - started)
    try:
        while not stop_flag.get("stopping"):
            time.sleep(1.0)
    except KeyboardInterrupt:  # pragma: no cover
        pass

    logger.info("开始 drain：最多等待 %ds 让在跑作业落地…", drain_seconds)
    TASKS.shutdown(grace_sec=float(drain_seconds))
    logger.info("Worker 已停止（本次进程内共执行 %d 个作业）",
                TASKS.stats().get("completed_total", 0))
    return 0


def _spawn(procs: list[multiprocessing.Process], concurrency: int, drain: int) -> multiprocessing.Process:
    p = multiprocessing.Process(target=run_worker,
                                kwargs={"concurrency": concurrency, "drain_seconds": drain},
                                name=f"smarthealth-worker-{len(procs)}")
    p.start()
    procs.append(p)
    return p


def main() -> int:
    parser = argparse.ArgumentParser(description="SmartHealth 独立作业 Worker")
    parser.add_argument("--concurrency", type=int, default=0,
                        help="单进程内并发作业数（默认取配置 worker_concurrency=4）")
    parser.add_argument("--processes", type=int, default=1,
                        help="起几个 Worker 进程（默认 1）")
    parser.add_argument("--drain", type=int, default=0,
                        help="停止时等待在跑作业的秒数（默认取配置 worker_drain_seconds）")
    parser.add_argument("--once", action="store_true",
                        help="把当前队列跑到空后退出（CI/补跑用）")
    args = parser.parse_args()

    from app.core.config import settings

    concurrency = args.concurrency or max(1, int(settings.worker_concurrency))
    drain = args.drain or max(1, int(settings.worker_drain_seconds))

    if args.processes <= 1:
        return run_worker(concurrency=concurrency, drain_seconds=drain, once=args.once)

    logger.info("启动 %d 个 Worker 进程，每个并发 %d（合计并发 %d）",
                args.processes, concurrency, args.processes * concurrency)
    procs: list[multiprocessing.Process] = []
    for i in range(args.processes):
        p = _spawn(procs, concurrency, drain)
        logger.info("  Worker 进程 %d 已启动（pid=%d）", i + 1, p.pid)

    exit_code = 0
    try:
        for p in procs:
            p.join()
            if p.exitcode not in (0, None):
                exit_code = p.exitcode or 1
    except KeyboardInterrupt:
        logger.info("主进程收到中断，转发停止信号给子进程…")
        for p in procs:
            if p.is_alive():
                p.terminate()
        for p in procs:
            p.join(timeout=30)
    logger.info("全部 Worker 进程已退出（exit=%d）", exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
