# Legal Agent × AgentScope

在 AgentScope 2.x 上通过 **MCP（legal-agent-mcp）** 调用 Legal Agent 后端的可运行示例。

## 架构

```
用户
  ↓ 自然语言
AgentScope Agent（ReAct + Toolkit）
  ↓ stdio MCP
legal-agent-mcp（6 个工具）
  ↓ HTTP + JWT
Legal Agent 后端（默认 http://127.0.0.1:8010）
```

| 角色 | 组件 |
|------|------|
| 决策 / 编排 | AgentScope `Agent` + `Toolkit(mcps=[…])` |
| MCP Server | `../../legal-agent-mcp` |
| 业务后端 | `../backend`（FastAPI） |

## 前置条件

1. **Python ≥ 3.11**
2. **Node.js ≥ 20**（跑 MCP Server）
3. Legal Agent 后端已启动
4. `legal-agent-mcp` 已构建
5. LLM Key：`DASHSCOPE_API_KEY` 或 `OPENAI_API_KEY`

## 一键准备

```bash
# 终端 1：Legal Agent 后端
cd /Users/yudong/AI-Coding/legal-agent/backend
uvicorn app.main:app --host 127.0.0.1 --port 8010

# 终端 2：构建 MCP（首次）
cd /Users/yudong/AI-Coding/legal-agent-mcp
npm install && npm run build

# 终端 3：本目录依赖
cd /Users/yudong/AI-Coding/legal-agent/agentscope
python3 -m venv .venv && source .venv/bin/activate
# 推荐用本地 agentscope 源码
pip install -e ../../agentscope httpx
# 或：pip install -r requirements.txt
```

复制环境变量：

```bash
cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY 或 OPENAI_API_KEY
set -a && source .env && set +a   # 或手动 export
```

## 运行

交互控制台（推荐）：

```bash
cd /Users/yudong/AI-Coding/legal-agent/agentscope
source .venv/bin/activate
export DASHSCOPE_API_KEY=sk-...
python main.py
```

单次提问：

```bash
python main.py --once "检索：劳动合同到期不续签是否需要支付经济补偿？"
```

常用参数：

| 参数 | 说明 |
|------|------|
| `--legal-url` | Legal Agent 地址，默认 `http://127.0.0.1:8010` |
| `--mcp-entry` | `legal-agent-mcp/dist/index.js` 路径 |
| `--model` | 覆盖模型名 |
| `--verbosity` | `quiet` / `default` / `debug` |
| `--skip-health` | 跳过 `/health` 检查 |
| `--once PROMPT` | 非交互单次调用 |

## MCP 工具

Agent 会通过 MCP 暴露以下工具（名称形如 `mcp__legal-agent__legal_search`）：

| 工具 | 能力 |
|------|------|
| `legal_search` | 法律检索 |
| `legal_chat` | 劳动法 / 合规问答 |
| `contract_draft` | 合同起草 |
| `contract_review_file` | 审核本地 doc/docx/pdf |
| `contract_compare_files` | 合同比对 |
| `legal_capabilities` | 元数据 |

示例话术：

- 「检索：试用期内用人单位解除劳动合同的条件」
- 「劳动法问答：北京最低工资标准是多少？」
- 「起草一份软件外包合同，立场为甲方，风格详细严谨」
- 「审核 `/绝对路径/contract.docx`」

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `LEGAL_AGENT_URL` | `http://127.0.0.1:8010` | 后端地址 |
| `LEGAL_AGENT_USERNAME` / `PASSWORD` | `admin` / `admin123` | MCP 自动登录 |
| `LEGAL_AGENT_TOKEN` | — | 有则跳过登录 |
| `LEGAL_AGENT_MCP_ENTRY` | `../../legal-agent-mcp/dist/index.js` | MCP 入口 |
| `DASHSCOPE_API_KEY` | — | 通义千问 |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | — | OpenAI 兼容 API |
| `LEGAL_AGENT_SCOPE_MODEL` | 厂商默认 | 模型名覆盖 |

## 与 AgentScope Studio 的关系

本仓库使用的 AgentScope **2.x** 交互入口是 `launch_console`，**不再**使用旧版 `agentscope.init(studio_url=...)`。

本机若已安装 `@agentscope/studio`（`as_studio`），主要用于旧版可视化；2.x 推荐：

- 本示例：`python main.py`（终端 Console）
- 或官方：`agentscope/examples/agent_service` + `examples/web_ui`

## 故障排查

| 现象 | 处理 |
|------|------|
| 无法连接 Legal Agent | 确认 `:8010` 已起，`curl http://127.0.0.1:8010/health` |
| 找不到 MCP 入口 | `cd legal-agent-mcp && npm run build` |
| MCP tools 列表为空 | 看 MCP 子进程是否报错；检查 `LEGAL_AGENT_*` 与 Node PATH |
| 未设置 API Key | 导出 `DASHSCOPE_API_KEY` 或 `OPENAI_API_KEY` |
| 合同审核路径无效 | `file_path` 必须是 MCP 进程可见的**绝对路径** |

## 目录结构

```
legal-agent/agentscope/
├── main.py              # 可运行入口
├── requirements.txt
├── .env.example
└── README.md
```

## 相关文档

- [legal-agent-mcp/README.md](../../legal-agent-mcp/README.md)
- [legal-agent-mcp 架构](../../legal-agent-mcp/docs/architecture.md)
- [AgentScope 文档](https://docs.agentscope.io/)
