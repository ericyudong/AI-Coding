"""部署预检（doctor）：在启动服务前确认「这套环境能不能跑起来」。

同一个工具承担三种角色，靠参数区分：

| 角色 | 用法 | 说明 |
|---|---|---|
| 本地排障 | `python scripts/doctor.py` | 文本表格，人读 |
| CI 快速检查 | `python scripts/doctor.py --ci` | 紧凑输出 + 稳定摘要行 |
| **上线门禁** | `python scripts/doctor.py --ci --require-postgres --require-redis --fail-on-warn` | 不满足即 FAIL，阻止发布 |

它检查的是**那些启动时不会报错、但运行时一定会出问题**的东西：
- 数据库连不上 / 迁移有漂移 / 库结构与代码不一致
- PostgreSQL 下连接池参数不合理、缺 SKIP LOCKED 所需版本
- Redis 配了但连不上，或**连得上却做不了分布式锁**（ACL 禁 EVAL 时 ping 正常、锁会泄漏）
- 数据目录不可写、磁盘将满（院内私有化最常见的故障）
- 作业引擎配置自相矛盾（workers_in_api 与多进程部署冲突）
- 依赖缺失（ONNX/tifffile/psycopg）

退出码约定（CI 门禁必须有明确语义，否则流水线判不出该不该拦）：
    0 = 通过（可能有 WARN，除非加了 --fail-on-warn）
    1 = **门禁未通过**（有 FAIL 项）—— 应当阻止发布
    2 = **门禁本身跑不起来**（参数错误），与"环境不合格"区分开，
        避免把"参数写错了"误报成"生产环境有问题"
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RESULTS: list[dict] = []


def record(level: str, name: str, detail: str, hint: str = "") -> None:
    RESULTS.append({"level": level, "name": name, "detail": detail, "hint": hint})


def ok(name: str, detail: str = "") -> None:
    record("OK", name, detail)


def warn(name: str, detail: str, hint: str = "") -> None:
    record("WARN", name, detail, hint)


def fail(name: str, detail: str, hint: str = "") -> None:
    record("FAIL", name, detail, hint)


CI_MODE_OUT = False


def main() -> int:
    parser = argparse.ArgumentParser(description="SmartHealth 部署预检")
    parser.add_argument("--json", action="store_true", help="输出 JSON（机器可读）")
    parser.add_argument("--ci", action="store_true",
                        help="CI 模式：紧凑输出 + 末尾打印稳定摘要行")
    parser.add_argument("--require-redis", action="store_true",
                        help="Redis 必须可用且分布式锁功能完整（多实例生产门禁）")
    parser.add_argument("--require-postgres", action="store_true",
                        help="数据库必须是 PostgreSQL（确保 CI 真的验证了生产路径）")
    parser.add_argument("--fail-on-warn", action="store_true",
                        help="WARN 也视为不通过（最严格的上线门禁）")
    parser.add_argument("--init-db", action="store_true",
                        help="先执行数据库迁移再检查（全新环境 / CI 首次运行用）")
    parser.add_argument("--skip-lock-selftest", action="store_true",
                        help="跳过分布式锁功能往返测试（只做连通性检查）")
    args = parser.parse_args()
    global CI_MODE_OUT
    CI_MODE_OUT = bool(args.ci)

    from app.core.config import settings

    # ---------------------------------------------------------- 0. 迁移（可选）
    # 全新环境（CI 的临时 PG / 新装的院内服务器）库是空的，必须先建起来再检查，
    # 否则"库结构与模型一致性"必然 FAIL —— 那是环境还没准备好，不是环境有问题。
    if args.init_db:
        try:
            from app.core.database import init_db

            summary = init_db()
            applied = summary.get("applied") or []
            ok("数据库迁移已执行",
               f"应用 {len(applied)} 条" + (f"（{', '.join('v%s' % a['version'] for a in applied[:5])}）"
                                            if applied else "（已是最新）"))
            if summary.get("baseline_marked"):
                ok("存量库已登记基线", "跳过历史迁移重放")
        except Exception as exc:
            fail("数据库迁移执行失败", f"{type(exc).__name__}: {exc}",
                 "先修好连接或迁移脚本，否则后续检查没有意义")

    # ---------------------------------------------------------- 1. 配置自洽
    if settings.workers_in_api and os.environ.get("SMARTHEALTH_MULTI_PROCESS") == "1":
        fail("部署形态一致性",
             "workers_in_api=true 但检测到多进程标记",
             "多进程部署必须设 SMARTHEALTH_WORKERS_IN_API=false，否则每个 API 副本都会起 Worker")
    else:
        ok("部署形态一致性",
           f"workers_in_api={settings.workers_in_api}")

    if settings.db_backend == "unknown":
        fail("数据库配置", f"无法识别的 database_url：{settings.database_url[:60]}",
             "仅支持 sqlite:///... 与 postgresql+psycopg://...")
    elif args.require_postgres and settings.db_backend != "postgresql":
        # 这条检查的意义：CI 里如果忘了配 PG，SQLite 也能"全绿"通过 ——
        # 那这个门禁等于没测生产形态（SQLite 是单写者，并发语义与 PG 完全不同）。
        fail("数据库配置",
             f"门禁要求 PostgreSQL，实际 backend={settings.db_backend}",
             "设置 SMARTHEALTH_DATABASE_URL=postgresql+psycopg://user:pwd@host:5432/dbname；"
             "SQLite 验证不了 FOR UPDATE SKIP LOCKED 与真实并发写")
    else:
        ok("数据库配置", f"backend={settings.db_backend}"
                         + ("（已按门禁要求校验）" if args.require_postgres else ""))

    # ---------------------------------------------------------- 2. 依赖可用性
    for mod, why, level in (
        ("sqlalchemy", "ORM 核心", "FAIL"),
        ("fastapi", "Web 框架", "FAIL"),
        ("numpy", "特征与算法", "FAIL"),
        ("PIL", "图像读取（合成切片/缩略图）", "FAIL"),
        ("apscheduler", "周期任务调度", "WARN"),
        ("redis", "Redis 锁与事件推送", "WARN"),
        ("psycopg", "PostgreSQL 驱动", "WARN"),
        ("onnxruntime", "真实模型推理", "WARN"),
        ("tifffile", "真实 WSI 金字塔读取", "WARN"),
        ("multipart", "文件上传", "WARN"),
    ):
        try:
            m = importlib.import_module(mod)
            ok(f"依赖 {mod}", f"{getattr(m, '__version__', '?')} —— {why}")
        except Exception:
            if level == "FAIL":
                fail(f"依赖 {mod}", f"缺失 —— {why}", f"pip install {mod}")
            else:
                warn(f"依赖 {mod}", f"缺失 —— {why}（相关功能将不可用）", f"pip install {mod}")

    # ---------------------------------------------------------- 3. 数据库连通与迁移
    try:
        from app.core.database import engine
        from app.core.db_engine import describe_database_url, ping, pool_status

        p = ping(engine)
        if p.get("ok"):
            ok("数据库连通", f"{describe_database_url()} · {p.get('latency_ms')}ms · "
                              f"{p.get('server_version', '')[:40]}")
        else:
            fail("数据库连通", str(p.get("error"))[:200], "检查连接串 / 网络 / 凭据")

        pool = pool_status(engine)
        if pool.get("supported"):
            if pool.get("size", 0) >= 5:
                ok("连接池配置", f"size={pool.get('size')} overflow={pool.get('max_overflow')} "
                                 f"timeout={pool.get('timeout')}s")
            else:
                warn("连接池配置", f"size={pool.get('size')} 偏小",
                     "多 Worker 高并发下建议 db_pool_size ≥ 10")
        else:
            ok("连接池配置", f"SQLite 使用默认池（{pool.get('note', '')}）")

        # 迁移状态
        from app.core.migrations import migration_status

        mig = migration_status(engine)
        if mig.get("ok"):
            ok("数据库迁移", f"v{mig.get('current_version')}/{mig.get('registered')} 全部已应用")
        else:
            if mig.get("pending"):
                fail("数据库迁移", f"存在未应用迁移：{[p['version'] for p in mig['pending']]}",
                     "启动服务会自动应用；若失败请查看 sys_schema_version 与日志")
            if mig.get("checksum_drift"):
                warn("数据库迁移", f"校验和漂移 {len(mig['checksum_drift'])} 处",
                     "同一版本号的实现被改过；后续环境不会重放，可能出现结构漂移")

        # PG 版本能力（SKIP LOCKED 需 9.5+）
        if settings.db_backend == "postgresql":
            ver = str(p.get("server_version", ""))
            # `SHOW server_version` 返回的是裸版本号（如 "16.15"），不带 "PostgreSQL"
            # 前缀 —— 旧代码按子串 `"PostgreSQL" in ver` 判断，在真实 PG 16 上
            # 永远走 WARN 分支（「未能解析版本：16.15」），--fail-on-warn 门禁被它拦死。
            # 用正则取主次版本号，两种形态（"16.15" / "PostgreSQL 16.15 on x86_64"）都兼容。
            m = re.search(r"(\d+)\.(\d+)", ver)
            if m:
                major, minor = int(m.group(1)), int(m.group(2))
                if (major, minor) >= (9, 5):
                    ok("PostgreSQL 能力",
                       f"PostgreSQL {major}.{minor}（支持 FOR UPDATE SKIP LOCKED，需 ≥9.5）")
                else:
                    warn("PostgreSQL 能力", f"{major}.{minor} 低于 9.5",
                         "FOR UPDATE SKIP LOCKED 需要 PostgreSQL 9.5+；"
                         "作业领取会退化为乐观更新（并发性能差且易撞车）")
            else:
                warn("PostgreSQL 能力", f"未能解析版本：{ver[:60]}")

        # 库结构 vs 模型（缺列会导致运行期 500）
        from app.core.database import Base
        from app import models  # noqa: F401
        from sqlalchemy import inspect

        inspector = inspect(engine)
        existing = set(inspector.get_table_names())
        missing_tables = [t.name for t in Base.metadata.sorted_tables if t.name not in existing]
        missing_columns: list[str] = []
        for t in Base.metadata.sorted_tables:
            if t.name not in existing:
                continue
            have = {c["name"] for c in inspector.get_columns(t.name)}
            for c in t.columns:
                if c.name not in have:
                    missing_columns.append(f"{t.name}.{c.name}")
        if missing_tables or missing_columns:
            fail("库结构与模型一致性",
                 f"缺表 {len(missing_tables)} / 缺列 {len(missing_columns)}",
                 "运行 init_db 或补一条迁移（缺列会导致运行期 500）")
        else:
            ok("库结构与模型一致性", f"{len(existing)} 张表全部匹配")
    except Exception as exc:
        fail("数据库检查", f"{type(exc).__name__}: {exc}", "先解决连通性再谈其它")

    # ---------------------------------------------------------- 4. Redis 与锁
    from app.core.locks import lock_status as _lock_status_fn
    lock_status = _lock_status_fn

    lk = lock_status()
    redis_conn = lk["redis"].get("connected")
    if redis_conn:
        ok("分布式锁", f"Redis {lk['redis'].get('version')}（{lk['redis'].get('mode')}）"
                       f" · 租约 {lk['lease_seconds']}s")
    elif settings.redis_url:
        msg = f"已配置 Redis（{settings.redis_url.rsplit('@', 1)[-1]}）但连不上"
        if args.require_redis:
            fail("分布式锁", msg, "生产多实例必须可用；检查 Redis 服务与网络")
        else:
            warn("分布式锁", msg, "将退化为数据库锁：功能可用，但效率与实时性下降")
    else:
        level = "FAIL" if args.require_redis else "WARN"
        msg = "未配置 Redis（SMARTHEALTH_REDIS_URL 为空）"
        hint = "多实例生产建议配置：分布式锁与作业事件推送走 Redis"
        (fail if level == "FAIL" else warn)("分布式锁后端", msg, hint)

    # 功能往返测试：连通不等于可用。Redis ACL 可以只给 SET 不给 EVAL，
    # 托管集群也可能限制 Lua —— 此时 ping 完全正常，但"释放锁"会失败，
    # 锁一直泄漏到租约到期，迁移与周期任务被无谓阻塞，而报错只会是
    # "未能获取锁"，极易被误判成业务问题。这种故障必须在门禁里拦住。
    if not args.skip_lock_selftest:
        try:
            from app.core.locks import self_test as _lock_selftest

            probe = _lock_selftest()
            failed_steps = [st["step"] for st in probe["steps"] if not st["ok"]]
            if probe["ok"]:
                ok("分布式锁功能",
                   f"{probe['backend']}：{len(probe['steps'])} 步往返全通过"
                   f"（抢锁／互斥／释放校验／无泄漏／续期）")
            else:
                fail("分布式锁功能",
                     f"{probe['backend']} 后端失败步骤：{failed_steps}",
                     "连得上不等于能用：Redis ACL 需允许 EVAL（Lua 释放与续期依赖它）；"
                     "数据库锁需能创建 sys_distributed_lock")
        except Exception as exc:
            fail("分布式锁功能", f"{type(exc).__name__}: {exc}",
                 "锁不可用会让多实例下的迁移与周期任务重复执行或长时间阻塞")

    # ---------------------------------------------------------- 5. 磁盘与数据目录
    data_dir = Path(settings.data_dir)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".doctor_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        usage = shutil.disk_usage(str(data_dir))
        pct = usage.used / usage.total * 100
        free_tb = usage.free / 1024 ** 4
        if pct > 95:
            fail("数据目录", f"{data_dir} 使用率 {pct:.1f}%（剩余 {free_tb:.2f} TB）",
                 "clear space；写入失败会让上传与特征落盘全部中断")
        elif pct > 85:
            warn("数据目录", f"{data_dir} 使用率 {pct:.1f}%（剩余 {free_tb:.2f} TB）")
        else:
            ok("数据目录", f"{data_dir} 可写 · 使用率 {pct:.1f}% · 剩余 {free_tb:.2f} TB")
    except Exception as exc:
        fail("数据目录", f"{data_dir} 不可写：{exc}", "检查权限与挂载")

    # ---------------------------------------------------------- 6. 作业引擎
    try:
        from app.core.tasks import TASKS
        from app.services import job_service  # noqa: F401

        types = TASKS.registered_types()
        if len(types) >= 8:
            ok("作业类型注册", f"{len(types)} 类")
        else:
            fail("作业类型注册", f"仅 {len(types)} 类，疑似 handler 导入失败",
                 "确认 app.services.job_service 可导入")
        if settings.workers_in_api:
            ok("作业执行者", f"API 进程内 {settings.job_workers} 个 Worker"
                             "（单进程部署）")
        else:
            ok("作业执行者", "独立 Worker 进程（python -m app.worker）")
    except Exception as exc:
        fail("作业引擎", f"{type(exc).__name__}: {exc}")

    # ---------------------------------------------------------- 6.5 推理与读取能力
    print_needed = True
    try:
        from app.services.wsi_readers import backend_capabilities

        caps = backend_capabilities()
        if caps["tifffile"] or caps["openslide"]:
            ok("WSI 读取后端",
               f"tifffile={caps['tifffile']} openslide={caps['openslide']} "
               f"imagecodecs={caps['imagecodecs']}")
        else:
            fail("WSI 读取后端", "既无 openslide 也无 tifffile",
                 "真实切片无法读取：pip install tifffile（或 openslide-python + openslide）")
        if not caps["imagecodecs"]:
            warn("压缩 TIFF 解码", "imagecodecs 未安装",
                 "真实 WSI 多为 LZW/JPEG 压缩：pip install imagecodecs")
    except Exception as exc:
        warn("WSI 读取后端", f"检查失败：{type(exc).__name__}: {exc}")

    try:
        from app.services import model_registry

        overview = model_registry.registry_overview()
        if overview["installed"] == 0:
            warn("模型权重清单", f"{overview['total']} 条登记，但 0 份已安装",
                 "当前编码器走内置实现；安装真实权重："
                 "python scripts/model_registry.py install <code> --from <文件>")
        else:
            ok("模型权重清单",
               f"{overview['installed']}/{overview['total']} 已安装 · "
               f"可商用且已装 {overview['commercial_ready']} · 自研 {overview['self_developed']}")

        from app.services.encoder_service import encoder_service

        # doctor 是新进程，注册表还没同步过清单；这里先同步再看诊断，
        # 否则会误报"无 ONNX 权重"（其实只是没加载）。
        encoder_service.sync_from_registry(verbose=False)
        diag = encoder_service.onnx_diagnostics()
        if diag["total"] == 0:
            ok("ONNX 编码器", "无 ONNX 权重（不影响启动）")
        elif diag["using_real_model"] == diag["total"]:
            ok("ONNX 编码器", f"{diag['total']} 个全部在用真实权重推理")
        else:
            warn("ONNX 编码器",
                 f"{diag['total'] - diag['using_real_model']}/{diag['total']} 未加载真实权重",
                 "执行 python scripts/model_registry.py verify --all 排查")
        if diag["mismatched_dims"]:
            warn("编码器维度一致性", f"声明与权重不符：{diag['mismatched_dims']}",
                 "以计算图为准，更新 configs/model_registry.json")
    except Exception as exc:
        warn("模型权重清单", f"检查失败：{type(exc).__name__}: {exc}")

    # ---------------------------------------------------------- 输出
    fail_count = sum(1 for r in RESULTS if r["level"] == "FAIL")
    warn_count = sum(1 for r in RESULTS if r["level"] == "WARN")
    if args.fail_on_warn and warn_count:
        # 最严格的门禁：WARN 也算不通过。这里**追加**一条而不是改写既有条目，
        # 这样日志里仍能看出"到底哪几条 WARN 触发了门禁"。
        fail("严格模式（--fail-on-warn）", f"存在 {warn_count} 条 WARN",
             "去掉 --fail-on-warn，或先消除 WARN 项")
        fail_count += 1

    gate_failed = fail_count > 0
    icon = {"OK": "[ OK ]", "WARN": "[WARN]", "FAIL": "[FAIL]"}

    if args.json:
        print(json.dumps({
            "summary": {"ok": not gate_failed, "fail": fail_count, "warn": warn_count,
                        "total": len(RESULTS),
                        "require_postgres": args.require_postgres,
                        "require_redis": args.require_redis,
                        "fail_on_warn": args.fail_on_warn,
                        "backend": settings.db_backend},
            "results": RESULTS}, ensure_ascii=False, indent=2))
    elif CI_MODE_OUT:
        # CI：逐条一行（便于日志检索与注释失败行），末尾给一行机器可读摘要。
        for r in RESULTS:
            print(f"{icon[r['level']]} {r['name']}: {r['detail']}")
            if r["hint"] and r["level"] != "OK":
                print(f"       -> {r['hint']}")
    else:
        print("=" * 78)
        print("  SmartHealth 部署预检（doctor）"
              + ("　[上线门禁模式]" if args.require_redis or args.require_postgres else ""))
        print("=" * 78)
        for r in RESULTS:
            print(f"{icon[r['level']]} {r['name']:<26} {r['detail']}")
            if r["hint"] and r["level"] != "OK":
                print(f"       → {r['hint']}")
        print("-" * 78)
        print(f"  合计 {len(RESULTS)} 项：OK {len(RESULTS) - fail_count - warn_count}"
              f" · WARN {warn_count} · FAIL {fail_count}")
        if fail_count:
            print("  结论：**不可部署**，请先处理 FAIL 项（退出码 1）")
        elif warn_count:
            print("  结论：可部署，但请知悉 WARN 项的影响（退出码 0）")
        else:
            print("  结论：全绿，可部署（退出码 0）")
        print("=" * 78)

    # 稳定的机器可读摘要行：CI 用它做门槛判定，**不要**去 grep 人类可读表格
    # —— 那改一次排版就把流水线改坏。字段名固定，只增不改。
    if args.ci:
        print(f"DOCTOR_SUMMARY ok={not gate_failed} fail={fail_count} warn={warn_count} "
              f"total={len(RESULTS)} backend={settings.db_backend} "
              f"require_postgres={str(args.require_postgres).lower()} "
              f"require_redis={str(args.require_redis).lower()}")

    return 1 if gate_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
