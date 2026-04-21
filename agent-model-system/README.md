# 🤖 AI Agent 模型管理系统

一个强大的三Agent协作系统，用于从HuggingFace自动下载Deepseek模型，进行微调并部署到本地。

## 📋 系统概述

本系统由三个专门的Agent组成，各司其职，相互协作：

### 1️⃣ InteractionAgent (交互Agent)
- **功能**: 与用户交互，协调其他两个Agent的工作
- **职责**:
  - 显示欢迎信息和系统说明
  - 询问用户想要下载的模型
  - 询问是否需要微调模型
  - 询问微调参数（学习率、Batch Size等）
  - 询问是否部署微调后的模型
  - 协调DownloadAgent和FinetuneAgent的执行

### 2️⃣ ModelDownloadAgent (下载Agent)
- **功能**: 从HuggingFace自动下载Deepseek最新模型
- **职责**:
  - 支持多个Deepseek模型版本（1b, 7b, 33b, chat, coder）
  - 使用huggingface_hub库进行下载
  - 支持断点续传
  - 自动管理模型本地存储
  - 提供模型列表查询功能

### 3️⃣ ModelFinetuneAgent (微调Agent)
- **功能**: 使用LLamaFactory对下载的模型进行微调
- **职责**:
  - 自动生成样本训练数据
  - 支持使用LLamaFactory进行模型微调
  - 支持使用transformers库进行微调（备选方案）
  - 自动生成部署脚本
  - 支持模型部署到本地FastAPI服务
  - 提供RESTful API接口

## 🚀 快速开始

### 前置要求

- Python 3.9 或更高版本
- CUDA 11.8+ (GPU加速，可选)
- 足够的磁盘空间 (取决于模型大小，通常需要30GB+)

### 安装步骤

1. **克隆或复制项目**
   ```bash
   cd agent-model-system
   ```

2. **创建虚拟环境** (推荐)
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **安装依赖包**
   ```bash
   pip install -r requirements.txt
   ```

4. **配置HuggingFace Token** (可选，但推荐)
   ```bash
   # Windows PowerShell
   $env:HUGGINGFACE_TOKEN = "your_token_here"
   
   # Linux/Mac
   export HUGGINGFACE_TOKEN="your_token_here"
   ```

   或创建 `.env` 文件:
   ```
   HUGGINGFACE_TOKEN=your_token_here
   ```

### 运行系统

**启动完整工作流程**:
```bash
python main.py
```

**查看已下载的模型**:
```bash
python main.py --check-models
```

**列出所有Agent**:
```bash
python main.py --list-agents
```

**显示帮助信息**:
```bash
python main.py --help
```

## 📁 项目结构

```
agent-model-system/
├── main.py                      # 主程序入口
├── config.py                    # 系统配置文件
├── requirements.txt             # Python依赖
├── README.md                    # 本文件
├── QUICKSTART.md                # 快速开始指南
├── agents/                      # Agent模块目录
│   ├── __init__.py
│   ├── base_agent.py            # 基础Agent类
│   ├── interaction_agent.py     # 交互Agent
│   ├── download_agent.py        # 下载Agent
│   └── finetune_agent.py        # 微调Agent
├── models/                      # 保存下载的模型
├── finetuned_models/            # 保存微调后的模型和脚本
│   ├── training_data/           # 训练数据
│   ├── finetune_script.py       # 生成的微调脚本
│   └── deploy_server_*.py       # 生成的部署脚本
└── logs/                        # 系统日志文件
    ├── agent_system.log         # 系统主日志
    ├── interaction_agent.log    # 交互Agent日志
    ├── download_agent.log       # 下载Agent日志
    └── finetune_agent.log       # 微调Agent日志
```

## 🔄 工作流程

### 正常使用流程

```
启动系统
    ↓
InteractionAgent显示欢迎信息
    ↓
询问用户选择模型
    ↓
调用ModelDownloadAgent下载模型
    ↓
询问是否微调
    ├→ 是: 询问微调参数
    │   ↓
    │   调用ModelFinetuneAgent进行微调
    │   ↓
    │   询问是否部署
    │   ├→ 是: 启动FastAPI服务
    │   └→ 否: 结束
    └→ 否: 结束
```

## 🧪 使用示例

### 示例 1: 下载并微调deepseek-7b

