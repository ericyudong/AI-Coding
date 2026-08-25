# OpenAI Codex 技术架构与模块实现分析

> 基于本地仓库 `/Users/yudong/AI-Coding/codex` 源码梳理  
> 分析日期：2026-08-22

---

## 1. 概述

**Codex CLI** 是 OpenAI 开源的本地 Coding Agent：在用户机器上运行，调用模型（Responses API），执行命令、编辑文件、调用 MCP/工具，并通过终端 TUI、IDE 扩展、Desktop App 或 SDK 对外提供交互。

| 维度 | 说明 |
|------|------|
| 核心语言 | Rust（`codex-rs/` Cargo workspace，100+ crates） |
| 分发形态 | npm `@openai/codex` 包装平台原生二进制；也有 Homebrew / 独立安装包 |
| 统一宿主协议 | `codex app-server`：JSON-RPC（Thread / Turn / Item） |
| 内部引擎协议 | `Op` / `EventMsg`（Submission Queue / Event Queue） |
| 安全边界 | 平台沙箱 + execpolicy + 用户审批 / Guardian |
| 扩展面 | `ext/` ExtensionRegistry、Plugins、MCP、Skills、Hooks |

---

## 2. 仓库顶层布局

```
codex/
├── codex-rs/          # Rust 主工程（agent、TUI、app-server、沙箱等）
├── codex-cli/         # npm 包：按平台 spawn 原生 `codex` 二进制
├── sdk/               # TypeScript / Python SDK
├── docs/              # 用户向文档（auth、config、sandbox、skills…）
├── scripts/           # 打包、MCP conformance、安装与调试
├── AGENTS.md          # 贡献者约束（勿膨胀 core、app-server v2 约定等）
└── package.json / Bazel / justfile
```

**分发链路：**

```
用户执行 `codex`
  → npm `codex-cli/bin/codex.js`（或独立安装包）
  → 解析 platform/arch → 定位 vendor 内原生二进制
  → 进入 Rust multitool CLI（`codex-cli` crate）
```

---

## 3. 总体分层架构

```
┌─────────────────────────────────────────────────────────────────┐
│ 分发 / SDK 层                                                    │
│  npm @openai/codex · @openai/codex-sdk · Python SDK              │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│ 入口层 Entrypoints                                               │
│  CLI multitool：默认 TUI / exec / app-server / mcp-server / …   │
│  arg0 再入：linux-sandbox · apply_patch · windows-sandbox       │
└──────────┬────────────────────┬──────────────────┬──────────────┘
           │                    │                  │
    ┌──────▼──────┐      ┌──────▼──────┐    ┌──────▼──────┐
    │ TUI(ratatui)│      │ exec 非交互  │    │ IDE / App   │
    │ AppServer   │      │ InProcess   │    │ JSON-RPC    │
    │ Client      │      │ AppServer   │    │ app-server  │
    └──────┬──────┘      └──────┬──────┘    └──────┬──────┘
           └────────────────────┼──────────────────┘
                                │ JSON-RPC v2
┌───────────────────────────────▼─────────────────────────────────┐
│ 协议 / 编排层：codex-app-server                                   │
│  Thread → Turn → Item · MessageProcessor · Extension 装配        │
└───────────────────────────────┬─────────────────────────────────┘
                                │ Op / Event (SQ / EQ)
┌───────────────────────────────▼─────────────────────────────────┐
│ 核心引擎：codex-core                                             │
│  ThreadManager → CodexThread → Session → run_turn                │
│  ModelClient · ToolRouter · Context · MCP · Extensions           │
└─────┬──────────────┬──────────────┬──────────────┬──────────────┘
      │              │              │              │
┌─────▼────┐  ┌──────▼─────┐ ┌─────▼─────┐ ┌──────▼──────┐
│codex-api │  │ sandboxing │ │ codex-mcp │ │ exec-server │
│/client   │  │ seatbelt   │ │ rmcp      │ │ environments│
│providers │  │ linux/win  │ │ connectors│ │ remote exec │
└──────────┘  │ execpolicy │ └───────────┘ └─────────────┘
              └────────────┘
```

**设计要点：** TUI、exec、IDE、Desktop 等客户端尽量统一走 **app-server**，再驱动 **codex-core**；内部仍用 `Op`/`EventMsg` 队列，便于多 UI 复用同一引擎。

