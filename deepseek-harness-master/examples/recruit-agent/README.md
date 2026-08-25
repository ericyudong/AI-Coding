# RecruitOS HR Agent（DeepSeek Harness）

在 DeepSeek Harness 中驱动 RecruitOS 招聘系统与 HR Agent AI 能力。

## 前置条件

1. 启动 RecruitOS（见同级仓库 `recruit-agent`）：

```bash
cd ../../../recruit-agent
npm run setup
npm run dev:backend    # :3001
npm run dev:hr-agent   # :3002
```

2. 登录 RecruitOS 获取 JWT，写入环境变量：

```bash
export RECRUITOS_JWT="<your-bearer-token>"
export DEEPSEEK_API_KEY="<your-key>"
```

## 运行

从 harness 根目录：

```bash
pnpm dsh --patch examples/recruit-agent/cordis.yml "为 job-xxx 生成一份后端工程师 JD"
```

或使用 headless 示例叠加本 patch：

```bash
pnpm dsh --profile headless --patch examples/recruit-agent/cordis.yml "分析本周招聘漏斗"
```

## 插件能力

| 类型 | 名称 |
|------|------|
| Skills | `hr-recruitment`, `hr-jd`, `hr-resume`, `hr-interview`, `hr-offer`, `hr-analytics` |
| Tools | `recruitos_query`, `recruitos_search`, `recruitos_save_draft`, `recruitos_propose_action`, `hr_agent_invoke` |

实现包：`@deepseek-ai/dsh-recruit-agent`（`packages/examples/recruit-agent`）。
