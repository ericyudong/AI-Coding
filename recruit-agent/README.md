# RecruitOS 招聘管理系统

基于《招聘管理系统需求说明书 V1.0》与《HR Agent 共性需求汇总》落地的可运行系统：

- **RecruitOS**：招聘业务系统（数据、规则、权限、执行与审计）
- **HR Agent**：AI 能力服务（理解、生成、推荐）；RecruitOS 依赖其提供 AI

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React + TypeScript + Vite + Ant Design + Recharts |
| RecruitOS 后端 | Express + TypeScript + Prisma + SQLite |
| HR Agent | Express + TypeScript（OpenAI 兼容 LLM，可无 Key 离线 mock） |
| 认证 | JWT + 角色权限 |

## 架构关系

```
前端 / RecruitOS 业务 API
        │
        │  AI 请求（草稿/解析/对话/分析…）
        ▼
   HR Agent (:3002)
        │
        │  工具回调（查询/草稿/动作）
        ▼
   RecruitOS API (:3001)  ← 数据与执行
```

## 快速启动

```bash
# 1. 安装并初始化（首次）
npm run setup

# 2. 启动 RecruitOS 后端（:3001）
npm run dev:backend

# 3. 启动 HR Agent（:3002）
npm run dev:hr-agent

# 4. 启动前端（:5173）
npm run dev:frontend
```

浏览器打开 http://localhost:5173 ，使用演示账号登录。侧边栏「HR Agent」可对话与调用场景能力。

可选：在 `hr-agent/.env` 配置 `OPENAI_API_KEY`（及 `OPENAI_BASE_URL` / `OPENAI_MODEL`）启用真实 LLM；未配置时使用内置规则引擎，仍可联调全流程。

## 演示账号

密码均为 `123456`：

| 用户名 | 角色 |
|--------|------|
| `admin` | 系统管理员 |
| `lead` | 招聘负责人 |
| `hr` | 招聘HR |
| `dept` | 用人部门负责人 |
| `interviewer` | 面试官 |
| `approver` | Offer审批人 |
| `ops` | 人事运营 |
| `viewer` | 数据查看人 |

## 目录结构

```
recruit-agent/
├── backend/          # RecruitOS API + Prisma + SQLite
├── frontend/         # React 管理后台
├── hr-agent/         # HR Agent AI 服务
├── docs/             # 架构与需求导出
└── README.md
```

## 第二阶段 + HR Agent

| 模块 | 入口 | 说明 |
|------|------|------|
| HR Agent 工作台 | `/agent` | 对话、JD/初筛/排期/评价汇总/人才推荐/Offer草稿/NLQ 等 |
| RecruitOS→Agent | `/api/ai/*` | 代理到 HR Agent，转发用户 JWT |
| Agent→RecruitOS | `/api/agent/*` 等 | 结构化查询、草稿、受控动作 |
| 岗位标准/流程/渠道/消息/外链 | 见侧边栏 | 二期基础能力 |

已启动场景（需求表「是否可启动=是」）：JD 生成、多渠道文案、简历解析与初筛、人才库推荐、面试协调、评价汇总、候选人沟通、Offer 草稿、数据分析。

暂缓：AI 寻聘助手、AI 视频面试（合规/成本风险）。

## 说明

- 外部渠道/消息/电子签/日历为可运行模拟实现。
- 附件目录：`backend/uploads/`
- 重置演示数据：`npm --prefix backend run db:reset`