---

## 4. Cargo Workspace 模块分组

### 4.1 入口与 UI

| Crate | 路径 | 功能 |
|-------|------|------|
| `codex-cli` | `cli/` | 主二进制；子命令分发（TUI/exec/app-server/mcp…） |
| `codex-arg0` | `arg0/` | 按 argv0 重入为沙箱 / apply_patch 等 helper |
| `codex-tui` | `tui/` | 终端交互 UI（ratatui）；经 AppServerClient 对话 |
| `codex-exec` | `exec/` | 非交互执行；stdout 人读或 JSONL |

### 4.2 核心 Agent

| Crate | 路径 | 功能 |
|-------|------|------|
| `codex-core` | `core/` | Session、Turn、工具编排、MCP 集成、安全策略 |
| `codex-protocol` | `protocol/` | `Op` / `EventMsg` / 权限与输入类型 |
| `codex-tools` | `tools/` | 工具 schema 与执行抽象 |
| `codex-thread-store` / `codex-rollout` / `codex-history` / `codex-state` | 对应目录 | 会话持久化、rollout、历史、SQLite 状态 |

### 4.3 App-server 族

| Crate | 功能 |
|-------|------|
| `codex-app-server` | JSON-RPC 服务实现、线程/回合生命周期 |
| `codex-app-server-protocol` | v1/v2 类型；可生成 TS / JSON Schema |
| `codex-app-server-transport` / `client` / `daemon` | 传输、客户端、守护进程 |

### 4.4 MCP

| Crate | 角色 |
|-------|------|
| `codex-mcp-server` | **作为 MCP Server**：把 Codex 暴露给外部客户端 |
| `codex-mcp` + `codex-rmcp-client` | **作为 MCP Client**：连接用户配置的 MCP / Apps |
| `codex-mcp-extension` (`ext/mcp/`) | 将 MCP 能力挂入 ExtensionRegistry |

### 4.5 沙箱与执行

| Crate | 功能 |
|-------|------|
| `codex-sandboxing` | 跨平台沙箱编排（`SandboxManager`） |
| `codex-linux-sandbox` | Linux bubblewrap / Landlock |
| `codex-windows-sandbox` | Windows restricted token / elevated |
| seatbelt（在 sandboxing 内） | macOS `sandbox-exec` |
| `codex-execpolicy` | Starlark 前缀规则：allow / prompt / forbidden |
| `codex-exec-server` | 本地或其他 Environment 上执行命令 |
| `codex-shell-command` / `apply-patch` | Shell 与补丁应用 |

### 4.6 模型与网络

| Crate | 功能 |
|-------|------|
| `codex-api` / `codex-client` / `http-client` / `websocket-client` | Responses API 与传输 |
| `codex-model-provider` / `models-manager` | 模型提供方与选型 |
| `codex-network-proxy` / `responses-api-proxy` | 网络策略代理、Responses 代理 |
| `ollama` / `lmstudio` | 本地模型后端适配 |

### 4.7 认证与配置

| Crate | 功能 |
|-------|------|
| `codex-login` / `aws-auth` / `keyring-store` / `secrets` | ChatGPT / API Key / 密钥存储 |
| `codex-config` / `features` / `codex-home` / `cloud-config` | 配置加载、特性开关、家目录 |

### 4.8 Code-mode 与扩展

| Crate | 功能 |
|-------|------|
| `codex-code-mode` / `host` / `protocol` / `runtime` | V8/Node 式代码工具执行；可连远程 host |
| `codex-extension-api` + `ext/*` | 扩展注册表与内置扩展（见第 9 节） |
| `codex-plugin` / `core-plugins` | 用户插件市场与安装同步 |
| `codex-skills` / `hooks` / `prompts` / `connectors` | Skills、钩子、提示词、连接器 |

---

## 5. 核心引擎实现（codex-core）

### 5.1 关键抽象

