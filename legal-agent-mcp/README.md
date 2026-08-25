# legal-agent-mcp

通过 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 调用 [Legal Agent](../legal-agent/) 后端能力的 MCP Server。可在 **Cursor**、**Codex**、**DeepSeek Harness** 等支持 MCP 的客户端中使用。

## 功能

| MCP 工具 | 说明 |
|----------|------|
| `legal_search` | 法律检索（综合分析 / 法规 / 类案 / 行政处罚 / 专业解读） |
| `legal_chat` | 智能问答（劳动法 / 法律问答 / 金融合规 / 企业出海） |
| `contract_draft` | 合同起草 |
| `contract_review_file` | 上传并审核本地 doc/docx/pdf 合同 |
| `contract_compare_files` | 比对两份合同文件 |
| `legal_capabilities` | 获取支持的检索类型、模块与风格 |

## 前置条件

1. 启动 Legal Agent 后端（默认 `http://127.0.0.1:8010`）：

```bash
cd ../legal-agent/backend
uvicorn app.main:app --host 127.0.0.1 --port 8010
```

2. Node.js >= 20

## 安装与构建

```bash
cd legal-agent-mcp
npm install
npm run build
```

开发模式（无需先 build）：

```bash
npm run dev
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LEGAL_AGENT_URL` | Legal Agent API 地址 | `http://127.0.0.1:8010` |
| `LEGAL_AGENT_TOKEN` | JWT（优先使用，跳过登录） | — |
| `LEGAL_AGENT_USERNAME` | 登录用户名 | `admin` |
| `LEGAL_AGENT_PASSWORD` | 登录密码 | `admin123` |

复制 `.env.example` 并按需修改。MCP 客户端配置中通过 `env` 字段传入。

## Cursor 配置

在 Cursor 设置 → MCP 中添加（`~/.cursor/mcp.json` 或项目 `.cursor/mcp.json`）：

```json
{
  "mcpServers": {
    "legal-agent": {
      "command": "node",
      "args": ["/Users/yudong/AI-Coding/legal-agent-mcp/dist/index.js"],
      "env": {
        "LEGAL_AGENT_URL": "http://127.0.0.1:8010",
        "LEGAL_AGENT_USERNAME": "admin",
        "LEGAL_AGENT_PASSWORD": "admin123"
      }
    }
  }
}
```

或使用 `tsx` 直接运行源码：

```json
{
  "mcpServers": {
    "legal-agent": {
      "command": "npx",
      "args": ["tsx", "/Users/yudong/AI-Coding/legal-agent-mcp/src/index.ts"],
      "env": {
        "LEGAL_AGENT_URL": "http://127.0.0.1:8010"
      }
    }
  }
}
```

## Codex 配置

在 `~/.codex/config.toml` 的 `[mcp_servers.legal-agent]` 段：

```toml
[mcp_servers.legal-agent]
command = "node"
args = ["/Users/yudong/AI-Coding/legal-agent-mcp/dist/index.js"]

[mcp_servers.legal-agent.env]
LEGAL_AGENT_URL = "http://127.0.0.1:8010"
LEGAL_AGENT_USERNAME = "admin"
LEGAL_AGENT_PASSWORD = "admin123"
```

## DeepSeek Harness 配置

在 `cordis.yml` 中添加 MCP 服务器：

```yaml
mcp:
  servers:
    legal-agent:
      transport: stdio
      command: node
      args:
        - /Users/yudong/AI-Coding/legal-agent-mcp/dist/index.js
      env:
        LEGAL_AGENT_URL: http://127.0.0.1:8010
        LEGAL_AGENT_USERNAME: admin
        LEGAL_AGENT_PASSWORD: admin123
```

## 使用示例

配置完成后，在对话中可直接请求：

- 「检索：劳动合同到期不续签是否需要支付经济补偿？」
- 「劳动法问答：试用期可以随便辞退吗？」
- 「起草一份软件外包服务合同，立场为甲方，风格详细严谨」
- 「审核 `/path/to/contract.docx` 这份合同」

Agent 会自动调用对应的 MCP 工具。

## 架构

详细设计见 [docs/architecture.md](docs/architecture.md)，PPT 版本见 [docs/architecture.pptx](docs/architecture.pptx)。

```
Cursor / Codex / DSH
        │  stdio (MCP)
        ▼
  legal-agent-mcp
        │  HTTP + JWT
        ▼
  legal-agent backend (:8010)
        │
        ▼
  LLM / 文档解析 / 比对服务
```

## License

MIT
