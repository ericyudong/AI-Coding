"""接口限流（令牌桶）。

院内私有化部署同样需要限流，原因不是防外敌，而是防「自己人把系统打挂」：
- 前端轮询作业进度、脚本刷接口、误配置的定时任务，都可能在几分钟内产生数万请求；
- 登录接口更需要单独限流，否则密码可被暴力枚举。

设计取舍：
- 进程内令牌桶（不引 Redis）。院内单实例够用；多实例时每实例独立限流，可接受。
- 按「用户 + 路由模板」分桶，而不是按 IP：院内常见全院同一出口 IP。
- 桶容量有限且定期清理，避免被随机 user-agent / 路径刷爆内存。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


@dataclass
class _Bucket:
    tokens: float
    updated_at: float
    hits: int = 0


class TokenBucketLimiter:
    """令牌桶限流器。

    容量 = 每分钟额度；补充速率 = 额度 / 60 每秒。
    超出后返回 429 并带上 `Retry-After`，让调用方知道该等多久 ——
    这是「可控降级」与「直接把用户打懵」的区别。
    """

    def __init__(self, per_minute: int, *, burst: int | None = None) -> None:
        self.per_minute = max(1, per_minute)
        self.capacity = float(burst if burst is not None else self.per_minute)
        self._rate = self.per_minute / 60.0
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()
        self._last_gc = time.monotonic()

    def allow(self, key: str, cost: float = 1.0) -> tuple[bool, float]:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=self.capacity, updated_at=now)
                self._buckets[key] = bucket
            elapsed = max(0.0, now - bucket.updated_at)
            bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self._rate)
            bucket.updated_at = now
            bucket.hits += 1
            if bucket.tokens >= cost:
                bucket.tokens -= cost
                allowed, retry_after = True, 0.0
            else:
                deficit = cost - bucket.tokens
                allowed, retry_after = False, round(deficit / self._rate, 2)

            # 惰性 GC：桶数超阈值时清理 10 分钟未活动的桶
            if len(self._buckets) > 20000 and now - self._last_gc > 60:
                stale = [k for k, b in self._buckets.items() if now - b.updated_at > 600]
                for k in stale:
                    self._buckets.pop(k, None)
                self._last_gc = now
            return allowed, retry_after

    def stats(self) -> dict:
        with self._lock:
            return {"buckets": len(self._buckets), "per_minute": self.per_minute,
                    "capacity": self.capacity}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """对写操作与登录接口限流；只读接口给更宽的额度。

    为什么不给所有接口同一额度：看板类接口天然高频（前端轮询 + 多用户同看），
    如果和写入同额度，正常使用就会被拦；而写入接口才是真正会伤库的。
    """

    EXEMPT = ("/healthz", "/readyz", "/metrics", "/console", "/docs", "/redoc", "/openapi.json")

    def __init__(self, app) -> None:
        super().__init__(app)
        self.general = TokenBucketLimiter(settings.rate_limit_per_minute)
        self.write = TokenBucketLimiter(max(60, settings.rate_limit_per_minute // 4))
        self.login = TokenBucketLimiter(settings.rate_limit_login_per_minute, burst=10)

    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled:
            return await call_next(request)
        path = request.url.path
        if path.startswith(self.EXEMPT):
            return await call_next(request)

        identity = self._identity(request)
        if "/auth/login" in path:
            limiter, scope = self.login, "login"
        elif request.method in ("GET", "HEAD", "OPTIONS"):
            limiter, scope = self.general, "read"
        else:
            limiter, scope = self.write, "write"

        allowed, retry_after = limiter.allow(f"{scope}:{identity}")
        if not allowed:
            from app.core.observability import METRICS

            METRICS.inc("http_rate_limited_total", scope=scope)
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(max(1, int(retry_after) + 1))},
                content={"code": 429,
                         "message": f"请求过于频繁（{scope} 类接口每分钟上限 "
                                    f"{limiter.per_minute} 次），请 {max(1, int(retry_after) + 1)} 秒后重试",
                         "data": {"scope": scope, "retry_after_sec": max(1, int(retry_after) + 1)}},
            )
        return await call_next(request)

    @staticmethod
    def _identity(request: Request) -> str:
        auth = request.headers.get("authorization") or request.headers.get("x-token") or ""
        if auth:
            # 不解析 JWT（限流不该做鉴权），用令牌指纹分桶即可
            return f"token:{hash(auth) & 0xFFFFFFFF:x}"
        client = request.client.host if request.client else "unknown"
        return f"ip:{client}"
