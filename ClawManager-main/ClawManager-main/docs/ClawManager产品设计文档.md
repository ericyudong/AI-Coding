# ClawManager 产品设计文档

## 1. 产品概述

### 1.1 产品简介

ClawManager 是一个基于 Kubernetes 的虚拟桌面管理平台，专门用于管理 OpenClaw 和 Linux 桌面运行实例，支持团队级和集群级的桌面运行环境部署与管理。

### 1.2 核心价值

- **统一管理平面**：一个管理员面板管理用户、配额、实例和运行时镜像
- **OpenClaw 支持**：支持 OpenClaw 内存和偏好的导入/导出
- **安全访问**：通过平台进行安全的桌面访问，无需直接暴露 Pod
- **AI Gateway**：提供模型访问治理、审计追踪、成本分析和风险控制
- **Kubernetes 原生**：基于 Kubernetes 的部署和运维流程

### 1.3 主要特性

- 桌面实例生命周期管理：创建、启动、停止、重启、删除、检查和同步
- 运行时类型支持：`openclaw`、`webtop`、`ubuntu`、`debian`、`centos`、`custom`
- 运行时镜像卡管理
- 用户配额控制：CPU、内存、存储、GPU 和实例数量
- 集群资源概览：节点、CPU、内存和存储
- 基于 Token 的桌面访问，带有 WebSocket 转发
- AI Gateway：模型管理、审计日志、成本会计和风险控制
- CSV 批量用户导入
- 多语言界面支持

---

## 2. 系统架构

### 2.1 整体架构

```
浏览器
  └── ClawManager 前端 (React 19)
      └── ClawManager 后端 (Go 1.21+)
          ├── MySQL 数据库
          └── Kubernetes API
              ├── Pod / PVC / Service
              └── OpenClaw / Webtop / Linux 桌面运行时
```

### 2.2 技术栈

| 层次 | 技术选型 |
|------|----------|
| 前端框架 | React 19 |
| 前端构建工具 | Vite |
| 前端样式 | Tailwind CSS |
| 后端语言 | Go 1.21+ |
| Web 框架 | Gin |
| 数据库 | MySQL |
| 容器编排 | Kubernetes |
| 认证 | JWT |

### 2.3 系统组件

#### 2.3.1 前端组件

```
frontend/src/
├── components/          # 公共组件
│   ├── AdminLayout.tsx          # 管理员布局
│   ├── UserLayout.tsx           # 用户布局
│   ├── InstanceAccess.tsx       # 实例访问组件
│   ├── LanguageSwitcher.tsx     # 语言切换器
│   └── ...
├── pages/               # 页面组件
│   ├── admin/                   # 管理页面
│   │   ├── AdminDashboard.tsx       # 管理员仪表盘
│   │   ├── UserManagementPage.tsx   # 用户管理
│   │   ├── InstanceManagementPage.tsx  # 实例管理
│   │   ├── AIGatewayPage.tsx       # AI Gateway 页面
│   │   ├── AIAuditPage.tsx         # AI 审计页面
│   │   ├── CostsPage.tsx           # 成本页面
│   │   ├── RiskRulesPage.tsx       # 风险规则页面
│   │   ├── ModelManagementPage.tsx # 模型管理
│   │   └── SystemSettingsPage.tsx  # 系统设置
│   ├── auth/             # 认证页面
│   │   ├── LoginPage.tsx
│   │   └── RegisterPage.tsx
│   ├── dashboard/        # 仪表盘
│   │   └── UserDashboard.tsx
│   ├── instances/        # 实例页面
│   │   ├── CreateInstancePage.tsx  # 创建实例
│   │   ├── InstanceListPage.tsx    # 实例列表
│   │   ├── InstanceDetailPage.tsx  # 实例详情
│   │   └── InstancePortalPage.tsx  # 实例门户
│   └── settings/         # 设置页面
├── services/             # API 服务
│   ├── api.ts
│   ├── authService.ts
│   ├── instanceService.ts
│   ├── userService.ts
│   ├── modelService.ts
│   ├── adminService.ts
│   └── ...
├── stores/               # 状态管理
├── contexts/             # React Context
│   ├── AuthContext.tsx
│   └── I18nContext.tsx
├── hooks/                # 自定义 Hooks
├── types/                # TypeScript 类型定义
└── router/               # 路由配置
```

