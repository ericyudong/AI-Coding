# JD 生成与发布

## 何时使用

- 用人部门提出模糊需求，需要结构化 JD
- 已有岗位草稿，需要优化或生成多渠道文案

## 步骤

1. 若有 `jobId`，先用 `recruitos_query` objectType=`job` 拉取上下文
2. 调用 `hr_agent_invoke`：
   - capability=`jd`，body: `{ "jobId"?, "brief"?, "dialogue"?, "saveDraft"? }`
   - capability=`publish`，body: `{ "jobId" }`（需已有 JD）
3. 将结果用 `recruitos_save_draft` 保存，type 建议 `JD` 或 `PUBLISH_PACK`

## 输出要求

- JD 包含：职责、任职要求、薪资区间、工作地点、团队简介
- 多渠道文案需区分 BOSS / 猎聘 / 内推等语气差异
