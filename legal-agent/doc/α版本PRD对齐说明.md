# 法务Agent α版本 PRD 对齐说明

> 基于 `α版本PRD_Part1/Part2` 的落地交付说明（含后续非阻塞能力）

## 已完成

### 信息架构 / 权限 / 合同 / 履约（α）
- 工作台四模块、7 角色、部门数据隔离、异步导入、标签摘要审计、履约助手等（见产品设计文档）

### 邮件预警
- `email_service` + `performance_alerts.email_status/sent_at/error`
- 后台定时任务 `alert_scheduler`（默认 15 分钟）刷新预警并尝试发信
- SMTP 默认关闭：状态记为 `skipped`；配置 `SMTP_ENABLED=true` 后真实发送
- 手动派发：`POST /performance/alerts/dispatch`

### 证据文件对象存储
- 本地对象存储目录 `data/objects/performance_evidence/`
- `POST /performance/nodes/{id}/evidence` 上传；调整申请绑定 `evidence_path`
- `GET /performance/adjustments/{id}/evidence` 鉴权下载

### 标签体系后台
- 表 `tag_taxonomy`，启动种子采购/销售/通用树
- 管理页 `/admin/tags`；合同详情编辑校验 L1/L2
- `GET /cms/tags/taxonomy` 供前端下拉

### ERP / 订单同步
- CSV 导入：`POST /performance/orders/import`
- 订单列表 / 人工关联 / 同步任务；页面 `/performance/orders`
- `ERP_SYNC_MODE=manual_import`（默认）；`api` 模式预留

## 配置示例（`.env`）

```env
SMTP_ENABLED=false
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=legal-agent@example.com
PERFORMANCE_ALERT_INTERVAL_SECONDS=900
ERP_SYNC_MODE=manual_import
```

## 重启

```bat
start.bat
```

登录：`admin` / `admin123`