| 概念 | 主要位置 | 说明 |
|------|----------|------|
| `ThreadManager` | `core/src/thread_manager.rs` | 创建/恢复/fork 线程；持有 Auth、Models、Extensions |
| `CodexThread` | `core/src/codex_thread.rs` | 线程句柄：`submit(Op)` / 接收 `Event` |
| `Session` | `core/src/session/` | 会话状态、服务容器、上下文、MCP、ModelClient |
| `submission_loop` | `session/handlers.rs` | 从 SQ 取 `Submission`，按 `Op` 分发 |
| `run_turn` | `session/turn.rs` | 一轮用户任务的主循环 |
| `ModelClient` | `core/src/client.rs` | Responses API（HTTP SSE / WebSocket） |
| `ToolRouter` / `ToolOrchestrator` | `tools/` | 工具注册、审批 → 沙箱 → 执行 → 重试 |
| Context fragments | `core/src/context/` | 模型可见上下文的结构化片段 |

### 5.2 内部协议：Op / Event

定义：`codex-rs/protocol/src/protocol.rs`  
文档：`codex-rs/docs/protocol_v1.md`

**实体心智模型：**

| 实体 | 含义 |
|------|------|
| **Codex** | 本地引擎；经 SQ/EQ 与 UI 通信 |
| **Session** | 当前配置与状态 |
| **Task** | 响应用户输入的一次完整工作（Session 同时最多一个） |
| **Turn（采样轮）** | 一次模型请求 + 工具执行；输出可作为下一轮输入 |

**典型 Op：**

- `UserTurn` / `TurnInput`：用户输入启动回合
- `Interrupt`：打断
- `ExecApproval` / Patch 审批：批准或拒绝执行
- `UserInputAnswer`：回答 `request_user_input`

**典型 EventMsg：**

- `AgentMessage` / 流式 delta
- `ExecApprovalRequest`
- `TurnStarted` / `TurnComplete`（线格式兼容 `task_*`）
- `Error` / `Warning`

### 5.3 `run_turn` 生命周期（实现要点）

`core/src/session/turn.rs` 大致流程：

1. 排空上轮异步 hook 结果  
2. 可选 **pre-sampling compact**（上下文压缩）  
3. 解析输入中的 MCP / plugin mentions  
4. 捕获 step context（world_state、display roots）  
5. 注入 skills / plugins；执行 SessionStart / turn-start hooks  
6. **外层 loop → `run_sampling_request`：**
   - 构建 `Prompt`（history + context fragments + tool specs）
   - `ModelClient` 流式拉取 Responses API
   - 消息写入历史；function/tool call 交给工具运行时
   - 工具结果进入下一轮 sampling，直到模型不再调工具
7. turn 结束 hooks、telemetry、持久化

`submission_loop` 与 turn 并发：Interrupt、审批响应、设置更新可在任务中注入。

### 5.4 工具子系统

`core/src/tools/` 主要 handler：

| Handler | 作用 |
|---------|------|
| `unified_exec` | Shell / 命令执行 |
| `apply_patch` | 文件补丁 |
| `mcp` | 外部 MCP 工具调用 |
| `plan` | Plan 模式 |
| `request_user_input` / `request_permissions` | 向用户提问 / 要权限 |
| `multi_agents` / `multi_agents_v2` | 多 Agent |
| `extension_tools` / `dynamic` | 扩展与动态工具 |
| `view_image` 等 | 多媒体与辅助工具 |

**Orchestrator 顺序：** 审批 → 选择 `SandboxType` → 执行 attempt → 沙箱拒绝时可升级策略重试（含审批缓存）。

---

## 6. App-server：统一宿主协议

文档：`codex-rs/app-server/README.md`

### 6.1 定位

为 VS Code 扩展、TUI、Desktop、exec 等富客户端提供 **JSON-RPC 2.0** 接口（线上可省略 `"jsonrpc":"2.0"`）。

**传输：**

- `stdio`（默认，JSONL）
- `websocket`（实验）
- `unix socket`（本地控制面；`app-server proxy`）
- `--listen off`

### 6.2 三元原语

```
Thread（会话）
  └── Turn（一次用户回合）
        └── Item（消息、推理、命令、补丁等原子产物）
```

### 6.3 典型生命周期

```
initialize → initialized
  → thread/start | resume | fork
  → turn/start
  → 订阅 item/*、turn/* 通知（流式）
  → turn/completed（或 turn/interrupt）
```

### 6.4 v1 vs v2

