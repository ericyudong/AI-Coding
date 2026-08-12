# 益慧科技法务 Agent 系统

基于 `pics/` 目录 UI 设计稿实现的智能法务 Agent 平台，包含首页门户、法律检索、合同审核/起草、劳动法问答等模块。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + Pinia |
| 后端 | Python FastAPI + SQLAlchemy + SQLite |
| AI | OpenAI 兼容 API（可选，未配置时使用演示模式） |

## 功能模块

- **首页**：法规搜索、快捷入口、四大 AI 模块卡片、资讯速递
- **AI 检索**：综合分析 / 法规查询 / 类案检索 / 行政处罚 / 专业解读
- **合同审核**：文件上传（doc/docx/pdf）、清单审核 / 参照审核
- **合同起草**：生成合同 / 生成条款，支持多种起草风格
- **问答 AI**：劳动法、金融合规、企业出海

## 快速启动

### 1. 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # 可选：配置 OPENAI_API_KEY
python run.py
```

后端默认运行在 http://127.0.0.1:8010

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 http://localhost:5173

### 3. 登录

- 用户名：`admin`
- 密码：`admin123`

## AI 配置

在 `backend/.env` 中配置：

```env
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

未配置 API Key 时，系统自动使用演示模式返回示例回答，便于 UI 联调。

## 生产部署

```bash
cd frontend && npm run build
xcopy /E /I dist ..\backend\static
cd ..\backend && python run.py
```

构建后的前端可由 FastAPI 静态托管，访问同一端口即可。

## 目录结构

```
legal-agent/
├── pics/              # UI 设计参考图
├── backend/           # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/    # REST API
│   │   ├── services/  # 业务逻辑
│   │   └── models/    # 数据模型
│   └── run.py
└── frontend/          # Vue 3 前端
    └── src/
        ├── views/     # 页面组件
        ├── layouts/   # 布局
        └── api/       # API 客户端
```

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/login` | 登录 |
| GET | `/api/v1/content/*` | 首页内容数据 |
| POST | `/api/v1/search` | 法律检索 |
| POST | `/api/v1/chat` | 智能问答 |
| POST | `/api/v1/contract/upload` | 上传合同 |
| POST | `/api/v1/contract/review/{id}` | 执行审核 |
| POST | `/api/v1/contract/draft` | 合同起草 |
