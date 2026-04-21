# E-Claw: 企业级AI智能体运行平台

## 项目概述

**E-Claw** 是基于OpenClaw架构设计的企业级AI智能体运行平台，采用三层融合架构，支持多租户隔离、断点续跑、RAG检索等核心能力。

## 核心特性

### 1. 多租户隔离
- 租户创建、禁用、删除
- 租户资源配额分配
- 租户数据完全隔离

### 2. 实例管理
- 支持多种实例类型：OpenClaw、Ubuntu、WebTop、Debian、CentOS及自定义镜像
- 基于Kubernetes的编排和扩缩容
- GPU加速实例支持AI工作负载
- 灵活的CPU、内存、磁盘配置
- 持久化存储支持（PVC）

### 3. 任务管理
- 多模态任务提交（文档、图片、音频、视频）
- 任务优先级调度
- 实时任务状态跟踪
- WebSocket实时进度更新

### 4. 知识库（RAG）
- 个人知识库
- 部门共享知识库
- 基于ChromaDB的RAG检索
- 文档导入（PDF、DOCX、图片、Excel）
- 向量相似度搜索

### 5. 用户与权限管理
- RBAC（基于角色的访问控制）模型
- 角色：员工、部门管理员、超级管理员
- 部门级和资源级权限控制
- JWT令牌认证

### 6. 资源配额
- Token使用计量
- 部门配额分配
- 个人配额管理
- 使用统计报表

### 7. 审计日志
- 全链路操作记录
- 多维度查询过滤
- 日志导出功能

## 技术栈

### 后端
- **语言**: Python 3.11+
- **框架**: FastAPI
- **数据库**: PostgreSQL + Redis
- **AI引擎**: LangChain + 本地LLM
- **向量数据库**: ChromaDB
- **通信**: WebSocket + RESTful API
- **Kubernetes**: Python Kubernetes客户端

### 前端
- **框架**: Vue 3 + TypeScript
- **UI库**: Element Plus
- **状态管理**: Pinia
- **路由**: Vue Router 4
- **图表**: ECharts
- **HTTP客户端**: Axios

### 部署
- **容器化**: Docker
- **编排**: Kubernetes
- **进程管理**: Uvicorn

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      客户端层                               │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │ Web UI  │  │ 移动端  │  │ 桌面端  │  │  API    │       │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │
└───────┼────────────┼────────────┼────────────┼─────────────┘
        └────────────┴────────────┴────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  适配层 (E-Claw适配器)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ WebSocket    │  │ 断点续跑     │  │ 本地知识库   │     │
│  │ 网关         │  │ 管理器       │  │ 管理器       │     │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘     │
└─────────┼─────────────────┼────────────────────────────────┘
          │                 │
          ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│                管理层 (E-Claw管理器)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ 多租户       │  │ 资源调度     │  │ 权限控制     │     │
│  │ 管理器       │  │ 引擎         │  │ (RBAC)       │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ 审计日志     │  │ Token计量     │  │ 告警管理     │     │
│  │ 服务         │  │ 服务         │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────┬──────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                执行层 (E-Claw执行引警)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ 任务执行器   │  │ RAG检索      │  │ 工具调用     │     │
│  │              │  │ 引擎         │  │ 管理器       │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## 目录结构

```
e-claw/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── api/               # API路由
│   │   │   ├── v1/
│   │   │   │   ├── auth.py    # 认证接口
│   │   │   │   ├── users.py   # 用户管理
│   │   │   │   ├── tasks.py   # 任务管理
│   │   │   │   ├── knowledge.py # 知识库
│   │   │   │   ├── instances.py # 实例管理
│   │   │   │   ├── gateway.py # AI网关
│   │   │   │   └── admin.py    # 管理员接口
│   │   │   └── websocket.py   # WebSocket接口
│   │   ├── core/              # 核心模块
│   │   │   ├── config.py      # 配置管理
│   │   │   ├── security.py    # 安全与JWT
│   │   │   ├── database.py    # 数据库
│   │   │   └── mcp.py         # MCP协议
│   │   ├── models/            # 数据模型
│   │   ├── services/          # 业务服务
│   │   │   ├── tenant_service.py   # 多租户服务
│   │   │   ├── task_service.py     # 任务服务
│   │   │   ├── knowledge_service.py # 知识库服务
│   │   │   ├── k8s_service.py      # Kubernetes服务
│   │   │   ├── instance_service.py # 实例服务
│   │   │   ├── llm_gateway_service.py # LLM网关
│   │   │   └── audit_service.py    # 审计服务
│   │   └── main.py            # 应用入口
│   ├── requirements.txt
│   └── run.bat
├── frontend/                   # 前端应用
│   ├── src/
│   │   ├── api/              # API调用
│   │   ├── components/       # 公共组件
│   │   ├── views/            # 页面视图
│   │   ├── stores/           # 状态管理（Pinia）
│   │   ├── router/           # 路由配置
│   │   └── utils/            # 工具函数
│   ├── index.html
│   └── package.json
├── test/                       # 测试脚本
└── PROJECT_STRUCTURE.md
```