#### 2.3.2 后端组件

```
backend/
├── cmd/
│   ├── server/           # 主服务入口
│   ├── initdb/           # 数据库初始化
│   └── fixpassword/      # 密码修复工具
├── internal/
│   ├── aigateway/        # AI Gateway 核心服务
│   │   └── service.go
│   ├── config/           # 配置管理
│   │   └── config.go
│   ├── db/               # 数据库连接
│   │   └── db.go
│   ├── handlers/         # HTTP 处理器
│   │   ├── auth_handler.go          # 认证
│   │   ├── user_handler.go          # 用户管理
│   │   ├── instance_handler.go      # 实例管理
│   │   ├── ai_gateway_handler.go    # AI Gateway
│   │   ├── ai_observability_handler.go  # AI 可观测性
│   │   ├── cluster_resource_handler.go  # 集群资源
│   │   ├── risk_rule_handler.go     # 风险规则
│   │   ├── llm_model_handler.go     # LLM 模型
│   │   ├── system_settings_handler.go  # 系统设置
│   │   ├── websocket_handler.go     # WebSocket
│   │   └── egress_proxy_handler.go  # 出站代理
│   ├── middleware/       # 中间件
│   │   ├── auth_middleware.go       # 认证中间件
│   │   ├── rbac_middleware.go       # RBAC 中间件
│   │   ├── cors_middleware.go       # CORS 中间件
│   │   └── error_handler.go         # 错误处理
│   ├── models/           # 数据模型
│   │   ├── user.go               # 用户模型
│   │   ├── instance.go           # 实例模型
│   │   ├── llm_model.go          # LLM 模型
│   │   ├── audit_log.go          # 审计日志
│   │   ├── cost_record.go        # 成本记录
│   │   ├── risk_rule.go          # 风险规则
│   │   ├── risk_hit.go           # 风险命中
│   │   ├── backup.go             # 备份
│   │   └── ...
│   ├── repository/       # 数据访问层
│   │   ├── user_repository.go
│   │   ├── instance_repository.go
│   │   ├── llm_model_repository.go
│   │   ├── audit_event_repository.go
│   │   ├── cost_record_repository.go
│   │   └── ...
│   ├── services/         # 业务逻辑层
│   │   ├── auth_service.go          # 认证服务
│   │   ├── user_service.go          # 用户服务
│   │   ├── instance_service.go      # 实例服务
│   │   ├── llm_model_service.go     # LLM 模型服务
│   │   ├── ai_gateway_service.go    # AI Gateway
│   │   ├── ai_observability_service.go  # AI 可观测性
│   │   ├── cluster_resource_service.go  # 集群资源
│   │   ├── cost_record_service.go   # 成本记录
│   │   ├── risk_detection_service.go # 风险检测
│   │   ├── quota_service.go         # 配额服务
│   │   ├── websocket_service.go     # WebSocket 服务
│   │   └── k8s/                     # Kubernetes 交互
│   └── utils/            # 工具函数
│       ├── jwt.go
│       ├── password.go
│       └── response.go
├── configs/              # 配置文件
│   ├── dev.yaml
│   └── k8s.yaml
└── deployments/          # 部署配置
    ├── docker/
    └── k8s/
```

---

## 3. 功能模块

### 3.1 用户管理模块

#### 3.1.1 功能描述

提供用户的创建、导入、认证和权限管理功能。

#### 3.1.2 功能列表

