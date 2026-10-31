"""FastAPI 应用入口（API 进程）。

启动流程：
1. 迁移 + 建表（init_db，走版本化迁移器）
2. 按部署形态决定是否在本进程内起作业 Worker（settings.workers_in_api）
3. 启动周期任务调度（每个任务 leader-only，多实例安全）
4. 挂载 15 个业务模块路由 + 探针/指标
5. 若前端已构建（frontend/public 存在），挂载静态资源（零外部依赖，院内可离线运行）

部署形态的两种正确姿势：

- **单进程（演示 / 小院内）**：`python run.py`
  本进程同时提供 API 与执行作业，`workers_in_api=True`，最简部署。
- **多进程（生产）**：`python run.py --workers 2` 或 `uvicorn --workers 4` + `python -m app.worker`
  API 进程**不能**再带 Worker（`workers_in_api=False`），否则每个 API 副本都会
  各起一份 Worker：并发度翻倍、心跳互相干扰、优雅关闭互相等待。
  作业统一交给独立 Worker 进程池执行。
"""

from __future__ import annotations

import logging
import shutil
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import build_router
from app.core.config import BASE_DIR, settings
from app.core.database import SessionLocal, engine, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("smarthealth")

FRONTEND_PUBLIC = BASE_DIR / "frontend" / "public"


@asynccontextmanager
async def lifespan(app: FastAPI):
    started = time.time()
    migration = init_db()
    from app.core.db_engine import describe_database_url
    from app.core.migrations import migration_status

    logger.info("数据库就绪（backend=%s, %s）", settings.db_backend, describe_database_url())
    if migration.get("applied"):
        logger.info("本次应用了 %d 条迁移：%s", len(migration["applied"]),
                    ", ".join(f"v{a['version']}({a['name']})" for a in migration["applied"]))
    _mig_status = migration_status(engine)
    if _mig_status.get("pending"):
        logger.warning("存在未应用的迁移：%s（该进程启动时会自动应用，此处不应出现）",
                       [p["version"] for p in _mig_status["pending"]])
    if _mig_status.get("checksum_drift"):
        logger.warning("迁移校验和漂移（同版本号实现被改过）：%s", _mig_status["checksum_drift"])

    # 作业引擎：handler 注册必须发生（提交接口依赖），但 Worker 是否启动由部署形态决定
    from app.core.tasks import TASKS
    from app.services import job_service  # noqa: F401 —— 导入即注册全部 handler

    # 模型权重清单同步：把"本院实际装了哪份权重"接进编码器注册表。
    # 放在启动时做，运维装完权重重启即生效；运行期也可调 POST /models/registry/sync。
    from app.services.encoder_service import encoder_service

    sync = encoder_service.sync_from_registry(verbose=False)
    if sync.get("synced"):
        logger.info("模型清单同步：接入 %d 个已安装权重（%s）",
                    sync["synced"], ", ".join(sync.get("synced_codes", [])[:6]))
    else:
        logger.info("模型清单同步：当前无已安装权重，编码器使用内置实现"
                    "（运行 python scripts/model_registry.py list 查看清单）")

    if settings.workers_in_api:
        recovery = TASKS.recover_orphans()
        TASKS.start(workers=settings.job_workers)
        if recovery.get("recovered") or recovery.get("pending"):
            logger.info("作业恢复：回收中断 %d 个、待继续排队 %d 个",
                        recovery.get("recovered", 0), recovery.get("pending", 0))
        logger.info("作业引擎：本进程内含 %d 个 Worker", settings.job_workers)
    else:
        logger.info("作业引擎：本进程仅提供 API（Worker 由独立进程承担，"
                    "workers_in_api=false）")

    # 周期任务（心跳检测、KPI 快照、评测回归、过期令牌清理）
    # 每个任务内部抢分布式锁，因此多实例同时启动也不会重复执行
    from app.core.scheduler import start_scheduler, stop_scheduler

    start_scheduler()

    from sqlalchemy import func, select

    from app.models.system import User

    with SessionLocal() as db:
        user_count = int(db.execute(select(func.count(User.id))).scalar() or 0)
    if user_count == 0:
        logger.warning(
            "数据库为空。请先执行：python -m app.seed [--reset] [--quick]  "
            "（演示账号 admin/admin123）"
        )
    else:
        logger.info("已加载 %d 个用户账号", user_count)

    from app.core.locks import lock_status

    logger.info("分布式锁后端：%s（Redis %s）", lock_status()["backend"],
                "已接入" if lock_status()["redis"].get("connected") else "未接入/不可用")
    logger.info("服务启动完成（%.2fs，部署形态=%s）→ http://%s:%d/docs",
                time.time() - started,
                "单进程(API+Worker)" if settings.workers_in_api else "多进程(仅API)",
                settings.backend_host, settings.backend_port)
    yield

    logger.info("服务关闭中：先停调度器与接单，再优雅结束在跑作业…")
    stop_scheduler()
    if settings.workers_in_api:
        TASKS.shutdown(grace_sec=8.0)
    logger.info("服务已停止")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "基于多年积累病理切片（已由医生完成标注）构建的垂类多模态模型与智慧医疗 Agent 平台。\n\n"
        "覆盖数据治理 → 标签体系 → 模型流水线 → Agent 协同 → 评测基座 → 合规审计 → 云边协同 → 注册路线图全线，"
        "演示数据为可复现的合成切片（真实算法链路：染色去卷积、Reinhard 归一化、门控 ABMIL、"
        "注意力证据、Platt 标定、Bootstrap 置信区间、MRMC 对照、联邦式增量微调）。"
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 中间件顺序：Starlette 后添加的先执行。
# 期望链路：可观测（最外层，能记录到限流返回的 429）→ 限流 → 路由。
from app.core.observability import ObservabilityMiddleware  # noqa: E402
from app.core.ratelimit import RateLimitMiddleware  # noqa: E402

