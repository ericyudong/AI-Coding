# LiteLLM User Context 管理分析

> 分析范围：Proxy 鉴权、请求装配、日志/花费归因、Guardrails、MCP、Dashboard UI。  
> 结论先行：权威身份对象是 `UserAPIKeyAuth`；可序列化复印件是 `metadata`/`litellm_metadata` 中的 `user_api_key_*`；应用侧客户是 `end_user_id`；`ContextVar` 只承载不可由客户端注入的内部信号。

---

## 1. 「User Context」指什么

本仓库里的 user context **不是** LLM `messages` 对话上下文，而是**多层身份 + 请求态元数据**：

| 概念 | 含义 | 典型字段 |
|------|------|----------|
| Virtual Key 身份 | 调用方使用的 LiteLLM API Key（落日志前会 hash） | `api_key` / `token` / `user_api_key_hash` |
| Internal User | 平台内部用户（可登录 UI、管理自己的 key） | `user_id`, `user_role`, `user_email` |
| Team / Org / Project | 租户层级，预算与模型权限的主载体 | `team_id`, `org_id`, `project_id` |
| End User / Customer | 应用侧终端用户 | `end_user_id` → SpendLogs 的 `end_user` |
| Request / Logging Context | 注入到 metadata 的权威字段 | `user_api_key_*`, `requester_*`, tags |
| UI Auth Context | Dashboard JWT / cookie 会话 | `AuthContext` 的 `userID`, `accessToken` |

**权威运行时对象**：`UserAPIKeyAuth`（`litellm/proxy/_types.py`）。几乎所有 proxy 路径都靠它做 authz、预算、限流、日志归因。

---

## 2. 架构总览

```
HTTP Request
    │
    ▼
FastAPI Depends(user_api_key_auth)
    │  解析 key / JWT / custom auth
    │  加载 key + team + user + end_user + org/project
    │  common_checks（模型权限、预算、blocked…）
    ▼
UserAPIKeyAuth  (request-scoped Python object)
    │
    ▼
add_litellm_data_to_request / LiteLLMProxyRequestSetup
    │  剥离客户端伪造的 user_api_key_*
    │  写入 metadata 或 litellm_metadata
    │  附带完整 user_api_key_auth 对象（MCP 等用）
    ▼
ProxyRequestProcessing / 各 endpoint
    │  function_setup → LiteLLMLoggingObj
    │  ProxyLogging.pre_call_hook（guardrails / rate limit）
    ▼
Router / litellm.acompletion(...)
    │  kwargs / litellm_params.metadata 携带身份
    ▼
Success/Failure callbacks + SpendLogs + Integrations
    │  StandardLoggingPayload.metadata (user_api_key_*)
    ▼
DB spend / Prometheus / Langfuse / Datadog / …
```

**传播方式**：以**显式传参**为主（`user_api_key_dict` → `data["metadata"]` → `kwargs`），不是全局 thread-local。`ContextVar` 只用于防伪造的内部信号。

---

## 3. 关键文件与职责

### 3.1 Auth / 身份

| 路径 | 角色 |
|------|------|
| `litellm/proxy/_types.py` | `UserAPIKeyAuth`、`LiteLLM_VerificationToken(View)`、角色枚举、User/Team/Org 模型 |
| `litellm/proxy/auth/user_api_key_auth.py` | FastAPI 依赖：`user_api_key_auth`；产出 `UserAPIKeyAuth` |
| `litellm/proxy/auth/auth_checks.py` | `common_checks`、`get_key/team/user/end_user_object`、预算校验 |
| `litellm/proxy/auth/auth_utils.py` | `get_end_user_id_from_request_body`、路由/模型解析 |
| `litellm/proxy/auth/handle_jwt.py` | JWT 身份映射 |
| `litellm/proxy/auth/route_checks.py` | 路由是否允许该角色访问 |
| `litellm/proxy/common_utils/user_api_key_cache.py` | Key/身份 DualCache（内存 + Redis） |

### 3.2 请求装配 / 生命周期