```bash
$ python main.py

[系统提示选择模型]
📋 可用的Deepseek模型:
  1. deepseek-1b
  2. deepseek-7b
  3. deepseek-33b
  4. deepseek-chat
  5. deepseek-coder

请选择模型 (1-5): 2

[系统开始下载]
📥 开始下载模型...
[下载进度...]
✅ 模型下载完成

[询问是否微调]
❓ 是否需要微调模型? (y/n): y

[配置微调参数]
⚙️ 配置微调参数:
  学习率 (默认: 1e-4): 5e-5
  Batch Size (默认: 4): 8
  训练轮数 (默认: 3): 5
  部署端口 (默认: 8000): 8000

[开始微调]
🔧 开始微调模型...
⚙️ 开始微调...
[微调进度...]
✅ 模型微调完成

[询问是否部署]
❓ 是否将微调后的模型部署到本地? (y/n): y

[部署完成]
✅ 模型已部署
🌐 模型服务地址: http://localhost:8000
```

## 🤔 常见问题

### Q: 下载模型时超时怎么办？
A: 可以使用代理或设置更长的超时时间。确保网络连接稳定。

### Q: 微调需要多长时间？
A: 取决于模型大小和数据量，通常需要几小时。可以通过调整batch_size和epochs来加速或减速。

### Q: 如何使用GPU加速训练？
A: 确保安装了CUDA并正确配置PyTorch。系统会自动检测可用的CUDA设备。

### Q: 如何调用部署的模型API？
A: 
```python
import requests
import json

url = "http://localhost:8000/generate"
data = {
    "prompt": "你好，请介绍一下你自己",
    "max_length": 512,
    "temperature": 0.7,
    "top_p": 0.9
}

response = requests.post(url, json=data)
result = response.json()
print(result["generated_text"])
```

### Q: 如何停止部署的服务？
A: 在运行部署脚本的终端中按 `Ctrl+C`。

## 📊 API文档

### 健康检查端点

```
GET /health

响应:
{
    "status": "healthy",
    "model": "deepseek"
}
```

### 文本生成端点

```
POST /generate

请求体:
{
    "prompt": "你的提示文本",
    "max_length": 512,
    "temperature": 0.7,
    "top_p": 0.9
}

响应:
{
    "prompt": "你的提示文本",
    "generated_text": "生成的完整文本",
    "model": "deepseek"
}
```

## 🔐 安全建议

1. **HuggingFace Token**: 不要在代码中硬编码token，使用环境变量
2. **API访问**: 在生产环境中添加认证和速率限制
3. **模型存储**: 定期备份重要的微调模型
4. **日志文件**: 定期清理日志文件以节省磁盘空间

## 🐛 故障排除

### 导入错误: No module named 'agents'
**解决方案**: 确保你在项目根目录运行 `python main.py`

### HuggingFace 认证错误
**解决方案**: 
1. 检查HUGGINGFACE_TOKEN是否正确设置
2. 从 https://huggingface.co/settings/tokens 获取新token
3. 重新设置环境变量

### 内存不足错误
**解决方案**:
1. 减小batch_size
2. 使用更小的模型版本 (deepseek-1b 而不是 deepseek-33b)
3. 增加虚拟内存

### 模型加载失败
**解决方案**:
1. 检查模型路径是否正确
2. 确保磁盘空间足够
3. 清除缓存: `rm -rf ~/.cache/huggingface/`

## 📝 配置文件说明

### config.py

主要配置包括：

- `MODELS_DIR`: 下载模型的存储目录
- `FINETUNED_MODELS_DIR`: 微调模型的输出目录
- `LOGS_DIR`: 日志文件目录
- `DEFAULT_FINETUNE_PARAMS`: 默认微调参数
- `AGENTS_CONFIG`: 各Agent的配置

## 🔗 相关资源

- [Deepseek Model Cards](https://huggingface.co/deepseek-ai)
- [LLamaFactory Documentation](https://github.com/hiyouga/LLaMA-Factory)
- [Transformers Library](https://huggingface.co/docs/transformers)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## 📄 许可证

MIT License

## 👥 贡献

欢迎提交问题和拉取请求！

## 📞 支持

如有问题，请在项目中提交Issue或联系开发者。

---

**版本**: 1.0.0  
**最后更新**: 2024年  
**作者**: AI Agent Development Team
