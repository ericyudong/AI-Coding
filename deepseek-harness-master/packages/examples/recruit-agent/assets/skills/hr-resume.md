# 简历解析与初筛

## 何时使用

- 新简历入库后需结构化解析
- 针对具体岗位做匹配度初筛

## 步骤

1. `recruitos_query` objectType=`candidate` 获取候选人资料（如有）
2. 解析：`hr_agent_invoke` capability=`resume_parse`，body: `{ "candidateId" }`
3. 初筛：`hr_agent_invoke` capability=`resume_screen`，body: `{ "candidateId", "jobId" }`

## 输出要求

- 给出匹配分、亮点、风险点、是否建议进入面试
- 不编造简历中未出现的技术栈或经历
