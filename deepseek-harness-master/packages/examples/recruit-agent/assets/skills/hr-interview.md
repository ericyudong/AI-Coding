# 面试协调与评价汇总

## 面试排期

`hr_agent_invoke` capability=`schedule`，body 可含 `applicationId`、`preferredSlots`、`interviewerIds` 等。

## 评价汇总

1. `recruitos_query` objectType=`application` 查看面试与评价记录
2. `hr_agent_invoke` capability=`summary`，body: `{ "applicationId" }`

## 输出要求

- 排期建议需考虑面试官冲突与候选人偏好
- 评价汇总需客观综合多方意见，标注分歧点