## 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+
- Kubernetes集群（生产环境）

### 后端设置

1. **进入后端目录**
   ```bash
   cd backend
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # 或
   source venv/bin/activate  # Linux/Mac
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **配置环境**
   创建`.env`文件并配置数据库和Redis：
   ```env
   DATABASE_URL=postgresql+asyncpg://user:password@localhost/eclaw
   REDIS_URL=redis://localhost:6379/0
   SECRET_KEY=your-secret-key
   ```

5. **初始化数据库**
   ```bash
   python backend/setup_db.py
   ```

6. **启动后端服务**
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   或使用提供的批处理文件：
   ```bash
   start_backend.bat
   ```

### 前端设置

1. **进入前端目录**
   ```bash
   cd frontend
   ```

2. **安装依赖**
   ```bash
   npm install
   ```

3. **启动开发服务器**
   ```bash
   npm run dev
   ```

4. **构建生产版本**
   ```bash
   npm run build
   ```

## API文档

### 认证
- `POST /api/login` - 用户登录
- `POST /api/v1/auth/logout` - 用户登出
- `GET /api/v1/auth/me` - 获取当前用户信息

### 实例管理
- `GET /api/direct/instances` - 获取实例列表
- `POST /api/direct/instances` - 创建实例
- `GET /api/image-templates` - 获取可用镜像模板
- `DELETE /api/v1/instances/{id}` - 删除实例

### 任务管理
- `GET /api/direct/tasks` - 获取任务列表
- `POST /api/v1/tasks` - 提交任务
- `GET /api/v1/tasks/{id}` - 获取任务详情
- `DELETE /api/v1/tasks/{id}` - 取消任务

### 知识库
- `GET /api/direct/knowledge` - 获取知识库列表
- `POST /api/v1/knowledge` - 上传文档
- `DELETE /api/v1/knowledge/{id}` - 删除文档
- `GET /api/v1/knowledge/search` - 搜索知识库

### 管理员
- `GET /api/direct/users` - 获取用户列表
- `POST /api/direct/tenants` - 创建租户
- `GET /api/v1/admin/tenants` - 获取租户列表
- `GET /api/v1/admin/audit` - 查询审计日志

### 系统
- `GET /health` - 健康检查
- `GET /api/v1/system/status` - 系统状态
- `GET /api/v1/system/monitor` - 系统监控
- `GET /api/v1/system/logs` - 系统日志

### AI网关
- `POST /api/v1/gateway/query` - LLM查询接口
- `POST /api/v1/gateway/rag` - RAG查询接口

## 实例类型

E-Claw支持以下实例模板：

1. **OpenClaw**: 全功能AI工作空间，包含LLM网关
   - 默认端口: 18789
   - 包含AI任务处理能力

2. **Linux (Ubuntu)**: 通用Linux工作环境
   - 镜像: ubuntu:22.04
   - 默认端口: 22 (SSH)

3. **WebTop**: 基于Web的Linux桌面环境
   - 镜像: lscr.io/linuxserver/webtop:latest
   - 默认端口: 3000
   - 提供图形界面

## 配置说明

### 环境变量

后端关键环境变量：

- `DATABASE_URL`: PostgreSQL连接字符串
- `REDIS_URL`: Redis连接字符串
- `SECRET_KEY`: JWT签名密钥
- `KUBECONFIG`: Kubernetes配置路径（可选）
- `CORS_ORIGINS`: 允许的CORS源

### 系统要求

### 最低配置
- CPU: 4核
- 内存: 16GB
- 存储: 200GB SSD

### 推荐配置
- CPU: 8核
- 内存: 32GB
- 存储: 500GB SSD
- GPU: NVIDIA GPU支持CUDA（AI工作负载）

## 开发指南

### 测试
在`test/`目录中提供了测试脚本：
- `test_login.py` - 测试认证功能
- `test_create_instance.py` - 测试实例创建
- `test_status.py` - 检查系统状态
- `test_k8s_connection.py` - 测试Kubernetes连接

### 代码规范
- 后端：遵循PEP 8规范
- 前端：使用TypeScript严格模式
- 使用有意义的变量和函数名

## 生产部署

### Docker部署

```bash
# 构建后端镜像
docker build -t e-claw-backend:latest -f backend/Dockerfile .

# 构建前端镜像
docker build -t e-claw-frontend:latest -f frontend/Dockerfile .

# 使用docker-compose运行
docker-compose up -d
```

### Kubernetes部署

```bash
# 应用Kubernetes清单
kubectl apply -f k8s/
```

## 故障排查

### 常见问题

1. **数据库连接错误**
   - 检查PostgreSQL是否运行
   - 验证.env文件中的DATABASE_URL配置

2. **实例创建失败**
   - 验证Kubernetes集群连接
   - 检查命名空间是否存在
   - 确保集群资源充足

3. **RAG搜索返回空**
   - 验证ChromaDB可访问性
   - 检查文档是否已索引
   - 查看嵌入模型配置

## 许可证

本项目为专有软件，保留所有权利。

## 技术支持

如有问题、建议或贡献，请联系开发团队。
