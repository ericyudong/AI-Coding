# 📁 项目结构详解

本文档详细说明了AI Agent模型管理系统的目录结构和各文件的用途。

## 目录树结构

```
agent-model-system/
├── 📄 main.py                    # ⭐ 主程序入口（运行此文件启动系统）
├── 📄 config.py                  # 系统配置文件
├── 📄 examples.py                # 使用示例脚本
├── 📄 requirements.txt            # Python依赖包列表
├── 📄 .env.example               # 环境变量配置示例
├── 📚 README.md                  # 完整文档
├── 📚 QUICKSTART.md              # 快速开始指南
├── 📚 PROJECT_STRUCTURE.md       # 本文件
│
├── 📁 agents/                    # 🤖 Agent模块目录
│   ├── 📄 __init__.py            # 包初始化文件
│   ├── 📄 base_agent.py          # 基础Agent类（所有Agent的父类）
│   ├── 📄 interaction_agent.py   # 交互Agent（与用户交互）
│   ├── 📄 download_agent.py      # 下载Agent（从HuggingFace下载模型）
│   └── 📄 finetune_agent.py      # 微调Agent（微调和部署模型）
│
├── 📁 models/                    # 📦 下载的模型存储目录
│   ├── deepseek-7b/              # 示例：下载的deepseek-7b模型
│   │   ├── config.json
│   │   ├── pytorch_model.bin
│   │   ├── tokenizer.json
│   │   ├── tokenizer_config.json
│   │   └── ...
│   └── [其他下载的模型]/
│
├── 📁 finetuned_models/          # 🎯 微调后的模型存储目录
│   ├── training_data/            # 训练数据
│   │   └── train.json            # 样本训练数据
│   ├── final_model/              # 最终微调后的模型
│   │   ├── config.json
│   │   ├── pytorch_model.bin
│   │   ├── tokenizer.json
│   │   └── ...
│   ├── 📄 finetune_script.py     # 自动生成的微调脚本
│   ├── 📄 deploy_server_8000.py  # 自动生成的API服务脚本
│   └── tensorboard_logs/         # TensorBoard日志
│
├── 📁 logs/                      # 📝 系统日志目录
│   ├── 📄 agent_system.log       # 主系统日志
│   ├── 📄 interaction_agent.log  # 交互Agent日志
│   ├── 📄 download_agent.log     # 下载Agent日志
│   └── 📄 finetune_agent.log     # 微调Agent日志
│
└── 📁 tests/                     # 🧪 测试目录（可选）
    ├── 📄 test_agents.py
    ├── 📄 test_download.py
    └── 📄 test_finetune.py
```

## 核心文件详解

### 📄 main.py - 主程序

**用途**: 系统的主入口点

**主要功能**:
- 初始化所有三个Agent
- 协调Agent的执行顺序
- 处理命令行参数
- 显示系统信息

**包含的命令**:
- `python main.py` - 启动完整工作流程
- `python main.py --check-models` - 检查已下载模型
- `python main.py --list-agents` - 列出所有Agent
- `python main.py --help` - 显示帮助信息

### 📄 config.py - 配置文件

**用途**: 集中管理系统配置

**包含的配置**:
- 目录路径配置
- Agent配置
- 模型列表
- 默认参数
- 日志设置

### 📁 agents/ - Agent模块

#### 📄 base_agent.py
所有Agent的父类，提供：
- 日志记录功能
- 状态管理
- 通用方法接口

#### 📄 interaction_agent.py
**InteractionAgent - 交互Agent**

职责:
- 显示系统欢迎信息
- 与用户交互选择模型
- 询问微调参数
- 协调其他两个Agent
- 管理整个工作流程

关键方法:
- `execute()` - 主执行方法
- `_ask_model_selection()` - 询问用户选择模型
- `_ask_finetune_params()` - 询问微调参数
- `_ask_deploy()` - 询问是否部署

#### 📄 download_agent.py
**ModelDownloadAgent - 下载Agent**

职责:
- 从HuggingFace下载Deepseek模型
- 管理本地模型库
- 支持断点续传
- 提供模型列表查询

关键方法:
- `execute()` - 下载特定模型
- `_download_from_huggingface()` - 从HF下载
- `list_downloaded_models()` - 列出已下载模型
- `_get_dir_size()` - 计算目录大小

#### 📄 finetune_agent.py
**ModelFinetuneAgent - 微调Agent**

职责:
- 使用LLamaFactory微调模型
- 生成样本训练数据
- 创建微调脚本
- 部署模型为API服务

