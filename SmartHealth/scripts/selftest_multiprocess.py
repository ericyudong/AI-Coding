"""多进程 Worker 真实并发验证（起多个真实进程抢同一队列）。

为什么必须用真实进程而不是多线程/模拟：
「多进程领取是否重复」这件事的失败模式恰恰藏在**进程边界**上 ——
本地线程锁在跨进程时完全无效、SQLite 写锁与 PG 行锁的行为不同、
`recover_orphans` 会把兄弟进程的作业误杀。这些都只有在真实多进程下才暴露。

验证四件事：
1. **不重复执行**：每个作业恰好被领取一次（attempts==1），无"跑两遍"。
2. **真实并发分担**：作业被 ≥2 个不同 worker_id 领取（证明不是单进程包办）。
3. **不误杀兄弟**：心跳新鲜的 running 作业不被启动时的 recover_orphans 回收。
4. **全部落地**：所有作业进入终态且成功，结果与事件流完整。

    python scripts/selftest_multiprocess.py
    python scripts/selftest_multiprocess.py --processes 4 --jobs 16
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------- 测试库隔离
# 必须在 import app.* 之前把 DATABASE_URL 指到独立的临时库。
#
# 为什么必须隔离：
# 1) 本机常常同时跑着在线服务（API + 内嵌 Worker + 周期任务）。它们与测试共用
#    同一个 SQLite 文件时，SQLite 的**单写者**特性会让所有写入串行排队；
#    busy_timeout 一等到就是几十秒，测试会"看起来卡死"。
# 2) 更要紧的是正确性：在线服务的内嵌 Worker 会**抢走测试投递的作业**，
#    于是"多进程是否重复执行"这个断言就失去了意义 —— 它测的是一个混合环境，
#    而不是被测对象本身。
# 3) 隔离后测试结果可复现：不受在线服务负载与调度周期影响。
_TEST_DB = Path(os.environ.get("SMARTHEALTH_TEST_DB")
                or (ROOT / "data" / "test_multiprocess.db"))
_MAIN_DB = ROOT / "data" / "smarthealth.db"

# **只在当前用 SQLite 时才切独立库**。
# 如果外部已经显式配了 PostgreSQL（CI 的生产形态），就**必须**用它 ——
# 否则这个"多进程并发验证"会悄悄跑在 SQLite 上，而 SQLite 的并发语义
# （单写者 / 无 SKIP LOCKED）与 PG 完全两回事，等于门禁没测到生产路径。
# 用 PG 时测试会在同一库里创建并清理自己的作业，因此 CI 里应让测试串行执行。
_EXISTING = os.environ.get("SMARTHEALTH_DATABASE_URL", "")
_USE_EXISTING = _EXISTING.lower().startswith(("postgresql", "postgres"))
if _USE_EXISTING:
    _TEST_DB = None
    print(f"多进程测试将使用已配置的 PostgreSQL（不再切独立 SQLite 库）")
else:
    _TEST_DB.parent.mkdir(parents=True, exist_ok=True)
    if not _TEST_DB.exists():
        if _MAIN_DB.exists():
            import shutil as _shutil

            _shutil.copy2(_MAIN_DB, _TEST_DB)   # 复制一份，带上演示切片数据
            for suffix in ("-wal", "-shm"):
                side = Path(str(_MAIN_DB) + suffix)
                if side.exists():
                    _shutil.copy2(side, Path(str(_TEST_DB) + suffix))
        else:
            print("提示：未找到演示库，测试将使用空库（请先执行 python -m app.seed --reset）")
    os.environ["SMARTHEALTH_DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
# 测试自己要跑 Worker，调度器关掉以减少无关写入
os.environ.setdefault("SMARTHEALTH_SCHEDULER_ENABLED", "false")

PASS = 0
FAIL = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [ OK ] {label}" + (f"  —— {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {label}  {detail}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--processes", type=int, default=3, help="并发 Worker 进程数")
    parser.add_argument("--jobs", type=int, default=12, help="投递的作业数")
    parser.add_argument("--concurrency", type=int, default=2, help="每进程内并发")
    parser.add_argument("--timeout", type=int, default=420)
    args = parser.parse_args()

    print("=" * 78)
    print(f"  多进程 Worker 真实并发验证（{args.processes} 进程 × {args.concurrency} 并发，"
          f"{args.jobs} 个作业）")
    print("=" * 78)

    from app.core.config import settings
    from app.core.database import SessionLocal, init_db
    from app.core.tasks import TASKS
    from app.models.asset import Slide
    from app.models.job import AsyncJob, AsyncJobEvent
    from sqlalchemy import func, select

    init_db()
    from app.services import job_service  # noqa: F401

    print(f"\n[0] 环境")
    print(f"  数据库后端：{settings.db_backend}")
    print(f"  测试库：{_TEST_DB if _TEST_DB is not None else '（使用已配置的 PostgreSQL）'}")
    print(f"  心跳失联阈值：{settings.job_heartbeat_stale_sec}s")

    # 断言的边界：只统计本次投递的作业（用 unique dedup 前缀隔离历史数据）
    run_tag = f"mp{int(time.time())}"
    db = SessionLocal()
    try:
        slides = list(db.execute(select(Slide).limit(args.jobs)).scalars())
        if len(slides) < 2:
            print("  [FAIL] 切片数据不足，请先执行 python -m app.seed --reset")
            return 1
        # 为保证作业数充足，必要时重复用同一批切片（dedup_key 不同即可各自成单）
        slide_ids: list[int] = []
        while len(slide_ids) < args.jobs:
            slide_ids.extend([s.id for s in slides])
        slide_ids = slide_ids[: args.jobs]

        print(f"\n[1] 投递作业（tag={run_tag}）")
        job_ids: list[int] = []
        for i, sid in enumerate(slide_ids):
            job = job_service.submit_precompute(
                db, slide_ids=[sid], force=True, actor="mp-test",
                actor_name="多进程验证",
            )
            # force 的 dedup_key 会因为 slide 相同而复用；手工打散，确保 N 个独立作业
            job.dedup_key = f"{run_tag}:{i}"
            job.payload_json = json.dumps(
                {"slide_ids": [sid], "force": True, "actor": "mp-test"}, ensure_ascii=False)
            job.status = "queued"
            job.progress = 0.0
            job.attempts = 0
            job.worker_id = ""
            job.started_at = ""
            job.finished_at = ""
            job.error_text = ""
            db.add(job)
            db.flush()
            job_ids.append(job.id)
        db.commit()
        print(f"  已投递 {len(job_ids)} 个独立作业: {job_ids[:6]}{'…' if len(job_ids) > 6 else ''}")

        # 清空本地引擎队列（本进程不参与执行，只作协调者）
        TASKS.shutdown(grace_sec=1.0)

        print(f"\n[2] 启动 {args.processes} 个真实 Worker 进程抢同一队列")
        env = dict(os.environ)
        env["SMARTHEALTH_WORKERS_IN_API"] = "false"
        # 子进程必须用**同一个**库，否则测的就不是同一队列了
        if _TEST_DB is not None:
            env["SMARTHEALTH_DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
        env["SMARTHEALTH_SCHEDULER_ENABLED"] = "false"
        procs = []
        for i in range(args.processes):
            cmd = [sys.executable, "-m", "app.worker",
                   "--concurrency", str(args.concurrency), "--once", "--drain", "15"]
            p = subprocess.Popen(cmd, cwd=str(ROOT), env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            procs.append(p)
            print(f"  Worker#{i + 1} 已启动 pid={p.pid}")
            time.sleep(0.6)   # 错开启动，让"启动即回收"的竞争真实发生

        deadline = time.time() + args.timeout
        while time.time() < deadline:
            remaining = db.execute(
                select(func.count(AsyncJob.id))
                .where(AsyncJob.id.in_(job_ids),
                       AsyncJob.status.in_(("queued", "running")))
            ).scalar()
            if int(remaining or 0) == 0:
                break
            time.sleep(1.5)

        print("\n[3] 等待 Worker 进程退出（drain）")
        for i, p in enumerate(procs):
            try:
                out, _ = p.communicate(timeout=90)
            except subprocess.TimeoutExpired:
                p.kill()
                out, _ = p.communicate()
            tail = [ln for ln in (out or "").splitlines() if "作业引擎" in ln or "已停止" in ln]
            print(f"  Worker#{i + 1} exit={p.returncode}"
                  + (f" | {tail[-1][-70:]}" if tail else ""))
            # 非零退出必须把完整输出摊出来：多进程下 Worker 的堆栈只存在于
            # 它自己的 stdout，不打印出来等于永远查不到根因。
            if p.returncode not in (0, None):
                print(f"  ---- Worker#{i + 1} 完整输出（exit={p.returncode}）----")
                for ln in (out or "").splitlines()[-60:]:
                    print(f"    {ln}")

        # ---------------------------------------------------------- 断言
        db.expire_all()
        jobs = list(db.execute(select(AsyncJob).where(AsyncJob.id.in_(job_ids))).scalars())

        print("\n[4] 校验结果")
        by_status: dict[str, int] = {}
        for j in jobs:
            by_status[j.status] = by_status.get(j.status, 0) + 1
        worker_ids = {j.worker_id for j in jobs if j.worker_id}
        attempts_hist: dict[int, int] = {}
        for j in jobs:
            attempts_hist[j.attempts] = attempts_hist.get(j.attempts, 0) + 1

        print(f"  状态分布：{by_status}")
        print(f"  领取者：{sorted(worker_ids)}")
        print(f"  尝试次数分布：{attempts_hist}")

        check("全部作业进入终态（无遗留 queued/running）",
              by_status.get("queued", 0) == 0 and by_status.get("running", 0) == 0,
              f"queued={by_status.get('queued', 0)} running={by_status.get('running', 0)}")
        check("全部作业执行成功",
              by_status.get("succeeded", 0) == len(job_ids),
              f"succeeded={by_status.get('succeeded', 0)}/{len(job_ids)}")

        # 核心断言：每个作业恰好领取一次 → 无重复执行
        check("无重复执行（每个作业 attempts 均为 1）",
              all(j.attempts == 1 for j in jobs),
              f"attempts 分布={attempts_hist}")

        # 核心断言：真实并发分担
        worker_procs = {w.split("-")[0] for w in worker_ids}
        check(f"作业被 ≥2 个不同 Worker 领取（证明真实并发分担）",
              len(worker_ids) >= 2,
              f"{len(worker_ids)} 个领取者：{sorted(worker_ids)}")
        check("领取者 worker_id 含进程号（可追溯到具体进程）",
              all(":" in w or "-" in w for w in worker_ids),
              f"样例={sorted(worker_ids)[:3]}")

        # ---------------------------------------------------------- PG 专用分支
        # 断言「真的走了 PostgreSQL 的 SKIP LOCKED 领取路径」。
        #
        # 为什么这条断言重要：staging 档的全部意义就是验证生产形态。
        # 如果因为驱动名/连接串写法导致 `db.bind.dialect.name` 不是 "postgresql"，
        # 代码会**静默**走通用（SQLite 那套）路径 —— 多进程测试照样能全绿，
        # 但 SKIP LOCKED 其实一次都没执行过，门禁就成了"绿灯下的空转"。
        # 这里用领取事件里的措辞把分支选择变成可验证事实。
        if settings.db_backend == "postgresql":
            started_msgs = [str(r) for (r,) in db.execute(
                select(AsyncJobEvent.message).where(
                    AsyncJobEvent.job_id.in_(job_ids), AsyncJobEvent.event == "started")
            ).all()]
            using_skip_locked = sum(1 for m in started_msgs if "SKIP LOCKED" in m)
            check("PostgreSQL 下确实走了 FOR UPDATE SKIP LOCKED 领取路径",
                  using_skip_locked > 0,
                  f"{using_skip_locked}/{len(started_msgs)} 条领取事件标注了 SKIP LOCKED")
        else:
            print(f"  [skip] 当前后端为 {settings.db_backend}，"
                  f"SKIP LOCKED 专属断言仅在 staging/release 档（PostgreSQL）生效")

        # 事件流完整性
        event_counts = dict(db.execute(
            select(AsyncJobEvent.job_id, func.count(AsyncJobEvent.id))
            .where(AsyncJobEvent.job_id.in_(job_ids))
            .group_by(AsyncJobEvent.job_id)
        ).all())
        incomplete = [jid for jid in job_ids if int(event_counts.get(jid, 0)) < 3]
        check("每个作业事件流完整（≥3 条：queued/started/finished）",
              not incomplete,
              f"不完整的作业：{incomplete[:5]}" if incomplete else
              f"平均 {sum(event_counts.values()) / max(len(event_counts), 1):.1f} 条/作业")

        seq_ok = True
        for jid in job_ids[:5]:
            seqs = [int(r) for (r,) in db.execute(
                select(AsyncJobEvent.seq).where(AsyncJobEvent.job_id == jid)
                .order_by(AsyncJobEvent.id)
            ).all()]
            if seqs != sorted(seqs) or len(seqs) != len(set(seqs)):
                seq_ok = False
                break
        check("事件序号在跨进程写入下仍单调且不重复", seq_ok)

        check("作业结果已落库（result_json 非空）",
              all((j.result_json or "").strip() for j in jobs),
              f"{sum(1 for j in jobs if (j.result_json or '').strip())}/{len(job_ids)} 有结果")

        # ---------------------------------------------------------- 5. 不误杀兄弟进程
        print("\n[5] 校验「启动时不误杀兄弟进程的作业」")
        live_job = jobs[0]
        live_job.status = "running"
        live_job.worker_id = "99999-sibling"
        from datetime import datetime

        live_job.heartbeat_at = datetime.now().isoformat(timespec="seconds")  # 心跳新鲜
        db.commit()

        result = TASKS.recover_orphans(force=False)
        db.expire_all()
        live_job = db.get(AsyncJob, live_job.id)
        check("心跳新鲜的 running 作业未被误回收",
              live_job.status == "running" and result.get("skipped_live", 0) >= 1,
              f"status={live_job.status} skipped_live={result.get('skipped_live')}")

        # 心跳过期的必须被回收
        live_job.heartbeat_at = "2000-01-01T00:00:00"
        db.commit()
        result2 = TASKS.recover_orphans(force=False)
        db.expire_all()
        live_job = db.get(AsyncJob, live_job.id)
        check("心跳过期的 running 作业被回收（可重试）",
              live_job.status == "failed" and result2.get("recovered", 0) >= 1,
              f"status={live_job.status} recovered={result2.get('recovered')}")

        # 清理测试数据
        db.execute(AsyncJob.__table__.delete().where(AsyncJob.id.in_(job_ids)))
        db.execute(AsyncJobEvent.__table__.delete().where(AsyncJobEvent.job_id.in_(job_ids)))
        db.commit()
    finally:
        db.close()

    print("\n" + "=" * 78)
    print(f"  多进程验证：{PASS} 通过 / {FAIL} 失败")
    print("=" * 78)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
