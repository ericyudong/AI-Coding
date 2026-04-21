# DeepSeek Q&A System

一个基于 FastAPI + DeepSeek 大模型的智能问答系统，支持多轮对话和对话历史管理。

## 功能特点

- 🤖 集成 DeepSeek 大模型 API
- 💬 支持多轮对话，保持对话历史
- 🌐 现代化 Web 前端界面
- ⚡ 快速异步处理
- 🔐 支持 API 密钥配置
- 📝 对话记录管理

## 快速开始

### 环境需求

- Python 3.8+
- Node.js 14+（可选，如果只用后端）

### 安装步骤

1. **克隆项目**

```bash
cd deepseek-qa-system
```

2. **配置后端环境**

```bash
# 创建虚拟环境
python -m venv venv

# Windows 激活虚拟环境
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

3. **配置 DeepSeek API**

创建 `.env` 文件在项目根目录：

```
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

4. **启动后端服务**

```bash
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

5. **打开前端**

在浏览器中访问：`http://localhost:8080`

## API 端点

### POST /api/chat
发送消息并获取 AI 响应

**请求体：**
```json
{
  "message": "你好，请介绍一下自己",
  "session_id": "optional-session-id"
}
```

**响应：**
```json
{
  "response": "AI的回答内容",
  "session_id": "session-id",
  "message_id": "message-id"
}
```

### GET /api/history/{session_id}
获取对话历史

**响应：**
```json
{
  "messages": [
    {
      "id": "message-id",
      "role": "user",
      "content": "提问内容",
      "timestamp": "2024-01-01T12:00:00Z"
    },
    {
      "id": "message-id",
      "role": "assistant",
      "content": "回答内容",
      "timestamp": "2024-01-01T12:00:01Z"
    }
  ]
}
```

### DELETE /api/session/{session_id}
删除对话会话

## 项目结构

```
deepseek-qa-system/
├── backend/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 主应用
│   ├── config.py              # 配置管理
│   ├── models.py              # 数据模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── deepseek_api.py    # DeepSeek API 调用
│   │   └── session.py         # 会话管理
│   └── routers/
│       ├── __init__.py
│       └── chat.py            # 聊天路由
├── frontend/
│   ├── index.html             # 主页
│   ├── style.css              # 样式
│   └── script.js              # 前端逻辑
├── requirements.txt           # Python 依赖
├── .env.example              # 环境变量示例
└── README.md                 # 项目说明

```

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|------|------|--------|
| DEEPSEEK_API_KEY | DeepSeek API 密钥 | 必填 |
| DEEPSEEK_BASE_URL | API 基础 URL | https://api.deepseek.com |
| DEEPSEEK_MODEL | 使用的模型 | deepseek-chat |
| LOG_LEVEL | 日志级别 | INFO |
| SESSION_EXPIRY | 会话过期时间（秒） | 86400 |

## 开发

### 运行单元测试

```bash
pytest tests/ -v
```

### 代码风格

项目使用 Black 和 isort 进行代码格式化：

```bash
black backend/
isort backend/
```

## 部署

### Docker 部署

```bash
docker build -t deepseek-qa-system .
docker run -p 8000:8000 -e DEEPSEEK_API_KEY=your_key deepseek-qa-system
```

## 常见问题

**Q: 如何获取 DeepSeek API 密钥？**

A: 访问 [DeepSeek 官网](https://www.deepseek.com/) 注册账户并申请 API 密钥。

**Q: 支持哪些模型？**

A: 支持所有 DeepSeek 提供的模型，默认使用 `deepseek-chat`。

**Q: 如何清除对话历史？**

A: 点击前端的"新建会话"按钮，或调用 DELETE API 删除特定会话。

## 许可证

MIT

## 反馈

如有问题或建议，欢迎提交 Issue。