app.add_middleware(RateLimitMiddleware)
app.add_middleware(ObservabilityMiddleware, log_requests=settings.audit_request_logging)


# ------------------------------------------------------------ 统一错误响应
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """统一错误体。

    `detail` 为 dict/list 时**保留结构**而不是 str() 拍平：
    像「删除被拒」这类错误带 `references` 与 `hint`，拍平后前端只能显示一坨字符串，
    用户就没法知道到底被哪几个引用挡住了。
    """
    detail = exc.detail
    message = detail if isinstance(detail, (dict, list)) else str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": message, "data": None},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(x) for x in first.get("loc", []) if x != "body")
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": f"参数校验失败：{location} {first.get('msg', '')}".strip(),
            "data": {"errors": exc.errors()[:6]},
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("未处理异常 %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": f"服务器内部错误：{exc}", "data": None},
    )


# ------------------------------------------------------------------ 路由
app.include_router(build_router(), prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "app": settings.app_name,
            "version": settings.version,
            "docs": "/docs",
            "api_prefix": settings.api_prefix,
            "frontend": f"http://{settings.backend_host}:{settings.frontend_port}"
            if FRONTEND_PUBLIC.exists() else None,
        },
    }


@app.get(f"{settings.api_prefix}/ping", tags=["00 平台"], summary="连通性探测")
def ping() -> dict:
    return {"code": 0, "message": "ok", "data": {"app": settings.app_short_name,
                                                 "version": settings.version}}


# ------------------------------------------------------ 探针与指标（不带鉴权，供运维系统抓取）
@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    """存活探针：只要进程还能响应就返回 200。

    刻意不检查数据库：数据库短暂抖动不应导致编排系统重启应用容器 ——
    那只会让故障从「数据库慢」升级成「服务全挂」。
    """
    return {"status": "alive", "app": settings.app_short_name, "version": settings.version,
            "time": __import__("datetime").datetime.now().isoformat(timespec="seconds")}


