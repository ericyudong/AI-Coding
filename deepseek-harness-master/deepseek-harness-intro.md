---
marp: true
theme: default
paginate: true
lang: zh-CN
style: |
  section {
    font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
    background-color: #f8fafc;
    color: #1e293b;
  }
  h1 {
    color: #0f172a;
    border-bottom: 2px solid #3b82f6;
    padding-bottom: 10px;
  }
  h2 {
    color: #1e40af;
  }
  ul {
    line-height: 1.6;
  }
  code {
    background: #e2e8f0;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.9em;
  }
---

# DeepSeek Harness
## 下一代插件化 AI Agent 基础设施

**基于 Cordis 框架构建的全栈式 Agent 运行时**

---

## 🎯 核心愿景

DeepSeek Harness (DSH) 是一个**完全插件化**的 Agent 执行环境。

- **一切皆插件**：从模型适配器、工具注册到会话日志和 Agent 循环本身，所有组件均可通过配置替换。
- **无特权内核**：没有需要修补的核心代码；通过挂载新插件来扩展功能。
- **可逆副作用**：所有注册都是可撤销的 Effect，插件卸载时自动清理资源。
- **多模态运行**：支持 Web GUI、Headless CLI、ACP 自动化服务器等多种 Profile。

---

## 🏗️ 架构基石：Cordis 框架

DSH 构建在 vendored Cordis 之上，提供以下核心能力：

| 概念 | 描述 |
| :--- | :--- |
| **Context (`ctx`)** | 共享上下文，承载所有服务和事件总线 |
| **Service Definition** | 声明能力接口（如 `ctx.llm`, `ctx.tools`） |
| **Typed Events** | 强类型事件系统，支持 Waterfall 和 Serial 模式 |
| **Effects** | 可组合、可清理的副作用注册机制 |
| **Scopes** | 每个 Agent 拥有独立的注册作用域 |

> 💡 扩展 DSH = 编写一个 Cordis 插件 + 在 cordis.yml 中挂载

---

## 📦 Profile 与 Bundle 体系

运行时由多层配置组合而成，支持灵活的定制与覆盖：

```text
[Base Layer] → [Bundle A] → [Bundle B] → [Profile Patch] → [User Patch]
```

- **Profile**: 命名的插件组合模板（如 `web`, `headless`）
- **Bundle**: 可分发的配置+代码单元，支持分层补丁
- **Patch**: 针对特定行的配置替换或插入
- **查看实际启动树**: `dsh --profile web --dump-config`

每一层都可以被上层覆盖，实现真正的"可组装架构"。

---

## 🔧 核心子系统

| 包名 | 职责 | Context Key |
| :--- | :--- | :--- |
| `core/session` | 追加式 SessionEvent 日志与内存存储 | `ctx.sessions` |
| `core/system-prompt` | Prompt 片段与 Tool Schema 组装 | `ctx.systemPrompt` |
| `core/tools` | 作用域工具注册与守卫执行管道 | `ctx.tools` |
| `core/agent-loop` | 默认 Agent 驱动实现 | `ctx.agentLoop` |
| `llm/llm` | LLM 消息/流词汇表与适配器接缝 | `ctx.llm` |
| `subagent` | 子代理委派与隔离执行 | `ctx.subagents` |

---

## 🔄 Turn 与 Step 生命周期

Agent 的执行流被精确建模为可观测的事件序列：

```text
turn/start
  ├─ claim input + queued message
  ├─ agent/pre-step (Waterfall: 可重写/拒绝)
  │   └─ step/start
  │       ├─ derive model history from log
  │       ├─ agent/request → llm/stream → assistant/message
  │       ├─ tool/call → tools/execute → tool/result
  │       └─ step/end
  └─ agent/turn-stopping
turn/end
```

- **Model-visible ⟺ Logged**: 任何到达模型的输入都必须可从日志重建
- **Waterfall 语义**: 监听器必须调用 `next()` 以委托给下一环节

---

## 🛠️ Capability Seams（能力接缝）

每个可替换能力都包含三个角色：

1. **Service Definition**: 声明接口契约（TypeScript Interface）
2. **Service Provider**: 具体实现（如 DeepSeek API、本地 Shell）
3. **Consumer**: 使用方（通常是面向模型的工具）

> ✅ 完整的能力 = Definition + Provider + Consumer  
> ❌ 单一角色不构成 Seam

示例：`fs` 能力包含文件系统接口定义、本地/E2B 提供者、以及 `read/write/edit` 工具消费者。

---

## 🌐 多运行时支持

DSH 支持多种执行环境和后端：

- **Web App**: 基于 Vite + Vue 的浏览器端 GUI (`apps/web`)
- **Headless**: 无服务器的一次性任务执行器
- **ACP Server**: Agent Client Protocol 自动化服务端
- **E2B Sandbox**: 云端安全沙箱执行环境
- **Local Shell**: 本地 Bash/PowerShell 进程树管理
- **Python SDK**: 独立的 Python 客户端与运行时绑定

---

## 📝 开发规范亮点

- **ESM Only**: 全项目 `"type": "module"`，Node ^22.19 || >=24
- **Strict TypeScript**: `strict: true` + `noImplicitAny`，禁止隐式 any
- **Effect-Based Registration**: 所有贡献通过 `ctx.effect()` / `ctx.on()`
- **Session Log as Source of Truth**: 模型可见内容必须可重放
- **Branded IDs**: 跨边界 ID 使用 `Branded<B>` 防止混淆
- **Documentation Tiers**: 严格的事实归属层级，避免重复叙述

---

## 🚀 快速开始

```bash
# 安装依赖
pnpm install

# 启动 Web GUI
pnpm run dev:web

# 运行 Headless 任务
pnpm dsh --profile headless "分析当前目录结构"

# 运行测试
pnpm run test

# 构建所有包
pnpm run build
```

> 🔑 真实 API 测试需要设置 `DEEPSEEK_API_KEY`

---

## 📚 相关资源

- **架构文档**: `docs/architecture.md`
- **Cordis 入门**: `docs/cordis-primer.md`
- **包目录**: `packages/README.md`
- **Agent Notes**: `.agents/notes/` (决策记录)
- **Cookbook**: `docs/cookbook/` (操作指南)
- **GitHub**: DeepSeek Harness Repository

---

<!-- _footer: 'Generated for DeepSeek Harness Project | Qwen3.7-Max' -->
