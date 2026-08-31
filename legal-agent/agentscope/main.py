#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run Legal Agent capabilities on AgentScope via legal-agent-mcp (stdio).

Architecture::

    User → AgentScope Agent (ReAct) → MCP stdio → legal-agent-mcp
         → HTTP + JWT → Legal Agent backend (:8010)

Prerequisites:
  1. Legal Agent backend listening on LEGAL_AGENT_URL
  2. legal-agent-mcp built (``npm run build`` in legal-agent-mcp/)
  3. LLM API key: DASHSCOPE_API_KEY or OPENAI_API_KEY

Usage::

    export DASHSCOPE_API_KEY=sk-...
    python main.py

    # one-shot (non-interactive)
    python main.py --once "检索：劳动合同到期不续签是否需要经济补偿？"
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import httpx

from agentscope.agent import Agent
from agentscope.console import launch_console
from agentscope.mcp import MCPClient, StdioMCPConfig
from agentscope.message import UserMsg
from agentscope.tool import Toolkit

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]  # AI-Coding/
DEFAULT_MCP_ENTRY = REPO_ROOT / "legal-agent-mcp" / "dist" / "index.js"
DEFAULT_LEGAL_URL = "http://127.0.0.1:8010"


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    return value.strip() if isinstance(value, str) and value.strip() else default


def build_model(model_name: str | None):
    """Prefer DashScope; fall back to OpenAI-compatible API."""
    dashscope_key = _env("DASHSCOPE_API_KEY")
    openai_key = _env("OPENAI_API_KEY")

    if dashscope_key:
        from agentscope.credential import DashScopeCredential
        from agentscope.model import DashScopeChatModel

        return DashScopeChatModel(
            credential=DashScopeCredential(api_key=dashscope_key),
            model=model_name or _env("LEGAL_AGENT_SCOPE_MODEL", "qwen3.6-plus"),
            stream=True,
        )

    if openai_key:
        from agentscope.credential import OpenAICredential
        from agentscope.model import OpenAIChatModel

        return OpenAIChatModel(
            credential=OpenAICredential(
                api_key=openai_key,
                base_url=_env("OPENAI_BASE_URL"),
            ),
            model=model_name or _env("LEGAL_AGENT_SCOPE_MODEL", "gpt-4.1"),
            stream=True,
        )

    raise RuntimeError(
        "请设置 DASHSCOPE_API_KEY 或 OPENAI_API_KEY 后再运行。",
    )


async def check_legal_backend(base_url: str) -> None:
    """Fail fast if Legal Agent is not reachable."""
    url = f"{base_url.rstrip('/')}/health"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(url)
            res.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"无法连接 Legal Agent 后端 ({url})。\n"
            f"请先启动：cd legal-agent/backend && "
            f"uvicorn app.main:app --host 127.0.0.1 --port 8010\n"
            f"原始错误：{exc}",
        ) from exc


def resolve_mcp_entry(cli_path: str | None) -> Path:
    raw = cli_path or _env("LEGAL_AGENT_MCP_ENTRY") or str(DEFAULT_MCP_ENTRY)
    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        raise RuntimeError(
            f"找不到 legal-agent-mcp 入口：{path}\n"
            f"请先执行：cd legal-agent-mcp && npm install && npm run build",
        )
    return path


def build_legal_mcp(mcp_entry: Path, legal_url: str) -> MCPClient:
    env = {
        "LEGAL_AGENT_URL": legal_url,
        "LEGAL_AGENT_USERNAME": _env("LEGAL_AGENT_USERNAME", "admin") or "admin",
        "LEGAL_AGENT_PASSWORD": _env("LEGAL_AGENT_PASSWORD", "admin123")
        or "admin123",
    }
    token = _env("LEGAL_AGENT_TOKEN")
    if token:
        env["LEGAL_AGENT_TOKEN"] = token

    # Preserve PATH so `node` resolves inside the MCP child process
    path_env = os.environ.get("PATH")
    if path_env:
        env["PATH"] = path_env

    return MCPClient(
        name="legal-agent",
        is_stateful=True,
        mcp_config=StdioMCPConfig(
            command=_env("LEGAL_AGENT_MCP_COMMAND", "node") or "node",
            args=[str(mcp_entry)],
            env=env,
            cwd=str(mcp_entry.parent.parent),
        ),
        execution_timeout=180.0,
    )


SYSTEM_PROMPT = """你是法务助手 LegalAssistant，运行在 AgentScope 上，通过 MCP 调用 Legal Agent。

可用 MCP 工具（优先使用，不要凭空编造法律结论）：
- legal_search：法律检索（comprehensive / regulation / case / penalty / interpretation）
- legal_chat：智能问答（labor_law / qa / financial / overseas），可传 session_id 续聊
- contract_draft：合同起草（purpose / position / style）
- contract_review_file：审核本地 doc/docx/pdf（file_path 需为绝对路径）
- contract_compare_files：比对两份合同
- legal_capabilities：查看支持的检索类型 / 模块 / 风格

回答要求：
1. 需要检索或起草/审核时先调用工具，再基于工具结果总结。
2. 明确标注依据来自 Legal Agent 工具结果；不确定时说明需补充事实。
3. 使用中文回复，结构清晰。
"""


async def run_once(agent: Agent, prompt: str) -> None:
    reply = await agent.reply(UserMsg(name="user", content=prompt))
    # Console pretty-print is handled inside Agent; also print text fallback
    print(reply)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=None,
        help="覆盖模型名（默认由 LEGAL_AGENT_SCOPE_MODEL / 厂商默认决定）",
    )
    parser.add_argument(
        "--legal-url",
        default=_env("LEGAL_AGENT_URL", DEFAULT_LEGAL_URL),
        help=f"Legal Agent 后端地址（默认 {DEFAULT_LEGAL_URL}）",
    )
    parser.add_argument(
        "--mcp-entry",
        default=None,
        help="legal-agent-mcp dist/index.js 路径",
    )
    parser.add_argument(
        "--once",
        metavar="PROMPT",
        default=None,
        help="单次提问后退出（非交互）",
    )
    parser.add_argument(
        "--verbosity",
        choices=["quiet", "default", "debug"],
        default="default",
    )
    parser.add_argument(
        "--skip-health",
        action="store_true",
        help="跳过 Legal Agent /health 检查",
    )
    args = parser.parse_args()

    legal_url = args.legal_url or DEFAULT_LEGAL_URL
    mcp_entry = resolve_mcp_entry(args.mcp_entry)

    if not args.skip_health:
        await check_legal_backend(legal_url)

    model = build_model(args.model)
    legal_mcp = build_legal_mcp(mcp_entry, legal_url)

    print(f"[legal-agentscope] Legal Agent: {legal_url}")
    print(f"[legal-agentscope] MCP entry:   {mcp_entry}")
    print("[legal-agentscope] Connecting MCP (stdio)…")

    await legal_mcp.connect()
    try:
        tools = await legal_mcp.list_tools()
        print(
            "[legal-agentscope] MCP tools: "
            + ", ".join(t.name for t in tools),
        )

        agent = Agent(
            name="LegalAssistant",
            system_prompt=SYSTEM_PROMPT,
            model=model,
            toolkit=Toolkit(mcps=[legal_mcp]),
        )

        if args.once:
            await run_once(agent, args.once)
        else:
            await launch_console(agent, verbosity=args.verbosity)
    finally:
        await legal_mcp.close(ignore_errors=True)
        print("[legal-agentscope] MCP closed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except RuntimeError as err:
        print(f"错误：{err}", file=sys.stderr)
        sys.exit(1)