- **用户注册**：支持用户自行注册账号
- **用户登录**：JWT Token 认证登录
- **用户列表**：管理员查看所有用户
- **用户创建**：管理员手动创建用户
- **CSV 批量导入**：支持 CSV 格式批量导入用户
- **角色管理**：支持管理员和普通用户角色
- **配额分配**：为用户分配 CPU、内存、存储、GPU 和实例数量配额
- **密码管理**：修改密码、密码重置

#### 3.1.3 数据模型

```go
type User struct {
    ID           int        `json:"id"`
    Username     string     `json:"username"`
    Email        *string    `json:"email"`
    Password     string     `json:"-"`
    Role         string     `json:"role"`       // admin, user
    Status       string     `json:"status"`     // active, inactive
    CreatedAt    time.Time  `json:"created_at"`
    UpdatedAt    time.Time  `json:"updated_at"`
}

type UserQuota struct {
    UserID          int `json:"user_id"`
    MaxInstances    int `json:"max_instances"`
    MaxCPUCores     int `json:"max_cpu_cores"`
    MaxMemoryGB     int `json:"max_memory_gb"`
    MaxStorageGB    int `json:"max_storage_gb"`
    MaxGPUCount     int `json:"max_gpu_count"`
}
```

### 3.2 实例管理模块

#### 3.2.1 功能描述

管理虚拟桌面实例的完整生命周期。

#### 3.2.2 功能列表

- **实例创建**：创建 OpenClaw、Webtop 或 Linux 桌面实例
- **实例列表**：查看当前用户或所有用户的实例
- **实例详情**：查看实例详细信息和状态
- **实例启动**：启动指定的桌面实例
- **实例停止**：停止指定的桌面实例
- **实例重启**：重启指定的桌面实例
- **实例删除**：删除指定的桌面实例
- **实例同步**：强制同步实例状态
- **实例访问**：生成访问令牌，通过 WebSocket 访问桌面
- **OpenClaw 迁移**：
  - 导出 OpenClaw 内存和偏好设置
  - 导入 OpenClaw 内存和偏好设置
- **实例代理**：通过后端代理访问实例 Pod

#### 3.2.3 支持的运行时类型

| 类型 | 描述 |
|------|------|
| openclaw | OpenClaw 桌面环境 |
| webtop | Webtop 远程桌面 |
| ubuntu | Ubuntu 桌面 |
| debian | Debian 桌面 |
| centos | CentOS 桌面 |
| custom | 自定义镜像 |

#### 3.2.4 实例数据模型

```go
type Instance struct {
    ID             int        `json:"id"`
    UserID         int        `json:"user_id"`
    Name           string     `json:"name"`
    Description    *string    `json:"description"`
    Type           string     `json:"type"`            // openclaw, webtop, etc.
    Status         string     `json:"status"`          // pending, running, stopped, etc.
    CPUCores       int        `json:"cpu_cores"`
    MemoryGB       int        `json:"memory_gb"`
    DiskGB         int        `json:"disk_gb"`
    GPUEnabled     bool       `json:"gpu_enabled"`
    GPUType        *string    `json:"gpu_type"`
    GPUCount       int        `json:"gpu_count"`
    OSType         string     `json:"os_type"`
    OSVersion      string     `json:"os_version"`
    ImageRegistry  *string    `json:"image_registry"`
    ImageTag       *string    `json:"image_tag"`
    StorageClass   string     `json:"storage_class"`
    PodName        *string    `json:"pod_name"`
    PodNamespace   *string    `json:"pod_namespace"`
    PodIP          *string    `json:"pod_ip"`
    AccessURL      *string    `json:"access_url"`
    CreatedAt      time.Time  `json:"created_at"`
    UpdatedAt      time.Time  `json:"updated_at"`
    StartedAt      *time.Time `json:"started_at"`
    StoppedAt      *time.Time `json:"stopped_at"`
}
```

### 3.3 AI Gateway 模块

#### 3.3.1 功能描述

AI Gateway 是 ClawManager 中用于模型访问治理的核心组件，提供统一的 OpenAI 兼容接口，同时增加策略控制、审计和成本可见性。

#### 3.3.2 功能列表

