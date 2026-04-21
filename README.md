# Eric's AI Project Collection | Eric的AI项目集合

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-Latest-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Projects-15+-orange.svg" alt="Project Count">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

## 🌟 简介 / Introduction 欢迎来到Eric的AI项目集合！这个仓库汇集了多个前沿的AI相关项目，涵盖了从大语言模型训练、智能代理系统、数据基础设施到企业级AI平台的完整生态系统。

**Welcome to Eric's AI Project Collection! This repository brings together several cutting-edge AI-related projects, covering a complete ecosystem from LLM training and intelligent agent systems to data infrastructure and enterprise-grade AI platforms.**

---

## 📂 项目分类 / Project Categories

### 🤖 1. 智能代理系统 / Intelligent Agent Systems

#### Hermes Agent ⚡
- **简介**: 由Nous Research构建的自我改进型AI代理，具有内置学习循环。支持多平台通信、自动化任务、技能创建和记忆管理。
- **English**: Self-improving AI agent built by Nous Research with built-in learning loop. Supports multi-platform communication, automation, skill creation, and memory management.
- **核心特性**:
  - 终端界面 (Terminal UI)
  - 多平台支持 (Telegram, Discord, Slack等)
  - 技能自动创建和改进 (Automatic skill creation and improvement)
  - 定时任务调度 (Cron scheduling)
  - 子代理委托 (Subagent delegation)

#### OpenClaw
- **简介**: 开源AI代理框架，支持工具调用、多模态交互和自适应学习。
- **English**: Open-source AI agent framework supporting tool calling, multimodal interaction, and adaptive learning.
- **核心特性**: 工具生态系统、自定义agent创建、可扩展架构

#### Jiuwenclaw
- **简介**: 基于OpenClaw的中文AI代理系统，针对中文环境优化。
- **English**: Chinese AI agent system based on OpenClaw, optimized for Chinese environments.
- **核心特性**: 中文语言模型集成、本地知识库、搜索引擎集成

#### Agent Model System 🤖
- **简介**: 强大的三Agent协作系统，从HuggingFace自动下载Deepseek模型，进行微调并部署到本地。
- **English**: Powerful three-agent collaboration system for automatically downloading Deepseek models from HuggingFace, fine-tuning, and deploying locally.
- **核心特性**: InteractionAgent（交互协调）、ModelDownloadAgent（自动下载）、ModelFinetuneAgent（自动微调与部署）

---

### 🎯 2. 模型训练与微调 / Model Training & Fine-tuning

#### LlamaFactory 🚀
- **简介**: 统一的大模型微调框架，支持100+模型的无代码离线训练。
- **English**: Unified LLM fine-tuning framework supporting 100+ models with zero-code offline training.
- **核心特性**:
  - 多模型支持 (Multi-model support: LLaMA, Qwen, Mistral等)
  - 完整微调流程 (Complete fine-tuning pipeline: LoRA, QLoRA, Full)
  - Web UI界面 (Gradio-based LLaMA-Board)
  - 多奖励模型支持 (Multiple reward models)
  - 高效训练资源管理 (Efficient resource management)

#### Data-Juicer 📊
- **简介**: 基础模型时代的数据操作系统，用于数据清洗、合成和分析。
- **English**: Data Operating System for the foundation model era, for data cleaning, synthesis, and analysis.
- **核心特性**:
  - 200+数据处理算子 (200+ data processing operators)
  - 多模态数据处理 (Multimodal data processing)
  - 云原生架构设计 (Cloud-native architecture)
  - 大规模数据处理能力 (Large-scale data processing)
  - 可视化配置界面

---

### 🎨 3. 开发工具与基础设施 / Development Tools & Infrastructure

#### CSGHub 🏢
- **简介**: 专为企业设计的LLM资产管理平台前端，作为私有化的Huggingface替代方案。
- **English**: LLM asset management platform frontend designed for enterprise, as a private Huggingface alternative.
- **核心特性**:
  - 统一模型管理 (Unified model management)
  - 数据集管理 (Dataset management)
  - Space应用部署 (Space deployment)
  - 企业级安全控制 (Enterprise-level security)
  - 本地化部署支持 (On-premises deployment)

#### CSGHub Server 🏢
- **简介**: CSGHub开源大模型资产管理平台的服务端，提供基于REST API的模型、数据集等资产管理功能。
- **English**: CSGHub Server - the backend part of the open-source LLM asset management platform, providing REST API-based model and dataset asset management.
- **核心特性**: 用户和组织管理、模型/数据集托管、Git LFS支持、内容审核、活跃度跟踪