| | v2（活跃开发） | v1（兼容） |
|--|----------------|------------|
| 风格 | `thread/*`、`turn/*`、`account/*`… | 旧 conversation 等方法 |
| 命名 | camelCase；`*Params` / `*Response` / `*Notification` | 历史形态 |
| 策略 | **新 API 只加 v2**（见 `AGENTS.md`） | 保留旧客户端 |

实现入口：`app-server/src/message_processor.rs`、各 `request_processors/*`；core 事件经 `bespoke_event_handling` 投影为 v2 notifications。

---

## 7. CLI / TUI / Exec 模式

### 7.1 CLI 子命令（节选）

默认无参 → 交互 TUI。

| 子命令 | 作用 |
|--------|------|
| `exec` / `e` | 非交互执行 |
| `review` | 非交互 code review |
| `login` / `logout` | 认证 |
| `mcp` | 管理 config 中的外部 MCP |
| `mcp-server` | 以 MCP Server 身份运行 Codex |
| `app-server` | 启动 JSON-RPC 服务 |
| `plugin` / `sandbox` / `doctor` | 插件、沙箱调试、环境诊断 |
| `resume` / `fork` / `queue` / … | 会话管理 |

### 7.2 TUI

`codex-tui` 经 **`codex-app-server-client`**（in-process 或 remote）驱动引擎，不直接绑死 `ThreadManager`。核心 UI：`tui/src/app.rs`、`chatwidget.rs`、`bottom_pane/`。

### 7.3 Exec 与 SDK

`codex-exec` 启动 in-process app-server，发 `thread/*` + `turn/*`：

- 默认：最终消息到 stdout  
- `--json` / `--experimental-json`：JSONL 事件流  

TypeScript SDK（`sdk/typescript`）：

```
Codex.startThread() / resumeThread()
  → Thread.run() / runStreamed()
  → spawn: codex exec --experimental-json …
  → 解析 JSONL → items / finalResponse / usage
```

不链接 Rust；依赖本地 CLI 二进制。

---

## 8. MCP 双重角色

```
外部 MCP Client ──stdio──► codex-mcp-server ──► ThreadManager / core
                                                      │
Codex Agent (core) ──codex-mcp / rmcp-client──► 用户 MCP Servers / Apps
```

| 方向 | 实现 | 行为 |
|------|------|------|
| Codex **当 Server** | `codex-mcp-server` | 暴露 thread/turn 等能力；工具如 `codex`；审批反向 RPC |
| Codex **当 Client** | `codex-mcp` | 连接管理、catalog 合并、工具暴露、elicitation |

说明文档：`codex-rs/docs/codex_mcp_interface.md`。

---

## 9. 沙箱与安全模型

### 9.1 策略层

1. **权限配置**：`SandboxPolicy` / `sandbox_mode`，以及较新的 `[permissions.*]` / `PermissionProfile`  
2. **审批**：`AskForApproval`；用户或 Guardian 自动审阅  
3. **execpolicy**：Starlark `prefix_rule` → `allow | prompt | forbidden`  
4. **网络**：`codex-network-proxy` + 工具层 network approval  

### 9.2 平台执行层

| 平台 | 机制 |
|------|------|
| macOS | Seatbelt（`/usr/bin/sandbox-exec`） |
| Linux | bubblewrap（优先）+ seccomp；legacy Landlock |
| Windows | restricted-token / elevated backends |

编排：`codex-sandboxing` 的 `SandboxManager`；CLI 通过 `arg0` 再 exec 沙箱 helper。  
WSL1 不支持 bwrap；WSL2 走 Linux 路径。

### 9.3 其它硬化

- `process-hardening`  
- workspace-write 下对 `.git` / `.codex` 等路径的只读保护  
- 审批缓存与沙箱拒绝后的策略升级重试  

---

## 10. Extension / Plugin 系统

### 10.1 ExtensionRegistry

`codex-extension-api` 提供贡献点，例如：

- `ThreadLifecycle` / `TurnLifecycle` / `TurnInput`  
- `Context` / `Tool` / `ToolLifecycle`  
- `McpServer` / `SkillInvocation`  
- `ApprovalReview` / `Config` / `TokenUsage` / `TurnItem`  

装配示例：`app-server/src/extensions.rs` 的 `thread_extensions()`。

