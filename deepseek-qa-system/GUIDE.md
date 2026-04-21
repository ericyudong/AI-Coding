# DeepSeek Q&A 系统 - 完整使用指南

## 📋 目录
1. [系统要求](#系统要求)
2. [安装步骤](#安装步骤)
3. [快速开始](#快速开始)
4. [配置说明](#配置说明)
5. [使用教程](#使用教程)
6. [API 文档](#api-文档)
7. [故障排除](#故障排除)
8. [部署指南](#部署指南)

---

## 🖥️ 系统要求

### 最低要求
- **操作系统**: Windows 10+, macOS 10.13+, Linux (Ubuntu 18.04+)
- **Python**: 3.8 或更高版本
- **内存**: 至少 2GB RAM
- **网络**: 良好的网络连接（调用 DeepSeek API）

### 可选
- **Docker**: 用于容器化部署
- **Git**: 用于版本控制

---

## 📦 安装步骤

### 方法 1: 本地 Python 环境（推荐初学者）

#### 步骤 1: 获取 DeepSeek API 密钥

1. 访问 [DeepSeek 官方网站](https://www.deepseek.com/)
2. 注册账户或登录
3. 进入 API 密钥管理页面
4. 创建新的 API 密钥并复制保存

#### 步骤 2: 配置环境

**Windows 用户:**
```bash
# 1. 进入项目目录
cd c:\eswin\emaas\deepseek-qa-system

# 2. 创建 .env 文件
copy .env.example .env

# 3. 用文本编辑器打开 .env，替换为你的 API 密钥
# 在 DEEPSEEK_API_KEY=your_api_key_here 后添加实际的密钥
```

**macOS/Linux 用户:**
```bash
# 1. 进入项目目录
cd deepseek-qa-system

# 2. 创建 .env 文件
cp .env.example .env

# 3. 用文本编辑器打开 .env，替换为你的 API 密钥
nano .env
```

#### 步骤 3: 运行应用

**Windows 用户 (双击运行):**
```bash
double-click run.bat
```

或在命令行运行：
```bash
run.bat
```

**macOS/Linux 用户:**
```bash
chmod +x run.sh
./run.sh
```

### 方法 2: Docker（推荐生产环境）

```bash
# 1. 确保安装了 Docker 和 Docker Compose
docker --version
docker-compose --version

# 2. 配置 .env 文件
cp .env.example .env
# 编辑 .env，添加 API 密钥

# 3. 启动应用
docker-compose up --build

# 4. 后台运行 (可选)
docker-compose up -d
```

---

## 🚀 快速开始

### 启动应用后

1. **打开浏览器**
   - 访问: http://localhost:8000

2. **查看 API 文档（可选）**
   - 访问: http://localhost:8000/docs

3. **开始提问**
   - 在输入框输入问题
   - 按 `Shift+Enter` 或点击发送按钮

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Shift+Enter` | 发送消息 |
| `Enter` | 新建一行 |

---

## ⚙️ 配置说明

### .env 文件配置

```env
# 必填：DeepSeek API 密钥
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 可选：API 服务地址（默认为官方 API）
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 可选：使用的模型名称
DEEPSEEK_MODEL=deepseek-chat

# 可选：日志级别 (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# 可选：会话过期时间（秒），默认 24 小时
SESSION_EXPIRY=86400

# 可选：开启调试模式
DEBUG=False
```

### 环境变量详解

**DEEPSEEK_API_KEY**
- 是否必需: ✅ 是
- 说明: 用于认证 DeepSeek API 请求
- 获取方式: DeepSeek 官网 → API 管理 → 创建密钥

**DEEPSEEK_BASE_URL**
- 是否必需: ❌ 否
- 默认值: `https://api.deepseek.com`
- 说明: DeepSeek API 服务地址

**DEEPSEEK_MODEL**
- 是否必需: ❌ 否
- 默认值: `deepseek-chat`
- 可用值: `deepseek-chat`, `deepseek-coder` 等
- 说明: 选择使用的 AI 模型

**LOG_LEVEL**
- 是否必需: ❌ 否
- 默认值: `INFO`
- 可用值: `DEBUG`, `INFO`, `WARNING`, `ERROR`

**SESSION_EXPIRY**
- 是否必需: ❌ 否
- 默认值: `86400` (24 小时)
- 说明: 对话会话保存时间

---

## 📚 使用教程

### 基本使用

#### 1. 新建对话
- 点击头部的 "➕ 新建会话" 按钮
- 进入全新的对话环境

#### 2. 提问
- 在底部输入框输入你的问题
- 按 `Shift+Enter` 或点击 "➤ 发送" 按钮

#### 3. 查看历史
- 左侧边栏显示所有对话记录
- 点击任何会话可切换查看

#### 4. 删除对话
- 在侧边栏会话项上悬停
- 点击 "删除" 按钮

### 高级用法

#### 修改系统提示
编辑 `backend/routers/chat.py`，找到这一行：
```python
system_prompt = "你是一个有帮助的AI助手。请用中文回答问题。"
```

修改为你想要的系统提示，例如：
```python
system_prompt = "你是一个专业的编程助手。请用中文回答关于Python的问题。"
```

#### 调整 API 参数
在 `backend/services/deepseek_api.py` 中修改 payload：
```python
payload = {
    "model": self.settings.deepseek_model,
    "messages": message_list,
    "temperature": 0.7,  # 0-1: 低值更确定，高值更创意
    "top_p": 0.95,       # 核采样参数
    "max_tokens": 2048   # 最大输出 token 数
}
```

---

## 🔌 API 文档

### 认证
大多数 API 已通过浏览器设置了 CORS，无需特殊认证。

### 端点列表

#### 1. 发送消息
```
POST /api/chat
```

**请求示例:**
```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d {
    "message": "你好",
    "session_id": "optional-session-id"
  }
```

**响应示例:**
```json
{
  "response": "你好！有什么我可以帮助你的吗？",
  "session_id": "abc123def456",
  "message_id": "msg-001",
  "timestamp": "2024-01-01T12:00:00"
}
```

#### 2. 获取对话历史
```
GET /api/history/{session_id}
```

**请求示例:**
```bash
curl "http://localhost:8000/api/history/abc123def456"
```

**响应示例:**
```json
{
  "messages": [
    {
      "id": "msg-001",
      "role": "user",
      "content": "你好",
      "timestamp": "2024-01-01T12:00:00"
    },
    {
      "id": "msg-002",
      "role": "assistant",
      "content": "你好！有什么我可以帮助你的吗？",
      "timestamp": "2024-01-01T12:00:01"
    }
  ],
  "session_id": "abc123def456",
  "total_messages": 2
}
```

#### 3. 创建新会话
```
POST /api/session/new
```

**响应示例:**
```json
{
  "session_id": "new-session-id"
}
```

#### 4. 删除会话
```
DELETE /api/session/{session_id}
```

**响应示例:**
```json
{
  "message": "Session abc123def456 deleted successfully"
}
```

#### 5. 获取所有会话
```
GET /api/sessions
```

**响应示例:**
```json
{
  "sessions": [
    {
      "session_id": "abc123def456",
      "message_count": 5,
      "created_at": "2024-01-01T10:00:00",
      "updated_at": "2024-01-01T12:00:00"
    }
  ],
  "total": 1
}
```

#### 6. 健康检查
```
GET /health
```

**响应示例:**
```json
{
  "status": "healthy",
  "model": "deepseek-chat",
  "api_url": "https://api.deepseek.com"
}
```

---

## 🔧 故障排除

### 常见问题

#### ❌ API 密钥无效
```
错误: API returned status 401
```
**解决方案:**
1. 确保 `.env` 文件存在且包含正确的 API 密钥
2. 重启应用
3. 检查 API 密钥是否过期（前往 DeepSeek 官网检查）

#### ❌ 无法连接到后端
```
错误: Failed to communicate with DeepSeek API
```
**解决方案:**
1. 确保后端服务正在运行
2. 检查网络连接
3. 验证 `DEEPSEEK_BASE_URL` 是否正确

#### ❌ CORS 错误（跨域请求错误）
```
错误: Access to XMLHttpRequest has been blocked by CORS policy
```
**解决方案:**
- CORS 已在后端配置，通常不会出现此问题
- 如出现，检查 `backend/main.py` 中的 CORS 中间件配置

#### ❌ 模块导入错误
```
错误: ModuleNotFoundError: No module named 'fastapi'
```
**解决方案:**
1. 确保虚拟环境已激活
2. 运行 `pip install -r requirements.txt`
3. 重启终端

#### ❌ Python 版本太低
```
错误: This Python version is not supported
```
**解决方案:**
- 更新 Python 到 3.8 或更高版本
- 官网下载: https://www.python.org/

### 诊断工具

检查系统状态：
```bash
# 检查 Python 版本
python --version

# 检查已安装的包
pip list

# 测试 API 连接
curl http://localhost:8000/health
```

---

## 🚢 部署指南

### Windows 服务器部署

#### 步骤 1: 使用 NSSM（Non-Sucking Service Manager）

```bash
# 下载 NSSM
# 从 https://nssm.cc/download 下载并解压

# 安装服务
nssm install DeepSeekQA "C:\path\to\python\python.exe" "-m uvicorn backend.main:app --host 0.0.0.0 --port 8000"

# 启动服务
nssm start DeepSeekQA

# 查看状态
nssm status DeepSeekQA

# 停止服务
nssm stop DeepSeekQA
```

### Linux 服务器部署

#### 步骤 1: 创建 Systemd 服务

```bash
# 创建服务文件
sudo nano /etc/systemd/system/deepseek-qa.service
```

**文件内容:**
```ini
[Unit]
Description=DeepSeek Q&A System
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/home/user/deepseek-qa-system
Environment="PATH=/home/user/deepseek-qa-system/venv/bin"
EnvironmentFile=/home/user/deepseek-qa-system/.env
ExecStart=/home/user/deepseek-qa-system/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 启用和启动服务
sudo systemctl enable deepseek-qa
sudo systemctl start deepseek-qa

# 检查服务状态
sudo systemctl status deepseek-qa

# 查看日志
sudo journalctl -u deepseek-qa -f
```

### Docker 部署

#### 构建和运行

```bash
# 构建镜像
docker build -t deepseek-qa:latest .

# 运行容器
docker run -d \
  -p 8000:8000 \
  -e DEEPSEEK_API_KEY=your_key \
  -e LOG_LEVEL=INFO \
  --name deepseek-qa \
  deepseek-qa:latest

# 查看日志
docker logs -f deepseek-qa

# 停止容器
docker stop deepseek-qa
```

#### 使用 Docker Compose

```bash
# 启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

### Nginx 反向代理（可选）

```nginx
upstream deepseek_qa {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name qa.example.com;

    location / {
        proxy_pass http://deepseek_qa;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_request_buffering off;
    }
}
```

---

## 📞 支持与反馈

- **问题报告**: 在项目中创建 Issue
- **功能建议**: 欢迎提交 Pull Request
- **文档改进**: 帮助完善使用指南

---

## 📄 许可证

MIT License - 详见 LICENSE 文件

---

## 🎉 祝你使用愉快！

如有任何问题，请参考故障排除部分或联系支持。