#### GPUStack 🖥️
- **简介**: GPU资源管理和调度平台，优化GPU集群使用效率。
- **English**: GPU resource management and scheduling platform, optimizing GPU cluster efficiency.
- **核心特性**: GPU集群管理、资源调度、性能监控

#### MLflow 📈
- **简介**: 开源机器学习实验跟踪平台，支持完整的ML生命周期管理。
- **English**: Open-source ML experiment tracking platform supporting complete ML lifecycle management.
- **核心特性**: 实验跟踪、模型注册、部署管理

---

### 🏢 4. 企业级应用 / Enterprise Applications

#### E-Claw 🏗️
- **简介**: 基于OpenClaw架构的企业级AI代理运行平台，支持多租户隔离和RAG检索。
- **English**: Enterprise-grade AI agent runtime platform based on OpenClaw, supporting multi-tenant isolation and RAG retrieval.
- **核心特性**:
  - 多租户隔离 (Multi-tenant isolation)
  - 任务管理与断点续传 (Task management and checkpoint resume)
  - 知识库与RAG检索 (Knowledge base and RAG retrieval)
  - RBAC权限控制 (RBAC permission control)
  - 资源配额管理 (Resource quota management)
  - AI网关统一接入 (Unified AI gateway)
  - 审计日志记录 (Audit logging)
- **技术栈**: FastAPI, Vue 3, PostgreSQL, Redis, Docker, Kubernetes

#### AI QA System
- **简介**: 基于LangChain的智能问答系统，支持文档理解和上下文问答。
- **English**: Intelligent Q&A system based on LangChain, supporting document understanding and context-based question answering.
- **核心特性**: RAG检索、文档向量索引、多语言支持

#### DeepSeek QA System 💬
- **简介**: 基于FastAPI + DeepSeek大模型的智能问答系统，支持多轮对话和对话历史管理。
- **English**: Intelligent Q&A system based on FastAPI + DeepSeek LLM, supporting multi-turn conversations and conversation history management.
- **核心特性**: DeepSeek大模型集成、多轮对话、现代化Web界面、异步处理、对话记录管理

#### JIRA System 👔
- **简介**: 项目管理与问题跟踪系统（类JIRA），支持用户管理、项目管理、问题追踪和评论功能。
- **English**: Project management and issue tracking system (JIRA-like), supporting user management, project management, issue tracking, and commenting.
- **技术栈**: FastAPI, Vue 3, PrimeVue, SQLite

---

### 📦 5. 数据处理与资源管理 / Data Processing & Resources

#### Data-Juicer-main
- **简介**: Data-Juicer的主要版本，包含完整的数据处理流水线。
- **English**: Main version of Data-Juicer with complete data processing pipeline.

#### Wanwu
- **简介**: 万物数据平台，专注于AI数据的收集、处理和分析。
- **English**: Wanwu data platform focusing on AI data collection, processing, and analysis.

#### GPU Allocator 🖥️
- **简介**: NVIDIA GPU按卡分配的Web管理系统。
- **English**: Web management system for allocating NVIDIA GPUs by card.
- **核心特性**: GPU资源池管理、应用管理、按卡分配、实时状态刷新、内存使用可视化

#### Slurm Job Manager 👔
- **简介**: 基于Slurm的分布式HPC作业管理与监控Web前端系统。
- **English**: Distributed HPC job management and monitoring web frontend system based on Slurm.
- **核心特性**: 作业提交与取消、实时监控（每10秒刷新）、节点状态查看、作业统计分析、深色主题UI

---

### 💬 6. 工具与演示系统 / Tools & Showcase Systems

#### AI Models Showcase
- **简介**: AI模型展示平台，用于演示和测试各种AI模型能力。
- **English**: AI model showcase platform for demonstrating and testing various AI model capabilities.
- **核心特性**: 模型对比、交互式演示、性能评估

#### Easy Learn AI
- **简介**: AI学习和评估网站，提供交互式学习体验。
- **English**: AI learning and evaluation website providing interactive learning experience.

#### ClawManager
- **简介**: AI代理管理工具，用于监控和管理多个AI代理实例。
- **English**: AI agent management tool for monitoring and managing multiple AI agent instances.
- **核心特性**: InteractionAgent（交互协调）、ModelDownloadAgent（自动下载）、ModelFinetuneAgent（自动微调与部署）