| 路径 | 角色 |
|------|------|
| `litellm/proxy/litellm_pre_call_utils.py` | **`add_litellm_data_to_request`**、`LiteLLMProxyRequestSetup`（注入/清洗 metadata） |
| `litellm/proxy/common_request_processing.py` | 统一 LLM 请求流水线 |
| `litellm/proxy/proxy_server.py` | 路由入口，大量 `Depends(user_api_key_auth)` |
| `litellm/proxy/utils.py` | **`ProxyLogging`**：pre/post hooks、guardrail 管道 |

### 3.3 Logging / Spend / Types

| 路径 | 角色 |
|------|------|
| `litellm/types/utils.py` | `StandardLoggingUserAPIKeyMetadata`、`StandardLoggingMetadata`、`StandardLoggingPayload` |
| `litellm/litellm_core_utils/litellm_logging.py` | 从 metadata 清洗出标准日志 payload |
| `litellm/litellm_core_utils/core_helpers.py` | `get_litellm_metadata_from_kwargs` |
| `litellm/litellm_core_utils/logging_worker.py` | 后台日志队列，`copy_context` 保留 ContextVar |
| `litellm/proxy/spend_tracking/` | SpendLogs 归因：`user` / `team_id` / `end_user` |
| `litellm/proxy/hooks/parallel_request_limiter_v3.py` | 按 key/user/team/end_user 限流 |
| `litellm/_internal_context.py` | `is_internal_call` ContextVar |

### 3.4 Guardrails / MCP / UI

| 路径 | 角色 |
|------|------|
| `litellm/integrations/custom_guardrail.py` | 从 kwargs/request_data 重建轻量 `UserAPIKeyAuth` |
| `litellm/proxy/guardrails/**` | 各 hook 接收 `user_api_key_dict` |
| `litellm/proxy/_experimental/mcp_server/auth/user_api_key_auth_mcp.py` | MCP 复用 `user_api_key_auth` |
| `litellm/proxy/_experimental/mcp_server/mcp_context.py` | toolset / instructions ContextVar |
| `ui/litellm-dashboard/src/contexts/AuthContext.tsx` | UI 会话：JWT cookie → userID/role/accessToken |

---

## 4. 核心数据结构

### 4.1 `UserAPIKeyAuth`（权威身份）

继承链：

```
LiteLLM_VerificationToken
  → LiteLLM_VerificationTokenView
    → UserAPIKeyAuth
```

**Key 层**（`LiteLLM_VerificationToken`）：

- `token`, `key_alias`, `spend`, `max_budget`, `models`
- `user_id`, `team_id`, `org_id`, `project_id`, `agent_id`
- `tpm_limit` / `rpm_limit`, `metadata`, `object_permission`, `router_settings` …

**联合视图**（`LiteLLM_VerificationTokenView`）：

- Team：`team_spend`, `team_max_budget`, `team_tpm/rpm_limit`, `team_metadata`, `team_member_*`
- End User：`end_user_id`, `end_user_tpm/rpm_limit`, `end_user_max_budget`
- Org / Project：`organization_*`, `project_*`

**Auth 扩展**（`UserAPIKeyAuth`）：

- `user_role`, `parent_otel_span`
- `user_tpm/rpm_limit`, `user_spend` / `user_max_budget`, `user_email`
- `request_route`, `jwt_claims`
- `budget_reservation`（`exclude=True`，不序列化）
- `team_object_permission` / `end_user_object_permission`

**安全要点**：构造时若传入明文 `api_key`，validator 会 hash（`sk-…` → SHA256；JWT → `hashed-jwt-…`）。日志侧只见哈希。

### 4.2 注入到请求的 `user_api_key_*`

由 `LiteLLMProxyRequestSetup.get_sanitized_user_information_from_key` 生成，类型为 `StandardLoggingUserAPIKeyMetadata`：

- `user_api_key_hash`, `user_api_key_alias`, `user_api_key_spend`, `user_api_key_max_budget`
- `user_api_key_team_id` / `team_alias` / `org_*` / `project_*`
- `user_api_key_user_id` / `user_email` / `end_user_id` / `request_route`
- `user_api_key_auth_metadata`（key.metadata）
- `user_api_key_budget_reset_at`

