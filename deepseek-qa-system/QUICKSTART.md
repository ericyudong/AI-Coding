# 🚀 DeepSeek Q&A 系统 - 快速开始检查清单

## ✅ 项目已创建完成！

你的 DeepSeek Q&A 系统已完全搭建。项目位置：
```
c:\eswin\emaas\deepseek-qa-system\
```

---

## 🎯 立即开始（5分钟）

### 第一步：获取 API 密钥 (1分钟)
1. 访问 https://www.deepseek.com/
2. 注册/登录账户
3. 获取 API 密钥

### 第二步：配置应用 (2分钟)
**Windows:**
```bash
cd c:\eswin\emaas\deepseek-qa-system
copy .env.example .env  
REM 用文本编辑器打开 .env，将 API 密钥粘贴到这一行：
REM DEEPSEEK_API_KEY=your_api_key_here
```

**macOS/Linux:**
```bash
cd deepseek-qa-system
cp .env.example .env
nano .env  # 编辑并保存
```

### 第三步：启动应用 (2分钟)

**方法 A：使用启动脚本（推荐）**

Windows:
```bash
run.bat 双击或在终端运行此文件
```

macOS/Linux:
```bash
chmod +x run.sh
./run.sh
```

**方法 B：手动启动**

```bash
# 1. 创建/激活虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows 或 source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务器
python -m uvicorn backend.main:app --reload
```

### 第四步：使用应用 (立即)
打开浏览器访问：http://localhost:8000

---

## 📁 项目结构

```
deepseek-qa-system/
├── 📄 README.md                 # 项目说明
├── 📄 GUIDE.md                  # 完整使用指南 ⭐ 必读
├── 📄 PROJECT_STRUCTURE.md      # 项目文件详解
│
├── 🐍 后端 (Python/FastAPI)
│   └── backend/
│       ├── main.py              # FastAPI 主程序
│       ├── config.py            # 配置管理
│       ├── models.py            # 数据模型
│       ├── services/            # 服务层
│       │   ├── deepseek_api.py  # API 调用
│       │   └── session.py       # 会话管理
│       └── routers/             # API 路由
│           └── chat.py          # 聊天接口
│
├── 🌐 前端 (Web)
│   └── frontend/
│       ├── index.html           # 页面
│       ├── style.css            # 样式
│       └── script.js            # 交互逻辑
│
├── 🐳 Docker & 部署
│   ├── Dockerfile               # Docker 镜像配置
│   ├── docker-compose.yml       # Docker Compose
│   ├── run.bat                  # Windows 启动脚本
│   ├── run.sh                   # Linux/Mac 启动脚本
│   └── run-docker.sh            # Docker 启动脚本
│
├── 📦 配置文件
│   ├── requirements.txt         # Python 依赖
│   ├── .env.example             # 环境变量示例 ⭐ 需复制
│   └── .gitignore               # Git 忽略规则
│
└── ✅ 测试
    ├── conftest.py              # 测试配置
    └── tests_api.py             # 测试用例
```

---

## 🔑 关键文件说明

| 文件 | 说明 | 需要修改 |
|-----|------|--------|
| `.env` | 配置文件（API密钥等） | ✅ 必需 |
| `README.md` | 项目概览 | ❌ |
| `GUIDE.md` | 完整指南 | ❌ |
| `backend/main.py` | 后端主程序 | ⚠️ 可选 |
| `frontend/index.html` | Web界面 | ⚠️ 可选 |

---

## 🌟 核心功能

| 功能 | 状态 | 说明 |
|-----|------|------|
| 🤖 AI 问答 | ✅ | 调用 DeepSeek 大模型 |
| 💬 多轮对话 | ✅ | 保持上下文和对话历史 |
| 📝 会话管理 | ✅ | 创建、切换、删除对话 |
| 🌐 Web 界面 | ✅ | 美观的用户界面 |
| ⚡ REST API | ✅ | 完整的后端 API |
| 🔄 异步处理 | ✅ | 高性能异步服务器 |
| 📖 API 文档 | ✅ | 自动生成（/docs） |

---

## 📋 首次运行检查清单

在启动应用前，请确认：

- [ ] 已获取 DeepSeek API 密钥
- [ ] 已配置 `.env` 文件
- [ ] Python 版本 ≥ 3.8（运行 `python --version` 检查）
- [ ] 网络连接正常
- [ ] 防火墙允许 8000 端口

---

## 💻 常用命令

### 启动应用
```bash
# 自动启动（推荐）
run.bat  # Windows
./run.sh  # macOS/Linux

# 手动启动
python -m uvicorn backend.main:app --reload
```

### 停止应用
```bash
按 Ctrl+C 停止服务器
```

### 查看 API 文档
```
访问 http://localhost:8000/docs
```

### 测试 API
```bash
# 测试健康检查
curl http://localhost:8000/health

# 创建新会话
curl -X POST http://localhost:8000/api/session/new

# 发送消息
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"你好\"}"
```

### 运行测试
```bash
pytest tests_api.py -v
```

---

## 🔒 安全建议

1. **API 密钥管理**
   - ❌ 不要在代码中硬编码 API 密钥
   - ✅ 使用 `.env` 文件（已配置，不要上传到 Git）
   - ✅ 定期轮换 API 密钥

2. **生产环境**
   - 使用 HTTPS 而非 HTTP
   - 配置反向代理（如 Nginx）
   - 限制 API 速率
   - 定期更新依赖包

3. **数据隐私**
   - 对话记录仅存储在内存中
   - 重启后自动清空
   - 支持手动删除会话

---

## 🐛 快速排查

### 问题：应用无法启动
**检查：**
1. Python 是否已安装 ✓
2. API 密钥是否配置 ✓
3. 依赖包是否安装完整 ✓
4. 8000 端口是否占用 ✓

### 问题：API 请求失败
**检查：**
1. DeepSeek API 密钥是否正确
2. 网络连接是否正常
3. API 额度是否用尽

### 问题：前端无法加载
**检查：**
1. 浏览器缓存是否已清空
2. 后端服务是否正在运行
3. 浏览器控制台是否有错误信息

详细故障排除，见 [GUIDE.md](GUIDE.md#-故障排除)

---

## 📚 学习资源

### 官方文档
- [DeepSeek API 文档](https://www.deepseek.com/api-docs)
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Python 官方文档](https://docs.python.org/3/)

### 项目文档（本项目）
- 📄 [README.md](README.md) - 项目概览
- 📄 [GUIDE.md](GUIDE.md) - 详细使用指南 ⭐
- 📄 [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - 代码结构说明

---

## 🎓 下一步建议

### 初级
- [ ] 按照指南成功运行应用
- [ ] 测试基本的 Q&A 功能
- [ ] 尝试多轮对话

### 中级
- [ ] 修改系统提示词
- [ ] 调整 API 参数
- [ ] 自定义 Web 界面样式

### 高级
- [ ] 部署到云服务器
- [ ] 添加数据库支持
- [ ] 实现用户认证系统
- [ ] 集成更多功能

---

## 📞 获取帮助

1. **查看完整指南**: [GUIDE.md](GUIDE.md)
2. **检查 API 文档**: http://localhost:8000/docs
3. **阅读源代码注释**: 代码中有详细的中文注释
4. **官方支持**: 访问 DeepSeek 官网

---

## 🎉 现在就开始吧！

```bash
# Windows
run.bat

# macOS/Linux
./run.sh
```

访问 http://localhost:8000 开始使用！

---

**祝你使用愉快！** 🚀

*有任何问题或建议，欢迎反馈！*