##### 3.3.2.1 模型管理

- 统一访问和路由通过单一 OpenAI 兼容接口
- 提供商接入，发现和集中端点配置
- 分层模型治理：普通模型和安全模型
- 每个模型的激活、端点、凭证引用和定价控制

##### 3.3.2.2 审计和追踪

- 端到端可追踪性，带有 `trace_id`、会话 ID 和请求 ID 关联
- 持久化请求和响应负载日志，包括流式 SSE 响应
- 记录风险命中、路由决策和最终调用状态
- 按用户、模型、实例、时间窗口或 trace ID 搜索和审查

##### 3.3.2.3 成本会计

- 每次调用的提示、补全和总 token 跟踪
- 支持推理 token 和缓存 token 分类（如果有）
- 每个模型的定价，可配置的输入和输出费率及货币支持
- 外部模型估算成本计算，内部安全模型成本分配
- 用户、实例、模型和会话级别的成本分析

##### 3.3.2.4 风险控制

- 内置规则：隐私、企业敏感数据、金融和安全/合规场景
- 基于正则表达式和自定义规则扩展性
- 自动操作如 `block` 和 `route_secure_model`
- 透明治理决策记录在审计跟踪中
- 管理控制台规则测试和命中预览

#### 3.3.3 支持的模型服务提供商

| 提供商 | 说明 |
|--------|------|
| OpenAI | OpenAI 官方 API |
| OpenRouter | OpenRouter 聚合平台 |
| DeepSeek | DeepSeek 模型 |
| SiliconFlow | SiliconFlow 平台 |
| Moonshot AI | 月之暗面 Kimi |
| Zhipu AI | 智谱清言 |
| Alibaba DashScope | 阿里云 DashScope |
| Volcengine Ark | 火山引擎 Ark |
| xAI | xAI Grok |
| Together AI | Together AI 平台 |
| Fireworks AI | Fireworks AI |
| Perplexity | Perplexity AI |
| 01.AI | 01.AI Yi 系列 |
| MiniMax | MiniMax 模型 |
| Local/Internal | 本地/内部端点，支持 Ollama、One API 等 |

#### 3.3.4 路由逻辑

```
用户请求
    │
    ▼
是否指定模型? ──是──> 按 display_name 匹配活动模型
    │否
    ▼
选择第一个 is_secure=false 的模型
    │
    ▼
风险控制扫描
    │
    ├── 触发 route_secure_model ──> 切换到第一个活动安全模型
    │
    └── 未触发
            │
            ▼
    is_secure 标志判断
            │
            ├── true ──> 内部安全路由
            │
            └── false ──> 外部常规路由
```

#### 3.3.5 数据模型

```go
type LLMModel struct {
    ID              int        `json:"id"`
    ProviderType    string     `json:"provider_type"`   // openai, openrouter, etc.
    DisplayName     string     `json:"display_name"`
    ModelName       string     `json:"model_name"`
    Endpoint        string     `json:"endpoint"`
    APIKeyRef       string     `json:"api_key_ref"`
    IsSecure        bool       `json:"is_secure"`       // 安全模型标识
    IsActive        bool       `json:"is_active"`
    InputPrice      float64    `json:"input_price"`     // 输入价格
    OutputPrice     float64    `json:"output_price"`    // 输出价格
    Currency        string     `json:"currency"`
    CreatedAt       time.Time  `json:"created_at"`
    UpdatedAt       time.Time  `json:"updated_at"`
}

type ModelInvocation struct {
    ID              int        `json:"id"`
    TraceID         string     `json:"trace_id"`
    InstanceID      int        `json:"instance_id"`
    UserID          int        `json:"user_id"`
    ModelID         int        `json:"model_id"`
    ModelName       string     `json:"model_name"`
    ProviderType    string     `json:"provider_type"`
    RequestTokens   int        `json:"request_tokens"`
    ResponseTokens  int        `json:"response_tokens"`
    TotalTokens     int        `json:"total_tokens"`
    ReasoningTokens int        `json:"reasoning_tokens"`
    Status          string     `json:"status"`
    ErrorMessage    *string    `json:"error_message"`
    CreatedAt       time.Time  `json:"created_at"`
}

type RiskRule struct {
    ID          int        `json:"id"`
    Name        string     `json:"name"`
    RuleType    string     `json:"rule_type"`       // regex, custom
    Pattern     string     `json:"pattern"`
    Category    string     `json:"category"`        // privacy, finance, security, etc.
    Action      string     `json:"action"`          // block, route_secure_model
    IsActive    bool       `json:"is_active"`
    Priority    int        `json:"priority"`
    CreatedAt   time.Time  `json:"created_at"`
    UpdatedAt   time.Time  `json:"updated_at"`
}

type RiskHit struct {
    ID          int        `json:"id"`
    TraceID     string     `json:"trace_id"`
    RuleID      int        `json:"rule_id"`
    RuleName    string     `json:"rule_name"`
    MatchedText string     `json:"matched_text"`
    Action      string     `json:"action"`
    CreatedAt   time.Time  `json:"created_at"`
}
```

