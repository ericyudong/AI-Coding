# Offer 与入职衔接

## 步骤

1. `recruitos_query` objectType=`application` 确认候选人状态与审批进度
2. `hr_agent_invoke` capability=`offer`，body: `{ "applicationId", "salaryHint"?, "notes"? }`
3. 草稿满意后 `recruitos_save_draft` type=`OFFER`
4. 正式发起：`recruitos_propose_action` actionKey=`SEND_OFFER`（需用户在 RecruitOS 确认）

## 注意

- Offer 涉及薪酬与合规，默认只生成草稿，不自动发送
- 引用公司标准 Offer 模板与审批链
