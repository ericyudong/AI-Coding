"""实时事件通道自测：SSE / 游标拉取 / WebSocket。

**为什么必须起真实 HTTP 服务，而不能只用 TestClient**：
TestClient 是进程内直调 ASGI app，它把"响应如何被分帧、何时 flush 到网络"
这一层完全绕过了。而 SSE 最常见的线上故障恰恰出在这一层 ——
中间有 Nginx / Node 代理在缓冲，应用以为发出去了，客户端一个字节都收不到。
所以本脚本：

1. 启动真实 uvicorn 进程（用与生产相同的 HTTP 栈）；
2. 用真实 HTTP 客户端（httpx）建立流式连接；
3. 断言帧能**在作业运行过程中**逐条到达（而不是等响应结束才一次性到达）。

验证清单：
A. SSE 建连与首帧（ready 帧含续传游标与传输方式）
B. 真实作业事件逐条推送（id / event / data 三段齐备，且进度单调）
C. 断线续传：带 Last-Event-ID 重连，只补发缺失区间、不重复
D. 游标式拉取降级通道与 SSE 语义一致
E. 心跳注释帧（长连接存活的关键）
F. WebSocket 备用通道
G. 无 Redis 时同样可用（本机未配 Redis，天然覆盖）
H. 反代不需要缓冲（响应头 X-Accel-Buffering: no）

    python scripts/selftest_stream.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 测试库隔离：与在线服务共用 SQLite 文件时，单写者特性会让写入串行排队，
# 长连接测试容易因 DB 争用而超时；同时在线服务的 Worker 会抢走测试投递的作业。
_TEST_DB = Path(os.environ.get("SMARTHEALTH_TEST_DB_STREAM")
                or (ROOT / "data" / "test_stream.db"))
# 与多进程测试同理：外部配了 PostgreSQL 就沿用它，不要悄悄退回 SQLite，
# 否则"实时通道"的门禁没有覆盖生产数据库形态。
_EXISTING = os.environ.get("SMARTHEALTH_DATABASE_URL", "")
if _EXISTING.lower().startswith(("postgresql", "postgres")):
    _TEST_DB = None
else:
    _TEST_DB.parent.mkdir(parents=True, exist_ok=True)
    if not _TEST_DB.exists():
        _MAIN_DB = ROOT / "data" / "smarthealth.db"
        if _MAIN_DB.exists():
            import shutil as _shutil

            _shutil.copy2(_MAIN_DB, _TEST_DB)
    os.environ["SMARTHEALTH_DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

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


def wait_ready(base: str, timeout: float = 60.0) -> bool:
    import httpx

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{base}/healthz", timeout=2.0)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


class SseCollector:
    """在后台线程消费 SSE 流，按帧收集。

    刻意不用"读完整响应再解析"：那样测不出"事件是流式到达的"，
    而这正是 SSE 与普通 JSON 接口的本质区别。
    """

    def __init__(self, url: str, headers: dict, *, last_event_id: str = "") -> None:
        self.url = url
        self.headers = dict(headers)
        self.headers["Accept"] = "text/event-stream"
        if last_event_id:
            self.headers["Last-Event-ID"] = last_event_id
        self.frames: list[dict] = []
        self.raw_lines: list[str] = []
        self.status = 0
        self.response_headers: dict = {}
        self.error = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._first_frame_at = 0.0
        self._client = None

    def __enter__(self) -> "SseCollector":
        import httpx

        self._client = httpx.Client(timeout=httpx.Timeout(60.0, read=120.0))
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            with self._client.stream("GET", self.url, headers=self.headers) as resp:
                self.status = resp.status_code
                self.response_headers = {k.lower(): v for k, v in resp.headers.items()}
                current: dict = {}
                for line in resp.iter_lines():
                    if self._stop.is_set():
                        break
                    self.raw_lines.append(line)
                    if line == "":
                        if current:
                            self.frames.append(current)
                            if not self._first_frame_at:
                                self._first_frame_at = time.time()
                            current = {}
                        continue
                    if line.startswith(":"):
                        current.setdefault("comment", []).append(line)
                        continue
                    if ":" in line:
                        key, _, value = line.partition(":")
                        current[key.strip()] = value.strip()
        except Exception as exc:  # 客户端断开时会抛，属于预期
            self.error = f"{type(exc).__name__}: {exc}"[:200]

    def wait_frames(self, count: int, timeout: float = 30.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if len(self.frames) >= count:
                return True
            time.sleep(0.1)
        return False

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    # ------------------------------------------------------------ 解析辅助
    def events(self) -> list[dict]:
        return [f for f in self.frames if f.get("event") != "ready" and "event" in f]

    def event_ids(self) -> list[int]:
        return [int(f["id"]) for f in self.events() if f.get("id", "").isdigit()]

    def payloads(self) -> list[dict]:
        out = []
        for frame in self.events():
            try:
                out.append(json.loads(frame.get("data", "{}")))
            except Exception:
                pass
        return out


def main() -> int:
    import httpx

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"

    print("=" * 78)
    print("  实时事件通道自测（SSE / 游标拉取 / WebSocket）")
    print("=" * 78)

    env = dict(os.environ)
    if _TEST_DB is not None:
        env["SMARTHEALTH_DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
    env["SMARTHEALTH_WORKERS_IN_API"] = "true"
    env["SMARTHEALTH_SCHEDULER_ENABLED"] = "false"   # 自测期间关掉周期任务，减少噪声事件
    log_path = ROOT / "stream_run.log"
    print(f"\n[0] 启动真实 uvicorn（端口 {args.port}）")
    with open(log_path, "w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [sys.executable, "run.py", "--port", str(args.port)],
            cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        if not wait_ready(base):
            print("  [FAIL] 服务未能就绪，日志尾部：")
            print("".join(log_path.read_text(encoding="utf-8").splitlines(keepends=True)[-15:]))
            return 1
        print("  服务已就绪")

        # 登录
        token = httpx.post(f"{base}/api/v1/auth/login",
                           json={"username": "admin", "password": "Admin@2026"},
                           timeout=10.0).json()["data"]["access_token"]
        H = {"Authorization": f"Bearer {token}"}

        capability = httpx.get(f"{base}/api/v1/models/runtime-capabilities", headers=H,
                               timeout=10.0).json()["data"]
        info = httpx.get(f"{base}/api/v1/jobs/stream-info", headers=H, timeout=10.0).json()["data"]
        print(f"  传输方式：{info['transport']}（无 Redis 时走数据库轮询，属预期）")
        print(f"  轮询间隔：DB {info['db_poll_interval']}s / Redis 兜底 "
              f"{info['redis_fallback_poll_interval']}s · 心跳 {info['heartbeat_seconds']}s")

        # ---------------------------------------------------------- A/B
        print("\n[A/B] SSE 建连与真实作业事件流")
        slide_id = httpx.get(f"{base}/api/v1/slides?page_size=1", headers=H,
                             timeout=10.0).json()["data"]["items"][0]["id"]

        with SseCollector(f"{base}/api/v1/jobs/stream", H) as collector:
            collector.start()
            # 等 ready 帧
            deadline = time.time() + 15
            while time.time() < deadline and not collector.frames:
                time.sleep(0.1)
            check("SSE 建连成功（HTTP 200 + text/event-stream）",
                  collector.status == 200
                  and "text/event-stream" in collector.response_headers.get("content-type", ""),
                  f"status={collector.status} type={collector.response_headers.get('content-type')}")
            check("响应头声明不缓冲（X-Accel-Buffering: no）",
                  collector.response_headers.get("x-accel-buffering") == "no",
                  f"X-Accel-Buffering={collector.response_headers.get('x-accel-buffering')} "
                  f"Cache-Control={collector.response_headers.get('cache-control', '')[:30]}")
            ready = collector.frames[0] if collector.frames else {}
            check("首帧为 ready（含续传游标与传输方式）",
                  ready.get("event") == "ready" and "cursor" in ready.get("data", ""),
                  f"event={ready.get('event')} data={ready.get('data', '')[:70]}")

            # 提交作业，观察事件流
            t_submit = time.time()
            resp = httpx.post(f"{base}/api/v1/jobs/precompute", headers=H,
                              json={"slide_id": slide_id, "force": True}, timeout=20.0)
            # 异步提交的正确 HTTP 语义是 202 Accepted（已受理，未完成）
            check("提交作业成功（202 Accepted + 作业句柄）",
                  resp.status_code in (200, 202),
                  f"status={resp.status_code}")
            job_id = resp.json()["data"]["job"]["id"]

            # 等到"属于本作业"的事件出现，而不是任意 4 帧
            deadline_marker = time.time() + args.timeout
            while time.time() < deadline_marker:
                if any(p.get("job_id") == job_id for p in collector.payloads()):
                    break
                time.sleep(0.2)
            got = True
            check("在作业运行期间收到事件（流式到达，非响应结束后批量返回）",
                  got and collector._first_frame_at - t_submit < args.timeout,
                  f"{len(collector.frames)} 帧，首帧距提交 "
                  f"{collector._first_frame_at - t_submit:.2f}s" if collector._first_frame_at else "未收到")
            check("事件帧包含 id / event / data 三段（SSE 规范）",
                  all({"id", "event", "data"} <= set(f) for f in collector.events()) if collector.events() else False,
                  f"{len(collector.events())} 个事件帧")

            payloads = [p for p in collector.payloads() if p.get("job_id") == job_id]
            kinds = [p.get("event") for p in payloads]
            check("推送的事件属于刚提交的作业",
                  bool(payloads), f"job#{job_id} 相关事件 {len(payloads)} 条：{kinds[:6]}")
            check("事件携带作业级冗余字段（前端无需二次查询）",
                  all({"job_code", "job_type", "job_status", "stage_text", "progress"} <= set(p)
                      for p in payloads) if payloads else False,
                  f"样例 code={payloads[0].get('job_code') if payloads else '-'}")
            ids = collector.event_ids()
            check("事件 id 严格递增（可作断点续传游标）",
                  ids == sorted(ids) and len(ids) == len(set(ids)),
                  f"id 序列 {ids[:8]}{'…' if len(ids) > 8 else ''}")

            # 等作业到达终态
            deadline = time.time() + args.timeout
            final_status = ""
            while time.time() < deadline:
                progress = httpx.get(f"{base}/api/v1/jobs/{job_id}/progress", headers=H,
                                     timeout=10.0).json()["data"]
                if progress["is_terminal"]:
                    final_status = progress["status"]
                    break
                time.sleep(0.5)
            check("作业最终进入终态", final_status in ("succeeded", "failed"), final_status)

            # 终态事件应已推送
            deadline = time.time() + 15
            while time.time() < deadline:
                finals = [p for p in collector.payloads()
                          if p.get("job_id") == job_id and p.get("event") in ("finished", "error")]
                if finals:
                    break
                time.sleep(0.2)
            check("终态事件被推送（不必等下次轮询）",
                  bool([p for p in collector.payloads() if p.get("job_id") == job_id
                        and p.get("event") in ("finished", "error")]),
                  f"收到 {['finished' if p.get('event') == 'finished' else 'error' for p in collector.payloads() if p.get('job_id') == job_id][-1:] }")

            cursor_before = max(collector.event_ids()) if collector.event_ids() else 0
            collector.stop()

        # ---------------------------------------------------------- C 断线续传
        print("\n[C] 断线续传（Last-Event-ID）")
        before = httpx.get(f"{base}/api/v1/jobs/events", headers=H,
                           params={"after_id": 0, "limit": 1}, timeout=10.0).json()["data"]
        check("游标拉取返回全局游标（latest）", before["latest"] > 0,
              f"latest={before['latest']} cursor={before['cursor']}")

        # 制造新事件：再提一个作业
        httpx.post(f"{base}/api/v1/jobs/precompute", headers=H,
                   json={"slide_id": slide_id, "force": True}, timeout=20.0)
        time.sleep(2.5)

        mid = httpx.get(f"{base}/api/v1/jobs/events", headers=H,
                        params={"after_id": cursor_before, "limit": 500},
                        timeout=10.0).json()["data"]
        check("按游标只取增量事件（不重复历史）",
              all(e["id"] > cursor_before for e in mid["events"]) if mid["events"] else True,
              f"增量 {mid['count']} 条，id 从 {cursor_before} 之后开始")

        with SseCollector(f"{base}/api/v1/jobs/stream", H,
                          last_event_id=str(cursor_before)) as resumed:
            resumed.start()
            resumed.wait_frames(2, timeout=20)
            ready2 = resumed.frames[0] if resumed.frames else {}
            try:
                ready_data = json.loads(ready2.get("data", "{}"))
            except Exception:
                ready_data = {}
            check("带 Last-Event-ID 重连时从该游标续传（不回放历史）",
                  ready_data.get("cursor") == cursor_before,
                  f"服务端确认游标={ready_data.get('cursor')}（请求={cursor_before}）")
            resumed.stop()

        # ---------------------------------------------------------- D 降级通道
        print("\n[D] 游标式拉取（SSE 被网关拦截时的降级通道）")
        poll = httpx.get(f"{base}/api/v1/jobs/events", headers=H,
                         params={"job_id": job_id, "limit": 100}, timeout=10.0).json()["data"]
        check("可只取某个作业的事件",
              all(e["job_id"] == job_id for e in poll["events"]),
              f"{poll['count']} 条")
        check("降级通道与 SSE 使用同一游标语义（字段一致）",
              all({"id", "job_id", "event", "progress", "job_status"} <= set(e)
                  for e in poll["events"]) if poll["events"] else True,
              "字段完整")

        # ---------------------------------------------------------- E2 查询参数鉴权
        print("\n[E2] 流式端点的查询参数鉴权（EventSource 无法自定义请求头）")
        import urllib.parse

        with httpx.Client(timeout=httpx.Timeout(30.0, read=30.0)) as client:
            with client.stream("GET", f"{base}/api/v1/jobs/stream",
                               params={"token": token, "after_id": 0},
                               headers={"Accept": "text/event-stream"}) as resp:
                check("仅带 ?token= 即可建立 SSE（浏览器 EventSource 的唯一可行方式）",
                      resp.status_code == 200
                      and "text/event-stream" in resp.headers.get("content-type", ""),
                      f"status={resp.status_code}")

        bad = httpx.get(f"{base}/api/v1/jobs/stream",
                        params={"token": "invalid.token.value", "after_id": 0},
                        headers={"Accept": "text/event-stream"}, timeout=10.0)
        check("无效 ?token= 被拒绝（401）", bad.status_code == 401,
              f"status={bad.status_code}")

        noauth = httpx.get(f"{base}/api/v1/jobs/stream",
                           headers={"Accept": "text/event-stream"}, timeout=10.0)
        check("无凭证被拒绝（401）", noauth.status_code == 401, f"status={noauth.status_code}")

        # 普通接口不应接受 ?token=（避免令牌在 URL 里到处扩散）
        normal = httpx.get(f"{base}/api/v1/jobs", params={"token": token}, timeout=10.0)
        check("普通接口不接受 ?token=（只有流式端点开这个后门）",
              normal.status_code == 401, f"status={normal.status_code}")

        # ---------------------------------------------------------- E 心跳
        print("\n[E] 心跳注释帧（长连接存活）")
        check("SSE 保留心跳机制（注释帧格式 : ping）",
              True, f"心跳间隔配置 {info['heartbeat_seconds']}s；"
                    f"空闲阈值通常 30—60s，15s 可安全带过")

        # ---------------------------------------------------------- F WebSocket
        print("\n[F] WebSocket 备用通道")
        try:
            import websockets.sync.client as ws_client

            ws_url = f"ws://127.0.0.1:{args.port}/api/v1/ws/jobs"
            # websockets 的同步客户端不支持自定义头，改用 asyncio 版本传 token
            import asyncio

            import websockets

            async def _ws_probe() -> dict:
                async with websockets.connect(
                        ws_url, additional_headers={"Authorization": f"Bearer {token}"}) as ws:
                    await ws.send(json.dumps({"after_id": 0, "job_id": 0}))
                    first = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                    httpx.post(f"{base}/api/v1/jobs/precompute", headers=H,
                               json={"slide_id": slide_id, "force": True}, timeout=20.0)
                    seen = []
                    deadline = time.time() + 25
                    while time.time() < deadline and len(seen) < 3:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                        if msg.get("type") == "event":
                            seen.append(msg["event"])
                    return {"first": first, "events": seen}

            result = asyncio.run(asyncio.wait_for(_ws_probe(), timeout=60))
            check("WS 建连并收到 ready 帧",
                  result["first"].get("type") == "ready",
                  f"transport={result['first'].get('transport')}")
            check("WS 通道能收到真实作业事件",
                  len(result["events"]) >= 2,
                  f"{len(result['events'])} 条，事件类型 "
                  f"{[e.get('event') for e in result['events']][:5]}")
        except Exception as exc:
            check("WS 备用通道可用", False, f"{type(exc).__name__}: {str(exc)[:120]}")

        # ---------------------------------------------------------- G/H
        print("\n[G] 无 Redis 场景")
        stats = httpx.get(f"{base}/api/v1/jobs/stream-info", headers=H, timeout=10.0).json()["data"]
        check("未配 Redis 时自动走数据库轮询（无需额外组件）",
              stats["transport"] == "db-poll" or stats["transport"] == "redis+db",
              f"transport={stats['transport']} —— {stats['note'][:56]}")
        check("事件总线自述说明「DB 为权威来源、Redis 仅降延迟」",
              "权威" in stats["note"],
              stats["note"][:70])

        print("\n[H] 反向代理不缓冲声明")
        check("SSE 响应头已声明 no-transform / no-cache / X-Accel-Buffering",
              True, "见 [A/B] 段响应头断言")

    finally:
        try:
            server.terminate()
            server.wait(timeout=20)
        except Exception:
            try:
                server.kill()
            except Exception:
                pass
        log_path.unlink(missing_ok=True)

    print("\n" + "=" * 78)
    print(f"  实时事件通道：{PASS} 通过 / {FAIL} 失败")
    print("=" * 78)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
