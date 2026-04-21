# DeepSeek Q&A System - Project File Structure

## 项目文件说明

### 后端 (backend/)
- `main.py`: FastAPI 主应用程序，处理路由和中间件配置
- `config.py`: 配置管理，加载环境变量
- `models.py`: Pydantic 数据模型定义
- `services/deepseek_api.py`: DeepSeek API 接口服务
- `services/session.py`: 会话和消息历史管理服务
- `routers/chat.py`: 聊天相关的 API 端点

### 前端 (frontend/)
- `index.html`: HTML 主界面
- `style.css`: 样式表
- `script.js`: 前端交互脚本

### 根目录配置文件
- `requirements.txt`: Python 依赖包列表
- `.env.example`: 环境变量示例
- `.gitignore`: Git 忽略文件配置
- `Dockerfile`: Docker 容器构建文件
- `docker-compose.yml`: Docker Compose 编排文件
- `conftest.py`: pytest 测试配置
- `tests_api.py`: API 测试用例

## 关键特性

### 后端特性
1. **异步处理**: 使用 FastAPI 的异步特性提高性能
2. **模块化设计**: 清晰的包结构便于维护和扩展
3. **会话管理**: 完整的对话会话管理系统
4. **错误处理**: 全面的异常捕获和日志记录

### 前端特性
1. **现代化 UI**: 响应式设计，支持多种屏幕尺寸
2. **实时交互**: 异步消息发送和接收
3. **会话管理**: 侧边栏显示和管理多个对话
4. **用户友好**: 支持快捷键、示例问题等

## 快速开始步骤

### 1. 环境设置
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### 2. 配置 API 密钥
创建 `.env` 文件：
```
DEEPSEEK_API_KEY=your_actual_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

### 3. 运行应用
```bash
python -m uvicorn backend.main:app --reload
```

### 4. 访问应用
打开浏览器访问 `http://localhost:8000`

## API 端点

### POST /api/chat
- 请求: `{"message": "问题", "session_id": "可选"}`
- 响应: `{"response": "回答", "session_id": "...", "message_id": "..."}`

### GET /api/history/{session_id}
- 获取指定会话的所有消息

### POST /api/session/new
- 创建新的对话会话

### GET /api/sessions
- 获取所有活跃会话列表

### DELETE /api/session/{session_id}
- 删除指定会话

## 开发建议

1. **修改模型提示**: 在 `backend/routers/chat.py` 中修改 `system_prompt`
2. **添加新功能**: 在 `backend/services/` 中添加新服务类
3. **自定义样式**: 编辑 `frontend/style.css`
4. **测试代码**: 运行 `pytest tests_api.py`

## 故障排除

- **API 错误**: 检查 `.env` 文件中的 API 密钥是否正确
- **连接错误**: 确保后端服务正在运行
- **CORS 错误**: 检查 `backend/main.py` 中的 CORS 配置
- **导入错误**: 确保所有依赖已正确安装
