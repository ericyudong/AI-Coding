"""作业事件的实时推送通道：SSE 为主，WebSocket 为备。

设计文档依据：第五章（Agent 与作业可观测性）。

为什么默认用 SSE 而不是 WebSocket：
- 作业事件是**单向、文本、有天然 id** 的流，SSE 三者全中，WS 要额外做协议与重连。
- SSE 有浏览器原生的**断线自动重连 + Last-Event-ID 续传**；WS 得自己写这一套。
- SSE 走普通 HTTP，院内网关/反向代理默认放行；WS 需要升级协商，常被中间设备拦。
- 这里唯一要 WS 的场景是"客户端还要往服务端推东西"（如前端主动订正游标），
  属于少数派需求，因此提供 WS 作为**备用**通道而非主路径。

必须处理的三个工程细节（缺一个长连接就活不下来）：
1. **心跳**：SSE 连接长时间无字节流动会被代理/防火墙按空闲掐断（常见阈值 30—60s）。
   这里以注释帧 `: ping` 周期性保活。
2. **反向代理缓冲**：Nginx / Node 的 http-proxy 默认会缓冲响应体，SSE 会被攒着不发，
   表现为"连上了但永远没数据"。响应头必须显式声明不缓冲
   （`X-Accel-Buffering: no`、`Cache-Control: no-cache`），Node 侧也要关掉超时与缓冲。
3. **断连清理**：客户端关闭后生成器必须尽快退出，否则每个断连都遗留一个轮询线程。
   用 `request.is_disconnected()` 主动探测 + 生成器 finally 兜底。
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import (APIRouter, Depends, HTTPException, Query, Request, WebSocket,
                     WebSocketDisconnect)
from fastapi.responses import StreamingResponse

from app.core.deps import DbSession, get_stream_user, require
from app.core.events import DB_POLL_INTERVAL, EVENTS
from app.core.response import ok

logger = logging.getLogger(__name__)
router = APIRouter(tags=["01 任务中心 · 实时事件"])

# 心跳间隔。取 15s：远小于常见的 30—60s 空闲阈值，又不至于刷屏占带宽。
HEARTBEAT_SECONDS = 15.0


def _sse_headers() -> dict[str, str]:
    """SSE 必需的响应头。

    `X-Accel-Buffering: no` 是给 Nginx 看的；没有它，即使应用层 flush 了，
    Nginx 仍会把响应攒在 buffer 里，前端表现为"连接成功但零事件"。
    `Cache-Control: no-cache` 防止中间缓存把流缓存住；
    `Connection: keep-alive` 明确这是长连接。
    """
    return {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Content-Type": "text/event-stream; charset=utf-8",
    }


@router.get("/jobs/stream", summary="作业事件流（SSE，支持 Last-Event-ID 断线续传）")
async def stream_jobs(
    request: Request,
    db: DbSession,
    job_id: int = Query(0, description="只看某个作业（0=全部）"),
    job_type: str = Query("", description="按作业类型过滤"),
    after_id: int = Query(0, description="从该事件 id 之后开始（Last-Event-ID 的显式写法）"),
    poll_interval: float = Query(0, description="轮询间隔秒（0=按传输方式自动）"),
    user: dict = Depends(get_stream_user),
) -> StreamingResponse:
    """推送作业事件。

    断点续传优先取请求头 `Last-Event-ID`（浏览器 EventSource 自动带），
    其次取查询参数 `after_id`（手工重连/脚本用）。两者都没有则从"当前最新"开始 ——
    **不能从 0 开始**，否则一个新连接会先把历史全量事件灌一遍，页面瞬间刷屏。
    """
    from app.core.security import has_permission

    if not has_permission(user["permissions"], "job:read"):
        raise HTTPException(status_code=403, detail="缺少权限：job:read")

    last_event_id = request.headers.get("last-event-id", "")
    cursor = 0
    if last_event_id.strip().isdigit():
        cursor = int(last_event_id.strip())
    elif after_id > 0:
        cursor = int(after_id)
    else:
        cursor = EVENTS.latest_event_id()   # 新连接只看"从现在起"

    scope_job_id = int(job_id) if job_id else None
    scope_type = job_type.strip()
    interval = float(poll_interval) if poll_interval and poll_interval > 0 else None

    # 关键：把游标一并传给生成器。只把游标写进 ready 帧、却不传下去，
    # 会让生成器从 0 开始，把全部历史事件重放给每个新连接。
    stream, mode = EVENTS.redis_subscriber(after_id=cursor, job_id=scope_job_id,
                                           job_type=scope_type)

    async def _generator():
        # 首帧：告知客户端连接已建立、快通道是否在用、续传点在哪。
        # 有这一帧，前端才能区分"连上了但没事件"与"没连上"。
        yield (f"retry: 3000\n"
               f"event: ready\n"
               f"data: {json.dumps({'cursor': cursor, 'transport': mode, 'user': user.get('username', '')}, ensure_ascii=False)}\n\n")
        idle_since = asyncio.get_event_loop().time()
        try:
            while True:
                if await request.is_disconnected():
                    logger.debug("SSE 客户端断开，退出事件流")
                    return
                # 事件拉取在同步生成器里做（阻塞 IO），放进线程池避免卡住事件循环
                item = await asyncio.to_thread(_next_or_none, stream)
                now = asyncio.get_event_loop().time()
                if item is None:
                    if now - idle_since >= HEARTBEAT_SECONDS:
                        # 注释帧：SSE 规范里以 ':' 开头的行是心跳注释，客户端会忽略。
                        # 它是长连接存活的关键 —— 没有它，代理 30—60s 就会掐断。
                        yield f": ping {int(now)}\n\n"
                        idle_since = now
                    await asyncio.sleep(0.05)
                    continue
                if item["type"] == "event":
                    yield item["event"].to_sse()
                    idle_since = now
                else:
                    if now - idle_since >= HEARTBEAT_SECONDS:
                        yield f": ping {int(now)}\n\n"
                        idle_since = now
        except asyncio.CancelledError:  # pragma: no cover - 客户端强制关闭
            raise
        except Exception:  # pragma: no cover
            logger.exception("SSE 事件流异常终止")
            yield ("event: error\n"
                   f"data: {json.dumps({'message': '事件流异常终止，请重连'}, ensure_ascii=False)}\n\n")
        finally:
            # 生成器是同步的，显式关闭以释放其内部循环（否则残留轮询线程）
            try:
                stream.close()
            except Exception:
                pass

    return StreamingResponse(_generator(), media_type="text/event-stream",
                             headers=_sse_headers())


def _next_or_none(stream):
    """从同步生成器取下一项；取不到（本次恰好没数据）返回 None。

    这里不能直接 `next(stream)`：它会在无数据时阻塞等待，把 SSE 的心跳节拍也一起拖住。
    stream() 每次无论有无事件都会 yield 一项（event 或 idle），所以正常不阻塞。
    """
    try:
        return next(stream)
    except StopIteration:
        return None


@router.get("/jobs/events", summary="作业事件（游标式拉取，SSE 不可用时的降级通道）")
def poll_events(
    db: DbSession,
    after_id: int = Query(0, description="从该事件 id 之后开始"),
    job_id: int = Query(0),
    job_type: str = Query(""),
    limit: int = Query(200, le=1000),
    user: dict = Depends(require("job:read")),
) -> dict:
    """游标式拉取。

    存在的意义：某些院内网关会拦掉长连接（SSE 也被拦），或前端在 iframe /
    受限环境里拿不到流式响应。这条接口保证"无论如何都能看到进度"，
    与 SSE 共用同一份事件来源与游标语义，前端切换通道时不需要改逻辑。
    """
    events = EVENTS.fetch_events(after_id=after_id,
                                 job_id=job_id or None,
                                 job_type=job_type.strip(),
                                 limit=limit)
    next_cursor = events[-1].id if events else int(after_id)
    return ok({
        "events": [e.to_dict() for e in events],
        "cursor": next_cursor,
        "latest": EVENTS.latest_event_id(),
        "count": len(events),
        "transport": EVENTS.stats()["transport"],
    })


@router.get("/jobs/stream-info", summary="事件通道自述（传输方式/间隔/订阅者）")
def stream_info(db: DbSession, user: dict = Depends(require("job:read"))) -> dict:
    """让前端与运维知道当前用的是快通道还是数据库轮询、延迟特性如何。"""
    stats = EVENTS.stats()
    stats["heartbeat_seconds"] = HEARTBEAT_SECONDS
    stats["db_poll_interval_default"] = DB_POLL_INTERVAL
    stats["endpoints"] = {
        "sse": "/api/v1/jobs/stream",
        "poll": "/api/v1/jobs/events",
        "ws": "/api/v1/ws/jobs",
    }
    return ok(stats)


@router.websocket("/ws/jobs")
async def ws_jobs(websocket: WebSocket) -> None:
    """WebSocket 备用通道。

    为什么保留它：少数客户端（桌面壳、非浏览器 SDK）更习惯 WS；
    且 WS 允许客户端在连接内**动态改过滤条件**（SSE 改条件必须重连）。
    实现上刻意与 SSE 共用同一份事件来源，避免两套逻辑两条 bug。
    """
    await websocket.accept()
    stream = None
    try:
        # 首帧由客户端下发订阅参数：{"after_id": 0, "job_id": 0, "job_type": ""}
        try:
            init = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
        except Exception:
            init = {}
        after_id = int(init.get("after_id") or 0)
        job_id = int(init.get("job_id") or 0) or None
        job_type = str(init.get("job_type") or "")
        cursor = after_id or EVENTS.latest_event_id()

        stream, mode = EVENTS.redis_subscriber(after_id=cursor, job_id=job_id,
                                               job_type=job_type)
        await websocket.send_json({"type": "ready", "cursor": cursor, "transport": mode})

        while True:
            item = await asyncio.to_thread(_next_or_none, stream)
            if item is None:
                await asyncio.sleep(0.05)
                continue
            if item["type"] == "event":
                await websocket.send_json({"type": "event", "event": item["event"].to_dict()})
            else:
                await websocket.send_json({"type": "idle", "cursor": item["cursor"]})
    except WebSocketDisconnect:
        logger.debug("WS 客户端断开")
    except Exception:  # pragma: no cover
        logger.exception("WS 事件通道异常")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        if stream is not None:
            try:
                stream.close()
            except Exception:
                pass