### 3.4 集群资源模块

#### 3.4.1 功能描述

提供集群资源概览，监控节点、CPU、内存和存储使用情况。

#### 3.4.2 功能列表

- **节点概览**：查看 Kubernetes 集群节点状态
- **资源使用统计**：CPU、内存、存储使用统计
- **配额使用分析**：用户配额使用情况

### 3.5 系统设置模块

#### 3.5.1 功能描述

管理系统运行时镜像和系统配置。

#### 3.5.2 功能列表

- **运行时镜像管理**：管理不同类型实例的运行时镜像
- **镜像覆盖**：从系统设置覆盖运行时镜像
- **存储类配置**：配置持久化存储类

### 3.6 WebSocket 服务

#### 3.6.1 功能描述

提供实时桌面访问和连接状态管理。

#### 3.6.2 功能列表

- **桌面访问**：通过 WebSocket 提供实时桌面访问
- **连接统计**：实时查看连接数量
- **连接管理**：管理活动连接

---

## 4. API 接口

### 4.1 认证接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/auth/register | 用户注册 |
| POST | /api/v1/auth/login | 用户登录 |
| POST | /api/v1/auth/refresh | 刷新 Token |
| POST | /api/v1/auth/logout | 登出 |
| GET | /api/v1/auth/me | 获取当前用户信息 |
| POST | /api/v1/auth/change-password | 修改密码 |

### 4.2 用户管理接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/users | 获取用户列表 | 管理员 |
| POST | /api/v1/users | 创建用户 | 管理员 |
| POST | /api/v1/users/import | CSV 批量导入用户 | 管理员 |
| DELETE | /api/v1/users/:id | 删除用户 | 管理员 |
| PUT | /api/v1/users/:id/role | 更新用户角色 | 管理员 |
| PUT | /api/v1/users/:id/quota | 更新用户配额 | 管理员 |
| GET | /api/v1/users/:id | 获取用户详情 | 用户/管理员 |
| PUT | /api/v1/users/:id | 更新用户信息 | 用户/管理员 |
| GET | /api/v1/users/:id/quota | 获取用户配额 | 用户/管理员 |

### 4.3 实例管理接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/instances | 获取实例列表 |
| POST | /api/v1/instances | 创建实例 |
| GET | /api/v1/instances/:id | 获取实例详情 |
| PUT | /api/v1/instances/:id | 更新实例 |
| DELETE | /api/v1/instances/:id | 删除实例 |
| POST | /api/v1/instances/:id/start | 启动实例 |
| POST | /api/v1/instances/:id/stop | 停止实例 |
| POST | /api/v1/instances/:id/restart | 重启实例 |
| GET | /api/v1/instances/:id/status | 获取实例状态 |
| POST | /api/v1/instances/:id/access | 生成访问令牌 |
| GET | /api/v1/instances/:id/access | 访问实例 |
| POST | /api/v1/instances/:id/sync | 强制同步 |
| GET | /api/v1/instances/:id/openclaw/export | 导出 OpenClaw |
| POST | /api/v1/instances/:id/openclaw/import | 导入 OpenClaw |

