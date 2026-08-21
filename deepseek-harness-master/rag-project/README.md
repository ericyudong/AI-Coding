# RAG Web App — 文档知识库问答系统

基于 RAG（Retrieval-Augmented Generation）的中文文档问答应用，支持文档上传、自动分块嵌入、向量检索和 LLM 生成回答。

## 架构

```
┌─────────────┐     HTTP      ┌──────────────┐     ChromaDB     ┌────────────┐
│  Streamlit   │ ◄──────────► │   FastAPI     │ ◄──────────────► │  Vector DB │
│  (Frontend)  │              │   (Backend)   │                  │ (ChromaDB) │
└─────────────┘               └──────┬───────┘                  └────────────┘
                                     │
                              ┌──────▼───────┐
                              │  LLM API     │
                              │ (DeepSeek /  │
                              │  OpenAI)     │
                              └──────────────┘
```

- **前端**: Streamlit — 文档上传 + 对话式问答界面
- **后端**: FastAPI — RESTful API（上传/查询/文档管理）
- **向量数据库**: ChromaDB (本地持久化)
- **嵌入模型**: sentence-transformers/all-MiniLM-L6-v2 (本地运行)
- **LLM**: OpenAI-compatible API (默认 DeepSeek)

## 快速开始

### 1. 安装依赖

```bash
cd rag-project
pip install -e .
```

### 2. 配置 LLM API Key

```bash
export OPENAI_API_KEY="your-deepseek-api-key"
# 可选：自定义 API 地址
export OPENAI_BASE_URL="https://api.deepseek.com/v1"
```

### 3. 启动服务

```bash
chmod +x run.sh
./run.sh
```

或分别启动：

```bash
# 后端
uvicorn app.server:app --host 127.0.0.1 --port 8000 --reload

# 前端（另一个终端）
streamlit run frontend/app.py --server.port 8501
```

### 4. 访问

- **Web 界面**: http://127.0.0.1:8501
- **API 文档**: http://127.0.0.1:8000/docs

## 支持的文件格式

| 格式 | 扩展名 |
|------|--------|
| 纯文本 | `.txt` |
| Markdown | `.md` |
| PDF | `.pdf` |
| Word | `.docx` |

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload` | 上传并入库文档 |
| POST | `/api/query` | 提问（返回回答+引用来源） |
| GET | `/api/documents` | 列出已入库文档 |
| DELETE | `/api/documents/{filename}` | 删除指定文档 |
| GET | `/api/health` | 健康检查 |

## 项目结构

```
rag-project/
├── app/
│   ├── config.py        # 配置参数
│   ├── ingest.py        # 文档解析与分块
│   ├── vectorstore.py   # ChromaDB 向量存储
│   ├── llm.py           # LLM 调用封装
│   └── server.py        # FastAPI 服务端
├── frontend/
│   └── app.py           # Streamlit Web 前端
├── data/
│   ├── uploads/         # 上传文件存储
│   └── chroma_db/       # 向量数据库持久化
├── pyproject.toml       # 依赖声明
├── run.sh               # 一键启动脚本
└── README.md
```

## 自定义配置

编辑 `app/config.py` 调整：

- `CHUNK_SIZE` / `CHUNK_OVERLAP`: 文本分块大小和重叠
- `EMBEDDING_MODEL`: 更换嵌入模型
- `LLM_MODEL`: 更换 LLM 模型
- `TOP_K`: 检索返回的文档块数量
