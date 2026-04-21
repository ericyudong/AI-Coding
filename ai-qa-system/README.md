# AI Q&A System 🤖

一个基于大语言模型的智能问答系统，支持多种 LLM 提供商、RAG（检索增强生成）和多轮对话。

## 功能特点

- **多 LLM 支持**: 支持 OpenAI、Anthropic (Claude)、Google Gemini 等主流 LLM 提供商
- **RAG 知识库**: 支持上传文档构建知识库，实现基于私有数据的智能问答
- **多轮对话**: 支持会话历史管理，保持上下文连续性
- **现代化 Web UI**: 简洁美观的聊天界面
- **RESTful API**: 完整的 API 接口，支持二次开发

## 快速开始

### 环境要求

- Python 3.8+
- API 密钥（根据使用的 LLM 提供商）

### 安装步骤

1. **克隆项目并进入目录**

```bash
cd ai-qa-system
```

2. **创建虚拟环境**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

3. **安装依赖**

```bash
pip install -r requirements.txt
```

4. **配置环境变量**

```bash
# 复制示例配置
copy .env.example .env
```

编辑 `.env` 文件，配置你的 API 密钥：

```env
# 选择 LLM 提供商: openai, anthropic, google
LLM_PROVIDER=openai

# OpenAI 配置
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4

# 或者使用 Anthropic
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=your_anthropic_api_key_here

# 或者使用 Google Gemini
# LLM_PROVIDER=google
# GOOGLE_API_KEY=your_google_api_key_here

# RAG 配置
RAG_ENABLED=true
```

5. **启动服务**

```bash
# 方式1: 直接运行
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 方式2: 使用 Python
python -m backend.main
```

6. **访问系统**

打开浏览器访问: http://localhost:8000

## API 文档

### 聊天接口

#### 发送消息

```bash
POST /api/chat
```

请求体:
```json
{
  "message": "你好，请介绍一下自己",
  "session_id": "optional-session-id",
  "use_rag": false,
  "temperature": 0.7,
  "max_tokens": 2000
}
```

响应:
```json
{
  "response": "AI的回答内容",
  "session_id": "session-id",
  "message_id": "message-id",
  "sources": [],
  "metadata": {
    "use_rag": false,
    "provider": "openai"
  }
}
```

#### 获取历史记录

```bash
GET /api/history/{session_id}
```

#### 列出所有会话

```bash
GET /api/conversations
```

#### 删除会话

```bash
DELETE /api/session/{session_id}
```

### 文档管理接口

#### 上传文档

```bash
POST /api/documents/upload
```

支持 PDF 和文本文件上传。

#### 添加文本

```bash
POST /api/documents/text
```

请求体:
```json
{
  "content": "这是要添加的文档内容...",
  "source": "manual"
}
```

#### 搜索文档

```bash
GET /api/documents/search?query=搜索内容&top_k=5
```

### 健康检查

```bash
GET /health
```

## 项目结构

```
ai-qa-system/
├── backend/
│   ├── __init__.py
│   ├── config.py          # 配置管理
│   ├── models.py          # 数据模型
│   ├── main.py            # FastAPI 主应用
│   ├── services/
│   │   ├── llm_service.py     # LLM 服务
│   │   ├── session_service.py # 会话管理
│   │   └── rag_service.py     # RAG 服务
│   └── routers/
│       ├── chat.py        # 聊天路由
│       └── documents.py   # 文档路由
├── requirements.txt       # Python 依赖
├── .env.example          # 环境变量示例
└── README.md             # 项目文档
```

## RAG 使用指南

1. **启用 RAG**: 在 `.env` 中设置 `RAG_ENABLED=true`

2. **上传文档**:
   - 使用 Web 界面上传
   - 或使用 API: `POST /api/documents/upload`

3. **使用知识库问答**:
   - 在 Web 界面勾选 "Use Knowledge Base (RAG)"
   - 或设置请求参数 `"use_rag": true`

## 配置说明

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| LLM_PROVIDER | LLM 提供商 | openai |
| OPENAI_API_KEY | OpenAI API 密钥 | - |
| OPENAI_MODEL | OpenAI 模型 | gpt-4 |
| ANTHROPIC_API_KEY | Anthropic API 密钥 | - |
| GOOGLE_API_KEY | Google API 密钥 | - |
| RAG_ENABLED | 启用 RAG | true |
| RAG_TOP_K | 检索文档数 | 5 |
| PORT | 服务端口 | 8000 |

## 常见问题

**Q: 如何获取 API 密钥？**

A: 
- OpenAI: https://platform.openai.com/api-keys
- Anthropic: https://console.anthropic.com/
- Google: https://aistudio.google.com/app/apikey

**Q: RAG 支持哪些文件格式？**

A: 目前支持 PDF 和纯文本文件。

**Q: 如何查看对话历史？**

A: 刷新页面后，使用相同的 session_id 可以继续对话。session_id 会在首次对话后返回。

## 许可证

MIT License