### 4.4 AI Gateway 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/gateway/llm/models | 获取可用模型列表 |
| POST | /api/v1/gateway/llm/chat/completions | 聊天完成 |

### 4.5 管理接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/admin/models | 获取模型列表 |
| POST | /api/v1/admin/models/discover | 发现模型 |
| PUT | /api/v1/admin/models | 创建/更新模型 |
| DELETE | /api/v1/admin/models/:id | 删除模型 |
| GET | /api/v1/admin/ai-audit | AI 审计日志 |
| GET | /api/v1/admin/ai-audit/:traceId | 追踪详情 |
| GET | /api/v1/admin/costs | 成本概览 |
| GET | /api/v1/admin/risk-rules | 风险规则列表 |
| POST | /api/v1/admin/risk-rules/test | 测试规则 |
| POST | /api/v1/admin/risk-rules/bulk-status | 批量更新状态 |
| PUT | /api/v1/admin/risk-rules | 创建/更新规则 |
| DELETE | /api/v1/admin/risk-rules/:ruleId | 删除规则 |
| GET | /api/v1/system-settings/images | 运行时镜像列表 |
| PUT | /api/v1/system-settings/images | 更新运行时镜像 |
| DELETE | /api/v1/system-settings/images/:instanceType | 删除运行时镜像 |
| GET | /api/v1/system-settings/cluster-resources | 集群资源 |

### 4.6 WebSocket 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/ws | WebSocket 连接 |
| GET | /api/v1/ws/stats | 连接统计 |

---

## 5. 部署架构

### 5.1 Kubernetes 部署

ClawManager 推荐部署在 Kubernetes 集群内部：

```bash
kubectl apply -f deployments/k8s/clawmanager.yaml
kubectl get pods -A
kubectl get svc -A
```

### 5.2 Docker 部署

```bash
docker build -t clawmanager:latest .
docker run -d -p 8080:8080 clawmanager:latest
```

### 5.3 环境变量

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| SERVER_ADDRESS | 服务器地址 | :8080 |
| SERVER_MODE | 服务器模式 | release |
| DB_HOST | 数据库主机 | localhost |
| DB_PORT | 数据库端口 | 3306 |
| DB_USER | 数据库用户 | root |
| DB_PASSWORD | 数据库密码 | - |
| DB_NAME | 数据库名称 | clawmanager |
| JWT_SECRET | JWT 密钥 | - |

---

## 6. 安全特性

### 6.1 认证与授权

- JWT Token 认证
- RBAC 角色权限控制
- Token 过期和刷新机制

### 6.2 网络安全

- 实例服务使用 Kubernetes 内部网络
- 桌面访问通过认证的后端代理
- CORS 中间件保护

### 6.3 数据安全

- 密码加密存储
- 安全模型隔离
- 敏感操作审计

---

## 7. 默认账户

- **默认管理员账户**: admin / admin123
- **导入管理员用户默认密码**: admin123
- **导入普通用户默认密码**: user123

---

## 8. 使用流程

1. 管理员登录系统
2. 创建或导入用户，分配配额
3. 在系统设置中审查或更新运行时镜像
4. 用户登录并创建实例
5. 用户通过 Portal 或 Desktop Access 访问桌面
6. 管理员从仪表盘监控健康状况和容量

---

## 9. CSV 导入模板

```csv
Username,Email,Role,Max Instances,Max CPU Cores,Max Memory (GB),Max Storage (GB),Max GPU Count (optional)
```

**注意**：
- Email 为可选字段
- Max GPU Count 为可选字段
- 其他字段为必填

---

## 10. 版本信息

- **最新版本**: Release (2026-03-20)
- **前端**: React 19
- **后端**: Go 1.21+
- **许可证**: MIT License