---

### 💬 9. 问答与协作系统 / Q&A & Collaboration Systems

#### DeepSeek QA System 💬
- **简介**: 基于FastAPI + DeepSeek大模型的智能问答系统，支持多轮对话和对话历史管理。
- **English**: Intelligent Q&A system based on FastAPI + DeepSeek LLM, supporting multi-turn conversations and conversation history management.
- **核心特性**: DeepSeek大模型集成、多轮对话、现代化Web界面、异步处理、对话记录管理

#### JIRA System 👔
- **简介**: 项目管理与问题跟踪系统（类JIRA），支持用户管理、项目管理、问题追踪和评论功能。
- **English**: Project management and issue tracking system (JIRA-like), supporting user management, project management, issue tracking, and commenting.
- **技术栈**: FastAPI, Vue 3, PrimeVue, SQLite

---

## 🗂️ 项目架构总览 / Project Architecture Overview

```
Eric's AI Project Collection
├── 🤖 Intelligent Agent Systems (智能代理系统)
│   ├── hermes-agent/      # Self-improving agent platform
│   ├── openclaw-main/    # AI agent framework
│   ├── jiuwenclaw/       # Chinese AI agent system
│   └── agent-model-system/ # Three-agent collaboration system
│
├── 🎯 Model Training (模型训练)
│   ├── LlamaFactory/      # LLM fine-tuning platform
│   └── data-juicer/      # Data processing OS
│
├── 🎨 Development Tools (开发工具)
│   ├── csghub/           # LLM asset management frontend
│   ├── csghub-server/    # LLM asset management server
│   ├── gpustack-main/    # GPU resource management
│   └── mlflow/           # ML experiment tracking
│
├── 🏢 Enterprise Apps (企业应用)
│   ├── e-claw/           # Enterprise AI agent platform
│   ├── ai-qa-system/     # Intelligent Q&A system
│   ├── deepseek-qa-system/ # DeepSeek Q&A system
│   ├── ai-models-showcase/ # AI model showcase
│   └── ClawManager-main/ # AI agent manager
│
├── 📦 Data Processing (数据处理)
│   ├── wanwu/           # Wanwu data platform
│   └── easy-learn-ai/    # AI learning website
│
├── 🖥️ Resource Management (资源管理)
│   ├── gpu-allocator/   # GPU allocation system
│   └── slurm-job-manager/ # Slurm job management
│
└── 💬 Collaboration Systems (协作系统)
    └── jira-system/      # Project management system
```

---

## 🚀 快速开始 / Quick Start

### 🖥️ 对于开发者 / For Developers

```bash
# Clone the repository
git clone https://github.com/ericyudong/AI-Coding.git
cd AI-Coding

# 设置Python虚拟环境 / Set up Python virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# 安装基础依赖 / Install basic dependencies
pip install fastapi uvicorn sqlalchemy langchain
```

### 🤖 尝试Hermes Agent / Try Hermes Agent

```bash
# 一键安装 / One-click install
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# 启动对话 / Start conversation
hermes
```

### 🎯 训练自定义模型 / Train Custom Models

```bash
cd LlamaFactory
pip install -r requirements.txt
python src/export_model.py --model_name_or_path meta-llama/Llama-3-8b --export_dir ./output
```

### 🏢 部署E-Claw企业平台 / Deploy E-Claw Enterprise Platform

