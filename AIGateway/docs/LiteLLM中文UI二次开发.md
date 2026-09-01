# LiteLLM Admin UI 中文二次开发说明

官方 Admin UI 默认仅英文。本仓库在 `litellm-litellm_internal_staging/ui/litellm-dashboard` 中增加了轻量 i18n（中/英）。

## 已覆盖（概览）

- 登录、侧边栏、顶栏语言切换、Ant Design 语言包
- Virtual Keys / Usage / Teams / Models / Organizations / Users（含详情）
- Health Check、Logs、Deleted Keys/Teams
- Settings 壳层 + UI/SSO/Logging/Vault/SCIM/Email 主文案、Router 路由/回退
- **Guardrails / Policies / MCP / Vector Stores / Caching**
- **Prompts / Budgets / Tags / Tools / API Playground**
- **AI Hub（Model/Agent/MCP/Skill）/ Test Key（ChatUI 配置区）**

词条约 **920+**，约 **70+** 个组件已 `useI18n`。偏好：`localStorage: litellm_ui_locale`。

## 开发

```bash
cd litellm-litellm_internal_staging/ui/litellm-dashboard
npm install && npm run dev
```

## 扩展

1. `src/i18n/locales/en.ts` 加词条  
2. `src/i18n/locales/zh.ts` 补同名 key  
3. `const { t } = useI18n()` 写在组件函数体内（勿插入参数列表）  
4. JSX 属性用 `title={t("...")}`，对象字段用 `label: t("...")`，不要写成 `"{t("...")}"`

## 仍可能残留英文

深层弹窗/表单字段、部分通知 toast、公开 Model Hub 页、Claude Code Plugins、个别实验页细节等。可按页面继续补词条。
