# 🚀 快速开始指南

让我们快速开始使用AI Agent模型管理系统！

## ⏱️ 5分钟快速入门

### 步骤1: 安装依赖

```bash
# 进入项目目录
cd agent-model-system

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 步骤2: 运行系统

```bash
python main.py
```

### 步骤3: 按照提示操作

系统会提示你：
1. 选择要下载的Deepseek模型
2. 选择是否微调模型
3. 配置微调参数（如需要）
4. 选择是否部署模型

## 📦 支持的模型

系统支持以下Deepseek模型：

| 模型名称 | 参数量 | 推荐GPU | 用途 |
|---------|--------|--------|------|
| deepseek-1b | 10亿 | 4GB+ | 轻量级应用 |
| deepseek-7b | 70亿 | 16GB+ | 通用应用 |
| deepseek-33b | 330亿 | 24GB+ | 高性能应用 |
| deepseek-chat | 7B/33B | 取决于版本 | 对话型模型 |
| deepseek-coder | 1B/6B/33B | 取决于版本 | 代码生成 |

## 🔧 基本操作

### 查看已下载的模型

```bash
python main.py --check-models
```

输出示例：
```
======================================================================
📦 已下载的模型列表
======================================================================

1. deepseek-7b
   路径: ./models/deepseek-7b
   大小: 14.23GB
```

### 列出所有Agent

```bash
python main.py --list-agents
```

### 显示帮助信息

```bash
python main.py --help
```

## 💡 使用场景示例

### 场景1: 仅下载模型（不微调）

```
$ python main.py

[选择模型] → 选择 deepseek-7b
[下载完成]
[询问微调] → 输入 n

✨ 完成！模型已保存到 ./models/deepseek-7b
```

### 场景2: 下载并微调模型

```
$ python main.py

[选择模型] → 选择 deepseek-7b
[下载完成]
[询问微调] → 输入 y
[配置参数] → 使用默认值或自定义
[微调开始] → 等待训练完成
[询问部署] → 输入 n

✨ 完成！微调模型已保存到 ./finetuned_models
```

### 场景3: 下载、微调并部署模型

```
$ python main.py

[选择模型] → 选择 deepseek-chat
[下载完成]
[询问微调] → 输入 y
[配置参数] → 学习率: 1e-4, Batch: 4, Epochs: 3
[微调开始] → 等待训练完成 (~2-4小时)
[询问部署] → 输入 y

✨ 完成！模型已部署到 http://localhost:8000

# 在另一个终端中测试API
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "你好"}'
```

## 🧪 测试API

部署完成后，你可以测试API：

### 使用curl测试

```bash
# 健康检查
curl http://localhost:8000/health

# 生成文本
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "请解释人工智能的基本概念",
    "max_length": 512,
    "temperature": 0.7
  }'
```

### 使用Python测试

```python
import requests
import json

# 配置
BASE_URL = "http://localhost:8000"

# 健康检查
response = requests.get(f"{BASE_URL}/health")
print("健康检查:", response.json())

# 生成文本
data = {
    "prompt": "请解释人工智能的基本概念",
    "max_length": 512,
    "temperature": 0.7,
    "top_p": 0.9
}

response = requests.post(f"{BASE_URL}/generate", json=data)
result = response.json()

print("\n生成结果:")
print("提示:", result.get("prompt"))
print("生成文本:", result.get("generated_text"))
print("模型:", result.get("model"))
```

## 📊 资源消耗

不同模型的资源消耗估计：

| 模型 | 磁盘空间 | GPU内存 | RAM | 时间 |
|-----|---------|---------|-----|------|
| deepseek-1b | ~2GB | 4GB | 8GB | ~10分钟 |
| deepseek-7b | ~14GB | 16GB | 32GB | ~30-60分钟 |
| deepseek-33b | ~65GB | 24GB+ | 64GB | ~2-4小时 |

## ⚡ 性能优化建议

### 加速下载

1. **使用代理** (如果在中国):
   ```bash
   export HF_ENDPOINT=https://huggingface.co
   ```

2. **多线程下载**:
   系统已自动配置，无需额外操作

### 加速微调

1. **使用混合精度训练**:
   已在默认配置中启用 (bf16=True)

2. **增加梯度堆积步数**:
   ```
   gradient_accumulation_steps: 8
   ```

3. **减小batch size**:
   从4降低到2以节省内存

### 加速推理

1. **使用量化模型**:
   在微调时启用4-bit或8-bit量化

2. **使用Flash Attention**:
   自动在支持的硬件上启用

## 🚨 常见错误及解决方案

| 错误 | 原因 | 解决方案 |
|-----|-----|---------|
| `ImportError: No module named 'agents'` | Python路径错误 | 确保在项目根目录运行 |
| `HF 401 Unauthorized` | Token无效 | 重新设置HUGGINGFACE_TOKEN |
| `CUDA out of memory` | GPU内存不足 | 减小batch_size或使用更小的模型 |
| `Connection timeout` | 网络问题 | 检查网络连接，考虑使用代理 |
| `FileNotFoundError: model not found` | 模型下载失败 | 删除不完整的文件，重新下载 |

## 📚 下一步

- 查看 [README.md](README.md) 获取详细文档
- 浏览 [agents/](agents/) 目录了解各Agent的实现
- 修改 [config.py](config.py) 自定义配置

## 🆘 需要帮助？

- 查看日志文件: `logs/agent_system.log`
- 检查特定Agent的日志: `logs/interaction_agent.log` 等
- 使用 `python main.py --help` 查看所有选项

## 📝 常用命令速查

```bash
# 启动完整流程
python main.py

# 检查已下载的模型
python main.py --check-models

# 列出所有Agent
python main.py --list-agents

# 显示系统版本
python main.py --version

# 显示帮助信息
python main.py --help

# 激活虚拟环境（Linux/Mac）
source venv/bin/activate

# 激活虚拟环境（Windows）
.\\venv\\Scripts\\activate

# 安装依赖
pip install -r requirements.txt

# 运行API服务
python finetuned_models/deploy_server_8000.py
```

---

祝你使用愉快！🎉

有任何问题，欢迎反馈！