`add_user_api_key_auth_to_request_metadata` 还会额外写入：

- 完整 `user_api_key_auth` 对象（供 MCP 等需要完整权限对象的路径）
- `agent_id`、`user_api_end_user_max_budget`、可选 `budget_reservation`

### 4.3 `metadata` vs `litellm_metadata`

| 容器 | 使用场景 |
|------|----------|
| `metadata` | 多数 chat/completion 路由 |
| `litellm_metadata` | Assistants/Threads 及部分新 API（避免与 OpenAI 的 `metadata` 冲突） |

SDK/logging 侧通过 `get_litellm_metadata_from_kwargs` 统一读取，优先 `litellm_metadata`。

### 4.4 角色枚举 `LitellmUserRoles`

`proxy_admin` / `proxy_admin_viewer` / `org_admin` / `internal_user` / `internal_user_viewer` / `team` / `customer`。

决定 UI 与 management API 的可见范围；LLM 调用路径上更关键的是 **key + team + end_user 的权限与预算**。

---

## 5. 请求生命周期（数据流）

### Phase A — Auth

入口：`user_api_key_auth`（`litellm/proxy/auth/user_api_key_auth.py`）。

1. 在读 body 前创建 OTEL parent span，挂到 `request.state`。
2. `_user_api_key_auth_builder`：
   - 自定义 / enterprise auth（可直接返回 `UserAPIKeyAuth`）
   - JWT / OAuth2 / master key / virtual key（DB + `UserApiKeyCache`）
   - 组装 team / user / end_user / org / project 字段
3. `RouteChecks.should_call_route` + 集中式 `_run_centralized_common_checks` → `common_checks`：
   - blocked、模型访问、team/user/end_user/org/project 预算
   - 可选 `enforce_end_user`、vector store 等
4. 若 builder 未设 `end_user_id`，再从 body/header **兜底解析**，保证 spend 归因。

**End-user 解析优先级**（`get_end_user_id_from_request_body`）：

1. 标准 customer header
2. `user_header_mappings` / 废弃的 `user_header_name`
3. body `user`（OpenAI 风格）
4. `litellm_metadata.user`
5. `metadata.user_id`
6. `safety_identifier`（Responses API；文档注明不可信环境勿依赖）

另外，`add_litellm_data_to_request` 里可用 header 映射覆盖 **internal `user_id`**，或把 header user 写入 `end_user_id` + OpenAI `user` 字段。

### Phase B — 请求增强（安全关键）

`add_litellm_data_to_request`：

1. **安全剥离**：根字段与 `metadata`/`litellm_metadata` 中所有以 `user_api_key_` 开头的字段，以及 guardrail/pipeline 控制字段、callback 注册字段、定价覆盖等
2. 构建 `proxy_server_request`（审计快照；不含 `secret_fields`）
3. **`add_user_api_key_auth_to_request_metadata`**：写入权威 `user_api_key_*` + 完整 `UserAPIKeyAuth`
4. 合并 key/team/project tags、spend_logs_metadata、budget 字段、headers、OTEL span
5. 可选：`add_user_information_to_llm_headers` → 上游 `x-litellm-user_api_key_*`

核心安全注释（代码意图）：客户端伪造的 `user_api_key_*` 必须先剥掉，再由 proxy 用鉴权结果重写。

### Phase C — Completion / Router

`ProxyBaseLLMRequestProcessing.common_processing_pre_call_logic`：

- 调用 `add_litellm_data_to_request`
- `litellm.utils.function_setup` → `LiteLLMLoggingObj`（metadata 进入 logging）
- `proxy_logging_obj.pre_call_hook(user_api_key_dict=…)` → rate limit / guardrails / policies
- 按 key/team 的 `router_settings` 覆盖调用 router

### Phase D — Logging / Spend