### 10.2 内置扩展（`ext/`）

| 扩展 | 作用 |
|------|------|
| skills | Skills 加载与注入 |
| mcp | MCP 工具/服务器贡献 |
| memories | 记忆读写进上下文 |
| goal | Thread goal 持久化 |
| queue | 空闲时 FIFO 队列提交 |
| guardian-v2 | 审批 Guardian 子代理 |
| web-search / image-generation | 搜索与图像 |
| history-notes / git-attribution | 笔记与 Git 归因 |
| agent / connectors / items | Agent、连接器、Item 类型 |

### 10.3 用户插件

`codex-plugin` + `codex-core-plugins`：marketplace、manifest、MCP 声明、安装同步——与 Rust 内置 `ext/` 互补。

### 10.4 其它挂载点

Hooks（`codex-hooks`）、Skills（`SKILL.md`）、Dynamic tools、Code-mode host（本地或 `--code-mode-host`）、app-server experimental API。

---

## 11. 端到端数据流

### 11.1 交互式（TUI / IDE）

```
用户输入
  → TUI / VS Code
  → app-server: turn/start { threadId, input, … }
  → Thread/Turn 处理器
  → CodexThread.submit(Op::TurnInput)
  → Session.submission_loop → run_turn
  → Prompt（history + fragments + tools）
  → ModelClient → OpenAI Responses API
  → 流式 Event / item notifications → UI
  → tool_call → ToolOrchestrator
       → (可选) 审批 ↔ 用户/Guardian
       → Seatbelt / bwrap / Windows 沙箱执行
       → 或 MCP / code-mode / apply_patch …
  → tool output → 再次 sampling
  → turn/completed + rollout / thread-store 持久化
```

### 11.2 SDK / Exec

```
SDK Thread.run(prompt)
  → codex exec --experimental-json
  → InProcess AppServer
  → 同上 Turn 管线
  → stdout JSONL → SDK 解析
```

### 11.3 对照表

| 阶段 | App-server | Core |
|------|------------|------|
| 连接 | `initialize` | 进程内已有 ThreadManager |
| 开会话 | `thread/start` | 建 Session + rollout |
| 用户回合 | `turn/start` | `Op::TurnInput` → `run_turn` |
| 进行中 | `item/*` 通知 | `EventMsg::*` |
| 审批 | server→client request | `Op::ExecApproval` 回填 |
| 打断 | `turn/interrupt` | `Op::Interrupt` |
| 结束 | `turn/completed` | hooks + 持久化 |

---

## 12. 关键文件速查

| 主题 | 路径 |
|------|------|
| Workspace 成员 | `codex-rs/Cargo.toml` |
| Core 导出 | `codex-rs/core/src/lib.rs` |
| Agent 循环 | `core/src/session/turn.rs`, `handlers.rs` |
| 内部协议 | `protocol/src/protocol.rs`, `docs/protocol_v1.md` |
| App-server | `app-server/README.md`, `message_processor.rs` |
| MCP | `docs/codex_mcp_interface.md` |
| 沙箱 | `sandboxing/`, `linux-sandbox/`, `windows-sandbox-rs/` |
| Execpolicy | `execpolicy/README.md` |
| Extensions | `app-server/src/extensions.rs`, `ext/extension-api/` |
| TS SDK | `sdk/typescript/src/{codex,thread,exec}.ts` |
| npm 包装 | `codex-cli/bin/codex.js` |
| 贡献约定 | `AGENTS.md` |

---

## 13. 架构结论

1. **分层清晰：** 分发包装 → 多入口 CLI → app-server 宿主协议 → core 引擎 → 模型/沙箱/MCP/扩展。  
2. **协议双层：** 对外 JSON-RPC v2（Thread/Turn/Item）；对内 Op/Event 队列。  
3. **安全纵深：** 权限配置 + execpolicy + 人工/Guardian 审批 + 平台沙箱。  
4. **可扩展：** ExtensionRegistry、插件市场、MCP、Skills、Hooks、Code-mode 多点挂载。  
5. **多客户端一引擎：** TUI / IDE / Desktop / SDK / MCP-server 最终汇入同一套 Turn 与工具管线。

---

*本文档由源码静态分析生成，实现细节以仓库当前版本为准。*
