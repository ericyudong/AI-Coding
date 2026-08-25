# DeepSeek Harness 插件集成

RecruitOS / HR Agent 已封装为 DeepSeek Harness 插件 `@deepseek-ai/dsh-recruit-agent`，源码位于 monorepo：

`deepseek-harness-master/packages/examples/recruit-agent`

## 架构变化

```
DeepSeek Harness (dsh)
  └── @deepseek-ai/dsh-recruit-agent 插件
        ├── Skills: hr-recruitment, hr-jd, hr-resume, …
        ├── Tools: recruitos_*, hr_agent_invoke
        └── HTTP → RecruitOS (:3001) + HR Agent (:3002)
```

原先的独立 HR Agent Express 服务仍保留，Harness 通过 `hr_agent_invoke` 调用其 REST API；结构化查询与草稿/动作走 `recruitos_*` 工具直连 RecruitOS。

## 快速使用

### 1. 启动 RecruitOS 栈

```bash
npm run setup
npm run dev:backend
npm run dev:hr-agent
```

### 2. 配置 JWT

登录 http://localhost:5173 后，将 Bearer Token 写入：

```bash
export RECRUITOS_JWT="<token>"
export DEEPSEEK_API_KEY="<key>"
```

### 3. 在 Harness 中运行

```bash
cd ../deepseek-harness-master
# 默认 headless profile 已挂载 recruit-agent 插件
pnpm dsh --profile headless "为后端岗位生成 JD"

# 或使用独立 patch 叠加更多配置
pnpm dsh --patch examples/recruit-agent/cordis.yml "分析本周招聘漏斗"
```

## 工具说明

| 工具 | 说明 |
|------|------|
| `recruitos_query` | 查询 job / candidate / application / offer |
| `recruitos_search` | 关键词搜索 |
| `recruitos_save_draft` | 保存 AI 草稿 |
| `recruitos_propose_action` | 提议业务动作（需用户确认） |
| `hr_agent_invoke` | 调用 HR Agent AI（jd / resume_screen / offer 等） |

## cordis.yml 配置示例

```yaml
- id: recruit-agent
  name: '@deepseek-ai/dsh-recruit-agent'
  config:
    recruitosBaseUrl: http://127.0.0.1:3001
    hrAgentBaseUrl: http://127.0.0.1:3002
    # authToken 可选；默认读 RECRUITOS_JWT / RECRUITOS_TOKEN
```

## 与独立 hr-agent 服务的关系

- **hr-agent/**：仍可单独运行，供 RecruitOS 前端 `/api/ai/*` 代理调用
- **dsh 插件**：将相同能力暴露为 Harness 工具，适合 CLI / 自动化编排

两者共用 RecruitOS 后端数据与 JWT 鉴权模型。