- `StandardLoggingPayloadSetup.get_standard_logging_metadata` 只保留白名单 `user_api_key_*` 等字段
- SpendLogs 归因三轴：
  - `user` ← `user_api_key_user_id`（internal user）
  - `team_id` ← `user_api_key_team_id`
  - `end_user` ← `end_user_id`（customer）
  - `api_key` ← hash
- 集成（Prometheus、Langfuse、Datadog、PostHog…）读 `standard_logging_object["metadata"]`

---

## 6. ContextVar / 异步上下文

| ContextVar | 用途 |
|------------|------|
| `litellm._internal_context.is_internal_call` | 内部嵌套调用跳过 async logging/billing；**不可由 HTTP body 设置** |
| MCP `_mcp_active_toolset_id` | 服务端按 toolset 路由设置；防客户端伪造 |
| MCP `_mcp_gateway_initialize_instructions` | 每请求 Initialize instructions |
| OpenAPI MCP `_request_auth_header` / `_request_extra_headers` | BYOK / 转发头注入本地 tool handler |
| `contextvars.copy_context()` | SDK 同步包装、`LoggingWorker` 后台任务保留原任务上下文 |

**设计意图**：

- 租户身份走 **metadata 显式传递**
- ContextVar 只承载「客户端绝不能伪造」的信号
- Async 下 ContextVar 按 task 隔离；`asyncio.create_task` 会复制当前 context

`request.state` 另存：`parent_otel_span`、`litellm_received_at`（与 `UserAPIKeyAuth` 互补，不是身份主体）。

---

## 7. 各子系统如何消费 User Context

### 7.1 Authz

- 模型：`can_team_access_model` / `can_user_call_model` / key `models` / access groups
- 路由：`RouteChecks` + `allowed_routes`
- 对象：`object_permission`（MCP servers、vector stores、agents…）
- 管理 API：`user_role` + admin view 判断

### 7.2 Budgets / Rate limits

- Auth 时：`common_checks` 查 key/team/user/end_user/org/project 预算
- 运行时 hooks：`parallel_request_limiter_v3`（key/user/team/end_user RPM/TPM）、`model_max_budget_limiter`、`budget_reservation`
- Prometheus：读 metadata 里的 `user_api_key_*_spend/max_budget`

### 7.3 Spend tracking

- 权威源：鉴权注入的 metadata，不是客户端自报身份
- SpendLogs 三轴：internal `user`、`team_id`、customer `end_user`
- 可选 `spend_logs_metadata`、`tags`、`agent_id`、`session_id` / `trace_id`

### 7.4 Logging / Observability

- `StandardLoggingPayload.metadata` 承载标准身份维度
- OTEL：`parent_otel_span` + traceparent
- 部分集成用 `user_api_key_auth_metadata` 做 project 覆盖

### 7.5 Guardrails

- `ProxyLogging.pre_call_hook(..., user_api_key_dict)`
- 权限：`user_api_key_dict.permissions`、team metadata 的 `disable_global_guardrails` / `opted_out_global_guardrails`
- 部分 guardrail 可配置是否把 `user_api_key_user_id` / `team_id` 发到上游
- Custom guardrail 可从 kwargs 的 `user_api_key_*` 重建 auth

### 7.6 MCP

- `MCPRequestHandler.process_mcp_request` → 复用 `user_api_key_auth`（oauth2 委托上游时可为空 auth）
- 工具权限：`user_api_key_auth.object_permission` / toolset
- Responses/Chat MCP handler：从 `litellm_metadata.user_api_key_auth` 取完整对象
- ContextVar：toolset 范围、BYOK Authorization、extra headers

### 7.7 Batch / Managed Files

- Batch rate limiter / managed files 路径需要显式传入 `user_api_key_dict`
- 缺少 user context 时，managed files 访问会失败（测试明确覆盖「有/无 context」行为）

---

## 8. UI Dashboard 侧

`ui/litellm-dashboard/src/contexts/AuthContext.tsx`：

- 从 cookie 读 JWT → `userID` / `userRole` / `userEmail` / `accessToken`
- Token **禁止写 `localStorage`**（XSS 风险）；MCP OAuth 等用 **`sessionStorage`**
- Usage 页面：非 admin / “my-usage” 强制自己的 `user_id`
- Keys/Users/Teams 页面按角色过滤