关键方法:
- `execute()` - 执行微调
- `deploy_model()` - 部署模型
- `_create_finetune_config()` - 创建微调配置
- `_create_finetune_script()` - 生成微调脚本
- `_create_deploy_script()` - 生成部署脚本

### 📁 models/ - 模型存储目录

**内容**: 从HuggingFace下载的原始模型

**结构示例**:
```
models/
└── deepseek-7b/
    ├── config.json              # 模型配置
    ├── pytorch_model.bin        # 模型权重
    ├── tokenizer.json           # 分词器配置
    ├── tokenizer_config.json    # 分词器详细配置
    ├── special_tokens_map.json  # 特殊令牌映射
    └── generation_config.json   # 生成配置
```

### 📁 finetuned_models/ - 微调模型输出目录

**包含内容**:

1. **training_data/** - 训练数据
   - `train.json` - 样本训练数据（自动生成）

2. **final_model/** - 微调后的最终模型
   - 与原模型结构相同
   - 权重已更新

3. **生成的脚本**:
   - `finetune_script.py` - 微调执行脚本
   - `deploy_server_8000.py` - API服务脚本

4. **tensorboard_logs/** - 训练日志（如果启用）

### 📁 logs/ - 日志目录

**包含的日志文件**:

| 文件 | 说明 |
|-----|------|
| `agent_system.log` | 主系统日志，记录所有操作 |
| `interaction_agent.log` | 交互Agent的专用日志 |
| `download_agent.log` | 下载Agent的专用日志 |
| `finetune_agent.log` | 微调Agent的专用日志 |

**日志内容包括**:
- 时间戳
- 操作状态（INFO, WARNING, ERROR）
- 详细消息
- 错误堆栈跟踪（如适用）

## 工作流程中的数据流

```
用户交互 (InteractionAgent)
      ↓
  选择模型
      ↓
ModelDownloadAgent 下载模型 → 保存到 models/
      ↓
  用户选择是否微调
      ↓
  是: ModelFinetuneAgent 读取 models/ 中的模型
      ↓
      生成训练数据 → finetuned_models/training_data/
      ↓
      创建微调脚本 → finetuned_models/finetune_script.py
      ↓
      运行脚本进行微调
      ↓
      微调完成后保存到 → finetuned_models/final_model/
      ↓
      创建API部署脚本 → finetuned_models/deploy_server_*.py
      ↓
  用户选择是否部署
      ↓
  是: 启动FastAPI服务
      ↓
  完成
```

## 配置和数据管理

### 环境变量
- 从 `.env` 文件或系统环境变量读取
- 包括HuggingFace token、日志级别等

### 配置文件
- `config.py` 定义所有系统配置
- 包括目录路径、Agent配置、默认参数等

### 模型管理
- 原始模型: `models/` 目录
- 微调后的模型: `finetuned_models/` 目录
- 每个模型占用大量磁盘空间（10GB-70GB+）

## 扩展和定制

### 添加新的Agent
1. 在 `agents/` 目录创建新文件
2. 继承 `BaseAgent` 类
3. 实现 `execute()` 方法
4. 在 `agents/__init__.py` 中导入

### 修改配置
编辑 `config.py` 中的配置值，无需修改其他代码

### 添加新的模型
修改 `config.py` 中的 `DEEPSEEK_MODELS` 字典

### 自定义微调参数
修改 `config.py` 中的 `DEFAULT_FINETUNE_PARAMS`

## 文件大小估计

| 项目 | 大小 | 说明 |
|-----|------|------|
| deepseek-1b 模型 | ~2GB | 最小模型 |
| deepseek-7b 模型 | ~14GB | 常用模型 |
| deepseek-33b 模型 | ~65GB | 最大模型 |
| 日志文件 | ~10-100MB | 取决于详细程度 |
| 训练数据 | ~1KB | 样本数据 |

**总需求**: 根据选择的模型，需要20GB-150GB的磁盘空间

## 常见操作和位置

| 操作 | 位置 |
|-----|------|
| 启动系统 | 运行 `python main.py` |
| 查看日志 | 打开 `logs/agent_system.log` |
| 查看已下载模型 | 浏览 `models/` 目录 |
| 启动API服务 | 运行 `python finetuned_models/deploy_server_8000.py` |
| 修改配置 | 编辑 `config.py` |
| 运行示例 | 执行 `python examples.py` |

---

📌 **提示**: 定期检查 `logs/` 目录以了解系统运行状态，定期清理 `logs/` 中的旧日志文件以节省空间。
