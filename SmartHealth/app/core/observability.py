"""可观测性基础设施：trace id、结构化访问日志、指标采集。

为什么演示系统总是「出问题查不出来」：
没有 trace id 就无法把「用户报的一个错误」和「日志里的几十条记录」对上；
没有指标就只能靠人肉看日志判断服务是否健康。

本模块提供三件套，且刻意保持零外部依赖（院内离线环境无法连 APM 平台）：
1. `trace_id_var`   —— 每个请求一个 trace id，可在任意日志中带出
2. `AccessLog`      —— 结构化访问日志（含耗时、状态、用户、trace id）
3. `METRICS`        —— 进程内计数器 / 直方图，暴露为 Prometheus 文本格式
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from collections import defaultdict
from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("smarthealth.access")

# 请求级 trace id。用 ContextVar 而非 threading.local：ASGI 下请求可能跨协程。
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")


def current_trace_id() -> str:
    return trace_id_var.get()


# ------------------------------------------------------------------ 指标
class Metrics:
    """极简指标注册表。

    只保留真正会被用到的三类指标，避免演变成自建的半成品 Prometheus：
    - counter：累计计数（请求数、错误数、作业数）
    - gauge：瞬时值（队列深度、在线节点数）
    - histogram：耗时分布（用固定桶，够算 P50/P95/P99）
    """

    BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._hist: dict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = {}
        self._hist_sum: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._hist_count: dict[tuple[str, tuple[tuple[str, str], ...]], int] = defaultdict(int)
        self.started_at = time.time()

    @staticmethod
    def _key(name: str, labels: dict[str, str] | None) -> tuple[str, tuple[tuple[str, str], ...]]:
        return name, tuple(sorted((labels or {}).items()))

    def inc(self, name: str, value: float = 1.0, **labels: str) -> None:
        with self._lock:
            self._counters[self._key(name, labels)] += value

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        with self._lock:
            self._gauges[self._key(name, labels)] = value

    def observe(self, name: str, seconds: float, **labels: str) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._hist.setdefault(key, []).append(seconds)
            self._hist_sum[key] += seconds
            self._hist_count[key] += 1
            # 防止无界增长：单指标只保留最近 5000 个样本（足够算分位数）
            if len(self._hist[key]) > 5000:
                self._hist[key] = self._hist[key][-2500:]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counters = [{"name": k[0], "labels": dict(k[1]), "value": round(v, 6)}
                        for k, v in self._counters.items()]
            gauges = [{"name": k[0], "labels": dict(k[1]), "value": round(v, 6)}
                      for k, v in self._gauges.items()]
            hists = []
            for key, samples in self._hist.items():
                ordered = sorted(samples)
                hists.append({
                    "name": key[0], "labels": dict(key[1]),
                    "count": self._hist_count[key],
                    "sum": round(self._hist_sum[key], 6),
                    "p50": _quantile(ordered, 0.50), "p95": _quantile(ordered, 0.95),
                    "p99": _quantile(ordered, 0.99), "max": round(ordered[-1], 6) if ordered else 0.0,
                })
        return {"counters": counters, "gauges": gauges, "histograms": hists,
                "uptime_sec": round(time.time() - self.started_at, 1)}

    def render_prometheus(self) -> str:
        """输出 Prometheus 文本格式。可被院内现有监控直接抓取。"""
        snap = self.snapshot()
        lines: list[str] = []
        lines.append("# HELP smarthealth_uptime_seconds 进程运行时长")
        lines.append("# TYPE smarthealth_uptime_seconds gauge")
        lines.append(f"smarthealth_uptime_seconds {snap['uptime_sec']}")
        for item in snap["counters"]:
            metric = _prom_name(item["name"])
            lines.append(f"# TYPE {metric} counter")
            lines.append(f"{metric}{_prom_labels(item['labels'])} {item['value']}")
        for item in snap["gauges"]:
            metric = _prom_name(item["name"])
            lines.append(f"# TYPE {metric} gauge")
            lines.append(f"{metric}{_prom_labels(item['labels'])} {item['value']}")
        for item in snap["histograms"]:
            metric = _prom_name(item["name"])
            lines.append(f"# TYPE {metric} summary")
            lines.append(f"{metric}_count{_prom_labels(item['labels'])} {item['count']}")
            lines.append(f"{metric}_sum{_prom_labels(item['labels'])} {item['sum']}")
            for q in ("p50", "p95", "p99"):
                labels = {**item["labels"], "quantile": q[1:]}
                lines.append(f"{metric}{_prom_labels({k: str(v) for k, v in labels.items()})} {item[q]}")
        return "\n".join(lines) + "\n"


def _quantile(ordered: list[float], q: float) -> float:
    if not ordered:
        return 0.0
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return round(ordered[idx], 6)


def _prom_name(name: str) -> str:
    return "smarthealth_" + name.replace(".", "_").replace("-", "_")


def _prom_labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{str(v).replace(chr(34), "")}"' for k, v in sorted(labels.items()))
    return "{" + inner + "}"


METRICS = Metrics()


# ------------------------------------------------------------------ 中间件

_TOKEN_QUERY_RE = re.compile(r"([?&])(token|access_token|refresh_token)=[^&\s]*", re.IGNORECASE)


def redact_url(url: str) -> str:
    """抹掉 URL 里的令牌，再写进日志。

    为什么必须做：SSE 端点必须支持 `?token=`（EventSource 无法自定义请求头），
    而访问日志默认记录完整路径 —— 令牌会随之落到日志文件、被日志采集系统带走、
    被有日志权限的人看到。**令牌进日志 = 令牌泄露**，且往往比令牌进 URL 更危险
    （URL 只在浏览器地址栏短暂存在，日志是长期留存且到处同步的）。
    """
    if not url:
        return url
    return _TOKEN_QUERY_RE.sub(r"\1\2=***", url)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """注入 trace id、统计指标、输出结构化访问日志。"""

    # 这些路径不写访问日志、不计入指标：探针与静态资源会把指标淹掉
    QUIET_PREFIXES = ("/healthz", "/readyz", "/metrics", "/console", "/static",
                      "/favicon.ico", "/openapi.json", "/docs", "/redoc")

    def __init__(self, app, *, log_requests: bool = True) -> None:
        super().__init__(app)
        self.log_requests = log_requests

    async def dispatch(self, request: Request, call_next):
        # path 用于路由判定与指标标签（不含查询串，天然无令牌）；
        # full_url 只用于日志，必须过 redact_url —— SSE 的令牌在查询参数里。
        path = request.url.path
        log_url = redact_url(str(request.url))
        quiet = path.startswith(self.QUIET_PREFIXES)

        incoming = request.headers.get("x-trace-id")
        trace_id = incoming or uuid.uuid4().hex[:16]
        token = trace_id_var.set(trace_id)

        started = time.perf_counter()
        status_code = 500
        error_text = ""
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Trace-Id"] = trace_id
            return response
        except Exception as exc:  # pragma: no cover - 交给全局异常处理
            error_text = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            elapsed = time.perf_counter() - started
            trace_id_var.reset(token)
            if not quiet:
                METRICS.inc("http_requests_total", method=request.method,
                            path=_route_label(request), status=str(status_code))
                METRICS.observe("http_request_duration_seconds", elapsed,
                                method=request.method, path=_route_label(request))
                if status_code >= 500:
                    METRICS.inc("http_server_errors_total", path=_route_label(request))
                elif status_code >= 400:
                    METRICS.inc("http_client_errors_total", path=_route_label(request))
            if self.log_requests and not quiet:
                logger.info(json.dumps({
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "trace_id": trace_id,
                    "method": request.method,
                    "path": path,
                    "url": log_url,
                    "status": status_code,
                    "ms": round(elapsed * 1000, 2),
                    "client": (request.client.host if request.client else ""),
                    "user": getattr(request.state, "username", ""),
                    "error": error_text,
                }, ensure_ascii=False))


def _route_label(request: Request) -> str:
    """用路由模板而非原始路径做标签，避免 /slides/1、/slides/2 炸出无限多标签。"""
    route = request.scope.get("route")
    path_format = getattr(route, "path", None)
    return path_format or "unmatched"


def record_job_metrics() -> None:
    """把作业队列状态同步为 gauge。由周期任务与 /metrics 调用。"""
    from app.core.database import SessionLocal
    from app.models.job import AsyncJob
    from sqlalchemy import func, select

    try:
        with SessionLocal() as db:
            rows = db.execute(
                select(AsyncJob.status, func.count(AsyncJob.id)).group_by(AsyncJob.status)
            ).all()
        for status, count in rows:
            METRICS.set_gauge("jobs_total", float(count), status=str(status))
    except Exception:  # pragma: no cover
        logger.debug("作业指标采集失败", exc_info=True)