**重要区分**：UI JWT 会话与 Proxy LLM 请求的 `UserAPIKeyAuth` 是**两套会话**：

- UI：JWT 管理平台资源
- 应用：Virtual Key 调 LLM（可再带 `user` / `end_user`）

UI 的 `userID` **不会**自动变成 LLM 调用的 `user_api_key_user_id`，除非该 JWT/key 本身绑定了该 user。

---

## 9. 设计决策与模式

1. **单一通行证对象** `UserAPIKeyAuth`，贯穿 Depends → hooks → MCP。
2. **显式 metadata 传播**，避免隐式全局状态；ContextVar 仅防伪造。
3. **信任边界**：代理重写所有 `user_api_key_*`；客户端伪造会被 strip。
4. **双轨身份**：`user_id`（key 所有者）≠ `end_user_id`（应用客户）；spend 两列都记。
5. **Key 永不明文落日志**：构造即 hash。
6. **层级控制合并**：tags / budget / guardrail opt-out 按 key → team → project 合并；请求侧 tags 可叠加。
7. **缓存**：`UserApiKeyCache` 降低热路径 DB 压力。
8. **metadata 命名分裂**：历史 `metadata` vs 新 `litellm_metadata`，读取侧用统一 helper。

---

## 10. 边缘情况与陷阱

1. **伪造身份**：只改 body `metadata.user_api_key_user_id` 无效；但 **`user` / `safety_identifier` / 自定义 header** 可影响 `end_user_id`（需网络与配置信任）。
2. **Custom auth early return**：builder 有多条捷径；外层补 `end_user_id` 与统一 `common_checks` 防漏检。
3. **`user_api_key_auth` 进 metadata**：含 Span 等不可 JSON 序列化对象；Spend/StandardLogging 会清洗，直接 dump 全量 metadata 可能失败。
4. **Assistants 路由**：身份在 `litellm_metadata`；只读 `metadata` 会丢上下文。
5. **MCP oauth2 `delegate_auth_to_upstream`**：可无 LiteLLM key → 空 `UserAPIKeyAuth`，spend/限流归因变弱。
6. **Header 映射双用途**：可设 internal `user_id` 或 customer `end_user`；配错会搞乱预算归属。
7. **内部嵌套 LLM**：须设 `is_internal_call`，否则重复计费/打点。
8. **LoggingWorker**：依赖 `copy_context()`；跨 loop / 错误丢 context 可能丢内部 ContextVar（身份仍在 kwargs metadata）。
9. **Master / 系统账户**：health/CLI/jobs 用合成 `UserAPIKeyAuth`，会出现在 spend。
10. **Admin UI vs API Key**：两套会话，不要假设 UI 登录身份会自动进入 LLM spend 归因。

---

## 11. 心智模型（一句话）

**`UserAPIKeyAuth` = 鉴权后的租户护照；`metadata.user_api_key_*` = 护照的可序列化复印件；`end_user_id` = 应用客户贴纸；ContextVar = 防伪内章。**

整条链路靠显式传递复印件做预算、限流、日志与 guardrail，而不是靠线程全局变量。

---

## 12. 快速导航（读代码入口）

若要深入某一段，建议按此顺序阅读：

1. `litellm/proxy/_types.py` — `UserAPIKeyAuth` 字段定义  
2. `litellm/proxy/auth/user_api_key_auth.py` — 鉴权入口  
3. `litellm/proxy/auth/auth_checks.py` — `common_checks`  
4. `litellm/proxy/auth/auth_utils.py` — `get_end_user_id_from_request_body`  
5. `litellm/proxy/litellm_pre_call_utils.py` — `add_litellm_data_to_request` / strip & inject  
6. `litellm/types/utils.py` — `StandardLoggingUserAPIKeyMetadata`  
7. `litellm/_internal_context.py` — 内部 ContextVar  
8. `ui/litellm-dashboard/src/contexts/AuthContext.tsx` — UI 会话