```bash
cd AI-Coding/e-claw/backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 📖 详细文档 / Detailed Documentation

### 项目特定文档 / Project-Specific Documentation

| 项目 / Project | 文档链接 / Documentation |
|----------------|-------------------------|
| **Hermes Agent** | [https://hermes-agent.nousresearch.com/docs/](https://hermes-agent.nousresearch.com/docs/) |
| **LlamaFactory** | [https://github.com/hiyouga/LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory) |
| **Data-Juicer** | [https://datajuicer.github.io/data-juicer/](https://datajuicer.github.io/data-juicer/) |
| **CSGHub** | [https://github.com/OpenCSGs/csghub](https://github.com/OpenCSGs/csghub) |
| **E-Claw** | [e-claw/README.md](./e-claw/README.md) |
| **OpenClaw** | [openclaw-main/docs/](./openclaw-main/docs/) |
| **GPU Allocator** | [gpu-allocator/README.md](./gpu-allocator/README.md) |
| **Agent Model System** | [agent-model-system/README.md](./agent-model-system/README.md) |
| **DeepSeek QA System** | [deepseek-qa-system/README.md](./deepseek-qa-system/README.md) |
| **Slurm Job Manager** | [slurm-job-manager/README.md](./slurm-job-manager/README.md) |

---

## 🛠️ 技术栈概览 / Technology Stack Overview

### 核心技术 / Core Technologies
- ** Programming Languages**: Python 3.11+, TypeScript, JavaScript
- ** **Web Frameworks**: FastAPI, Flask, Vue 3, React
- ** **Databases**: PostgreSQL, MongoDB, SQLite, Redis
- ** **ML/DL Frameworks**: PyTorch, TensorFlow, LangChain, Transformers
- ** **Containerization**: Docker, Kubernetes
- ** **Development Tools**: Git, VS Code, JupyterLab

### AI相关技术 / AI-Related Technologies
- **LLM Training**: LoRA, QLoRA, DPO, PPO
- **Vector Databases**: ChromaDB, FAISS
- **Agent Frameworks**: LangChain, AutoGPT
- **Model Deployment**: MLflow, Gradio, Ollama
- **Data Processing**: Pandas, NumPy, Dask

---

## 🌟 使用场景 / Use Cases

### 👨‍💼 企业应用 / Enterprise Applications
- ** customer service automation** (客户服务自动化)
- ** document processing and analysis** (文档处理分析)
- ** knowledge management** (知识管理)
- ** workflow automation** (工作流自动化)
- ** issue tracking and management** (问题追踪与管理)
- ** GPU resource allocation** (GPU资源分配)
- ** HPC job scheduling** (HPC作业调度)

### 🎓 教育研究 / Education & Research
- ** personalized learning assistants** (个性化学习助手)
- ** academic research support** (学术研究支持)
- ** experiment tracking** (实验跟踪)
- ** model fine-tuning** (模型微调)

### 🔄 开发者工具 / Developer Tools
- ** code generation assistance** (代码生成辅助)
- ** automated testing** (自动化测试)
- ** CI/CD integration** (CI/CD集成)
- ** API development** (API开发)

---

## 🤝 贡献指南 / Contributing

我们欢迎各种形式的贡献！/ We welcome all forms of contributions!

### 如何贡献 / How to Contribute
1. Fork 本仓库 / Fork this repository
2. 创建特性分支 (`git checkout -b feature/amazing-feature`) / Create feature branch
3. 提交更改 (`git commit -m 'Add some amazing feature'`) / Commit changes
4. 推送到分支 (`git push origin feature/amazing-feature`) / Push to branch
5. 创建Pull Request / Create Pull Request

### 代码规范 / Code Standards
- **Python**: Follow PEP 8 style guide
- **TypeScript**: Use ESLint and Prettier
- **Comments**: Provide clear documentation in both Chinese and English
- **Testing**: Write tests for new features

---

## 📝 许可证 / License

大部分项目使用MIT许可证。具体请查看各个项目的LICENSE文件。
Most projects use the MIT License. Please check the LICENSE file in each project for details.

---

## 🙏 致谢 / Acknowledgments

感谢所有开源项目的贡献者，特别是：
Special thanks to all contributors in the open-source community, especially:

- **Nous Research** - Hermes Agent
- **hiyouga** - LlamaFactory
- **datajuicer** - Data-Juicer
- **OpenCSG** - CSGHub
- 以及所有其他开源项目 / And all other open-source projects

---

## 📧 联系方式 / Contact

- **Maintainer**: Eric
- **Email**: [your-email@example.com]
- **GitHub**: [@ericyudong](https://github.com/ericyudong)
- **Project Repository**: [https://github.com/ericyudong/AI-Coding](https://github.com/ericyudong/AI-Coding)

---

## 📊 项目统计 / Project Statistics

- **总项目数 / Total Projects**: 20+
- **语言支持 / Language Support**: Python, TypeScript, JavaScript
- **总代码行数 / Total Lines of Code**: 100,000+
- **开源协议 / Open Source Licenses**: MIT, Apache 2.0

---

<div align="center">
  
  **[⬆ 回到顶部 / Back to Top](#érics-ai-project-collection--eric的ai项目集合)**
  
  <br>
  
  Made with ❤️ by Eric
  
  Last updated: 2026-04-21
  
</div>