@app.get("/readyz", include_in_schema=False)
def readyz():
    """就绪探针：数据库、磁盘、作业引擎、调度器四项都会实测。

    就绪与存活分开是运维常识：就绪失败应把它摘出负载均衡，而不是杀掉进程。
    """
    from starlette.responses import JSONResponse

    from app.core.observability import record_job_metrics
    from app.core.scheduler import scheduler_status
    from app.core.tasks import TASKS

    checks: dict[str, dict] = {}
    ready = True

    # 1) 数据库
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = {"ok": True}
    except Exception as exc:
        checks["database"] = {"ok": False, "error": str(exc)[:200]}
        ready = False

    # 2) 数据目录可写（院内私有化最常见的故障就是磁盘写满）
    try:
        probe = settings.data_dir / ".readyz_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        usage = shutil.disk_usage(str(settings.data_dir))
        free_tb = round(usage.free / 1024 ** 4, 3)
        checks["storage"] = {"ok": True, "free_tb": free_tb,
                             "used_percent": round(usage.used / usage.total * 100, 1)}
        if usage.used / usage.total > 0.95:
            checks["storage"]["ok"] = False
            checks["storage"]["error"] = "磁盘使用率超过 95%，需立即清理"
            ready = False
    except Exception as exc:
        checks["storage"] = {"ok": False, "error": str(exc)[:200]}
        ready = False

    # 3) 作业引擎
    stats = TASKS.stats()
    checks["job_engine"] = {"ok": bool(stats.get("started")),
                            "workers": stats.get("workers"),
                            "queued": stats.get("queued"),
                            "running": stats.get("running")}
    if not stats.get("started"):
        ready = False

    # 4) 调度器（缺失只降级告警，不判不就绪：主链路不依赖定时任务）
    sched = scheduler_status()
    checks["scheduler"] = {"ok": bool(sched.get("running")), "job_count": sched.get("job_count", 0),
                           "execution_mode": sched.get("execution_mode"),
                           "degraded": not sched.get("running")}

    # 5) 数据库迁移状态（存在未应用迁移或校验和漂移 = 库结构与代码不一致，绝不能接单）
    try:
        from app.core.migrations import migration_status

        mig = migration_status(engine)
        checks["migrations"] = {
            "ok": bool(mig.get("ok")),
            "current_version": mig.get("current_version"),
            "registered": mig.get("registered"),
            "pending": [p["version"] for p in mig.get("pending", [])],
            "checksum_drift": len(mig.get("checksum_drift", [])),
        }
        if not mig.get("ok"):
            ready = False
    except Exception as exc:
        checks["migrations"] = {"ok": False, "error": str(exc)[:200]}
        ready = False

    # 6) 分布式锁后端（Redis 不可用不算不就绪：会退化为数据库锁，功能可用）
    try:
        from app.core.locks import lock_status

        lk = lock_status()
        checks["coordination"] = {
            "ok": True,
            "backend": lk["backend"],
            "redis_connected": bool(lk["redis"].get("connected")),
            "degraded": lk["backend"] != "redis",
        }
    except Exception as exc:
        checks["coordination"] = {"ok": False, "error": str(exc)[:200]}

    try:
        record_job_metrics()
    except Exception:  # pragma: no cover
        pass

    payload = {"status": "ready" if ready else "not_ready", "checks": checks}
    return JSONResponse(status_code=200 if ready else 503, content=payload)


@app.get("/metrics", include_in_schema=False)
def metrics():
    """Prometheus 文本格式指标。院内可直接接入既有监控。"""
    from starlette.responses import PlainTextResponse

    from app.core.observability import METRICS, record_job_metrics

    try:
        record_job_metrics()
    except Exception:  # pragma: no cover
        pass
    return PlainTextResponse(METRICS.render_prometheus(), media_type="text/plain; version=0.0.4")


# 静态前端（若已存在）。放在路由之后挂载，避免遮蔽 API。
if FRONTEND_PUBLIC.exists():
    app.mount("/console", StaticFiles(directory=str(FRONTEND_PUBLIC), html=True), name="console")
    logger.info("已挂载静态前端：/console → %s", FRONTEND_PUBLIC)
