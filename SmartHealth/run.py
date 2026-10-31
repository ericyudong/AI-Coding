"""启动脚本：单进程 / 多进程两种部署形态。

    # 单进程（演示、小院内）：API + 作业 Worker 在同一进程
    python run.py

    # 多进程（生产）：N 个 API worker + 独立作业 Worker 进程
    python run.py --workers 2
        → 等价于手动执行：
            uvicorn app.main:app --workers 2          （workers_in_api 自动为 false）
            python -m app.worker --processes 1        （独立作业进程）

    # 指定端口 / 热重载
    python run.py --port 8100 --reload

部署形态的判断规则（写在这里，避免运维靠记忆）：
- `--workers N`（N>1）或多进程 uvicorn：API 进程内**不**跑作业 Worker，
  因为每个 API 副本都起 Worker 会导致并发度翻倍、心跳互扰、关闭互等。
- 单进程：API 与 Worker 同进程，部署最简，适合演示与小规模院内。

首次运行若数据库为空，请先执行：
    python -m app.seed --reset
"""

from __future__ import annotations

import argparse
import multiprocessing
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import settings  # noqa: E402


def _print_banner(host: str, port: int, api_workers: int) -> None:
    mode = "单进程(API+Worker)" if api_workers <= 1 else f"多进程({api_workers} API + 独立 Worker)"
    print("=" * 70)
    print(f"  {settings.app_name}")
    print(f"  部署形态：{mode}")
    print(f"  接口文档：http://{host}:{port}/docs")
    print(f"  探针/指标：http://{host}:{port}/healthz  /readyz  /metrics")
    print(f"  前端控制台：cd frontend && node server.js")
    print(f"  数据库后端：{settings.db_backend}")
    print("=" * 70)


def run_single(host: str, port: int, reload: bool) -> None:
    """单进程：API 与 Worker 同进程（workers_in_api=True）。"""
    os.environ.setdefault("SMARTHEALTH_WORKERS_IN_API", "true")
    import uvicorn

    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


def run_multi(host: str, port: int, api_workers: int, job_workers: int,
              job_concurrency: int) -> int:
    """多进程：N 个 API 进程（不含 Worker）+ 独立作业 Worker 进程池。

    用 subprocess 而非 multiprocessing.fork：uvicorn 的多进程模式自己管理
    子进程与端口共享，外部再 fork 一层容易在 Windows 上出问题（无 fork）。
    """
    env = dict(os.environ)
    env["SMARTHEALTH_WORKERS_IN_API"] = "false"   # API 进程不带作业 Worker

    api_cmd = [sys.executable, "-m", "uvicorn", "app.main:app",
               "--host", host, "--port", str(port), "--workers", str(api_workers)]
    job_cmd = [sys.executable, "-m", "app.worker",
               "--processes", str(job_workers), "--concurrency", str(job_concurrency)]

    print(f"  启动 API：{' '.join(api_cmd[1:])}")
    print(f"  启动 Worker：{' '.join(job_cmd[1:])}")
    api_proc = subprocess.Popen(api_cmd, env=env)
    job_proc = subprocess.Popen(job_cmd, env=env)

    procs = [("api", api_proc), ("worker", job_proc)]

    def _shutdown(_signum=None, _frame=None):
        print("\n收到停止信号，转发给子进程（先停 API 接单，再等 Worker drain）…")
        for name, p in procs:
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
        for name, p in procs:
            try:
                p.wait(timeout=40)
            except Exception:
                p.kill()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _shutdown)
        except (ValueError, OSError):  # pragma: no cover
            pass

    try:
        while True:
            for name, p in procs:
                code = p.poll()
                if code is not None:
                    print(f"[{name}] 进程退出（exit={code}），停止整个栈")
                    _shutdown()
                    return code or 1
            time.sleep(1.0)
    except KeyboardInterrupt:
        _shutdown()
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="SmartHealth 服务启动器")
    parser.add_argument("--host", default=settings.backend_host)
    parser.add_argument("--port", type=int, default=settings.backend_port)
    parser.add_argument("--reload", action="store_true", help="代码热重载（仅单进程可用）")
    parser.add_argument("--workers", type=int, default=1,
                        help="API 进程数。>1 时自动切换为多进程形态（API 不再内置作业 Worker）")
    parser.add_argument("--job-workers", type=int, default=1,
                        help="独立作业 Worker 进程数（仅多进程形态生效）")
    parser.add_argument("--job-concurrency", type=int, default=0,
                        help="每个作业 Worker 进程内的并发数（默认取配置）")
    args = parser.parse_args()

    if args.reload and args.workers > 1:
        parser.error("--reload 与 --workers>1 不能同时使用（热重载只支持单进程）")

    concurrency = args.job_concurrency or max(1, int(settings.worker_concurrency))
    _print_banner(args.host, args.port, args.workers)

    if args.workers <= 1:
        run_single(args.host, args.port, args.reload)
        return 0
    return run_multi(args.host, args.port, args.workers, args.job_workers, concurrency)


if __name__ == "__main__":
    raise SystemExit(main())
