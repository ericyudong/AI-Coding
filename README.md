# Eric's AI Project Collection

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-Latest-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Projects-19-orange.svg" alt="Project Count">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

## 🌟 Introduction

Welcome to Eric's AI Project Collection! This repository brings together several cutting-edge AI-related projects, organized into two major categories: **AI Infra** and **AI Agent** — covering a complete ecosystem from infrastructure and platform tooling to intelligent agent systems and enterprise applications.

---

## 📂 Project Categories

- 🏗️ **Category 1: AI Infra** — AI infrastructure, gateways, guardrails, GPU/HPC resource management, OCR/AI showcase tools, and utility scripts.
- 🤖 **Category 2: AI Agent** — Open-source agent frameworks, multi-agent systems, enterprise AI agent platforms, and vertical-domain agents.

---

# 🏗️ Category 1: AI Infra

AI infrastructure platforms, model gateways with guardrails, GPU/HPC resource management, OCR/AI showcase systems, and development utilities.

## 🛡️ 1.1 Inference Gateway & Guardrails

### AIGateway 🛡️
- **Description**: Unified LLM inference gateway built on LiteLLM Proxy with multi-model routing, six-layer guardrails, and full observability/auditing. Designed for financial compliance with gate thresholds: jailbreak bypass ≤ 2%, false positive ≤ 2%, PII leak = 0, groundedness ≥ 0.9.
- **Key Features**:
  - Six-layer guardrails: Input (Presidio PII, Lakera, injection), Dialog, Retrieval, Tool, Output (LlamaGuard/Bedrock), Monitoring (Langfuse/OTel)
  - Policy-as-code (`policy.yaml`) with validation and eval gates
  - Tier-based model routing via `x-model-tier` header
  - Rollback scripts (route, canary weight, GitOps image) with MTTR ≤ 15 min
  - Docker Compose and Kubernetes/Argo CD deployments

### DevGuard 🔒
- **Description**: AI Guardrails monorepo with Argo CD-native GitOps. Combines CI build gates with guardrail evaluation and GitOps deployment via Argo CD, Argo Rollouts, and Gatekeeper.
- **Key Features**:
  - CI gates: policy validation, unit tests, eval, red-team checks
  - Gate thresholds: jailbreak bypass ≤ 2%, false positive ≤ 2%, PII leak = 0%
  - Argo CD self-healing and auto-rollback on SLO breach
  - Admission control via Gatekeeper constraints
  - Compliance support (SR 11-7 / DORA / MiFID II / GDPR Art.22)

---

## ☸️ 1.2 Cloud-Native DevOps

### K8s DevOps (Tekton + Argo CD) ☸️
- **Description**: Complete GitOps demonstration combining Tekton CI pipelines with Argo CD continuous delivery, featuring a sample Go application.
- **Key Features**:
  - Tekton pipeline: git-clone → build-push-image (Kaniko) → update-manifest
  - Argo CD auto-sync from Git manifests to Kubernetes cluster
  - Optional webhook-triggered CI via Tekton Triggers
  - Sample Go app runnable locally without Kubernetes

---

## 🖥️ 1.3 GPU & HPC Resource Management

### GPU Allocator 🖥️
- **Description**: Web management system for allocating NVIDIA GPUs by card.
- **Key Features**: GPU resource pool management, application management, per-card allocation, real-time status refresh, memory usage visualization

### Slurm Job Manager 👔
- **Description**: Distributed HPC job management and monitoring web frontend system based on Slurm.
- **Key Features**: Job submission and cancellation, real-time monitoring (refresh every 10 seconds), node status view, job statistics, dark theme UI

---

## 💬 1.4 Tools & Showcase Systems

### OCR Test Platform 📄
- **Description**: Web platform for testing OCR model performance, supporting document upload, OCR recognition, and visual model configuration.
- **Key Features**:
  - Document upload via drag-and-drop (PNG, JPG, JPEG, TIFF, BMP, GIF, PDF)
  - Automatic PDF page conversion and per-page recognition with merged results
  - Multi-engine support: Tesseract, PaddleOCR, EasyOCR, OvisOCR
  - Visual engine configuration (language, PSM, OEM, GPU, preprocessing)
  - Recognition history, text copy, and TXT export
- **Tech Stack**: FastAPI, HTML5 + CSS3 + JavaScript, PyMuPDF

### AI Models Showcase
- **Description**: AI model showcase platform for demonstrating and testing various AI model capabilities.
- **Key Features**: Model comparison, interactive demos, performance evaluation

### ClawManager 🎛️
- **Description**: Kubernetes-first control plane for managing OpenClaw and Linux desktop runtimes at team and cluster scale. Acts as a virtual desktop management platform with batch deployment, Webtop support, desktop portal access, runtime image settings, OpenClaw memory/preferences Markdown backup and migration, and built-in AI Gateway for model governance, audit, cost accounting, and risk control.
- **Key Features**:
  - One admin panel for users, quotas, instances, and runtime images
  - OpenClaw import/export for memory and preferences
  - Secure browser access without exposing pods directly
  - AI Gateway with model governance, audit trails, cost analysis, and risk controls
  - Kubernetes-native deployment with admin-managed rollout and self-service instance creation
  - Multilingual documentation (English / 中文 / 日本語 / 한국어 / Deutsch)

### Util Scripts 🛠️
- **Description**: Collection of utility scripts for converting exam, answer, and token evaluation data to Word documents.
- **Key Features**: convert_exam_to_word.py, convert_answers_to_word.py, convert_token_eval_to_word.py, convert_to_word.py

---

# 🤖 Category 2: AI Agent

Open-source agent frameworks, multi-agent systems, enterprise AI agent platforms, and vertical-domain intelligent agents.

## 🧠 2.1 Open-Source Agent Frameworks

### OpenAkita 🌐
- **Description**: Open-source multi-agent AI assistant platform. Multiple AI agents collaborate as an "AI company" that autonomously gets things done — web search, computer operation, file management, and scheduled tasks across 6 IM platforms (Telegram, Feishu, WeCom, DingTalk, QQ, etc.).
- **Key Features**:
  - Multi-agent collaboration and organization orchestration
  - Plugin system with 89+ tools
  - 6-layer sandbox security
  - 30+ LLM support
  - Desktop / Web / Mobile clients

### OpenClaw
- **Description**: Open-source AI agent framework supporting tool calling, multimodal interaction, and adaptive learning.
- **Key Features**: Tool ecosystem, custom agent creation, extensible architecture

---

## 🤖 2.2 Multi-Agent Collaboration Systems

### Agent Model System 🤖
- **Description**: Powerful three-agent collaboration system for automatically downloading Deepseek models from HuggingFace, fine-tuning, and deploying locally.
- **Key Features**: InteractionAgent (interaction coordination), ModelDownloadAgent (automatic downloading), ModelFinetuneAgent (automatic fine-tuning and deployment)

### Agent Harness Framework 🔧
- **Description**: Engineering framework for agent runtime management, memory management, and self-evolution. Provides a complete agent lifecycle with telemetry-driven optimization.
- **Key Features**:
  - Full agent lifecycle management (init, run, pause, resume, terminate)
  - Multi-tier memory architecture (short-term, long-term, working memory)
  - Runtime telemetry collection (behavior, metrics, interactions)
  - Self-evolution engine for automatic strategy and prompt optimization
  - Web monitoring UI

---

## 🏢 2.3 Enterprise AI Platforms

### E-Claw 🏗️
- **Description**: Enterprise-grade AI agent runtime platform based on OpenClaw, supporting multi-tenant isolation and RAG retrieval.
- **Key Features**:
  - Multi-tenant isolation
  - Task management and checkpoint resume
  - Knowledge base and RAG retrieval
  - RBAC permission control
  - Resource quota management
  - Unified AI gateway
  - Audit logging
- **Tech Stack**: FastAPI, Vue 3, PostgreSQL, Redis, Docker, Kubernetes

### RecruitOS + HR Agent 👥
- **Description**: Recruitment management system (RecruitOS) with an integrated HR Agent AI service providing understanding, generation, and recommendation capabilities. RecruitOS depends on the HR Agent for all AI features.
- **Key Features**:
  - Full recruitment workflow: data, rules, permissions, execution, and audit
  - HR Agent with LLM-powered drafting, parsing, dialogue, and analysis
  - JWT authentication with role-based permissions (8 demo roles)
  - Offline mock mode when no API key is configured
- **Tech Stack**: React + TypeScript + Vite + Ant Design + Recharts, Express + TypeScript + Prisma + SQLite

### JIRA System 👔
- **Description**: Project management and issue tracking system (JIRA-like), supporting user management, project management, issue tracking, and commenting.
- **Tech Stack**: FastAPI, Vue 3, PrimeVue, SQLite

---

## 💬 2.4 Intelligent Q&A & Vertical Agents

### DeepSeek QA System 💬
- **Description**: Intelligent Q&A system based on FastAPI + DeepSeek LLM, supporting multi-turn conversations and conversation history management.
- **Key Features**: DeepSeek LLM integration, multi-turn conversations, modern web interface, asynchronous processing, conversation history management

### AI QA System
- **Description**: Intelligent Q&A system based on LangChain, supporting document understanding and context-based question answering.
- **Key Features**: RAG retrieval, document vector indexing, multilingual support

### Legal Agent ⚖️
- **Description**: Intelligent legal agent platform with a portal home, legal research, contract review/drafting, and labor-law Q&A modules, built from UI design specifications.
- **Key Features**:
  - Legal search: regulation query, similar case retrieval, administrative penalties, professional interpretation
  - Contract review: doc/docx/pdf upload with checklist and reference-based review
  - Contract drafting with multiple drafting styles
  - Q&A AI for labor law, financial compliance, and enterprise globalization
- **Tech Stack**: Vue 3 + TypeScript + Vite + Element Plus + Pinia, FastAPI + SQLAlchemy + SQLite, OpenAI-compatible API

---

## 🗂️ Project Architecture Overview

```
Eric's AI Project Collection
│
├── 🏗️ AI Infra
│   ├── 🛡️ Inference Gateway & Guardrails
│   │   ├── AIGateway/                # LiteLLM gateway + 6-layer guardrails
│   │   └── DevGuard/                 # AI guardrails GitOps (Argo CD)
│   │
│   ├── ☸️ Cloud-Native DevOps
│   │   └── k8sdevops/                # Tekton CI + Argo CD GitOps
│   │
│   ├── 🖥️ GPU & HPC Resource Management
│   │   ├── gpu-allocator/            # GPU allocation system
│   │   └── slurm-job-manager/        # Slurm job management
│   │
│   └── 💬 Tools & Showcase
│       ├── ocr-test-platform/        # OCR model testing platform
│       ├── ai-models-showcase/       # AI model showcase
│       ├── ClawManager-main/         # Kubernetes-native virtual desktop control plane + AI Gateway
│       └── util/                     # Utility scripts
│
└── 🤖 AI Agent
    ├── 🧠 Open-Source Agent Frameworks
    │   ├── openakita/                # Open-source multi-agent AI assistant
    │   └── openclaw-main/            # AI agent framework
    │
    ├── 🤖 Multi-Agent Collaboration
    │   ├── agent-model-system/       # Three-agent collaboration system
    │   └── agent-harness/            # Agent runtime + memory + self-evolution
    │
    ├── 🏢 Enterprise AI Platforms
    │   ├── e-claw/                   # Enterprise AI agent platform
    │   ├── recruit-agent/            # RecruitOS + HR Agent
    │   └── jira-system/              # Project management system
    │
    └── 💬 Intelligent Q&A & Vertical Agents
        ├── deepseek-qa-system/       # DeepSeek Q&A system
        ├── ai-qa-system/             # Intelligent Q&A system
        └── legal-agent/              # Intelligent legal agent platform
```

---

## 🚀 Quick Start

### 🖥️ For Developers

```bash
# Clone the repository
git clone https://github.com/ericyudong/AI-Coding.git
cd AI-Coding

# Set up Python virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install basic dependencies
pip install fastapi uvicorn sqlalchemy langchain
```

### 🛡️ Run AIGateway Locally

```bash
cd AIGateway
cp .env.example .env
pip install -r requirements.txt
python scripts/validate_policy.py
cd deployments && docker compose up -d --build
```

### 🏢 Deploy E-Claw Enterprise Platform

```bash
cd e-claw/backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 📄 Launch OCR Test Platform

```bash
cd ocr-test-platform/backend
pip install -r requirements.txt
python main.py
# Visit http://localhost:8000
```

---

## 📖 Detailed Documentation

### AI Infra

| Project | Documentation |
|---------|---------------|
| **AIGateway** | [AIGateway/README.md](./AIGateway/README.md) |
| **DevGuard** | [DevGuard/README.md](./DevGuard/README.md) |
| **K8s DevOps** | [k8sdevops/README.md](./k8sdevops/README.md) |
| **GPU Allocator** | [gpu-allocator/README.md](./gpu-allocator/README.md) |
| **Slurm Job Manager** | [slurm-job-manager/README.md](./slurm-job-manager/README.md) |
| **OCR Test Platform** | [ocr-test-platform/README.md](./ocr-test-platform/README.md) |
| **AI Models Showcase** | [ai-models-showcase/README.md](./ai-models-showcase/README.md) |
| **ClawManager** | [ClawManager-main/ClawManager-main/README.md](./ClawManager-main/ClawManager-main/README.md) |
| **Util Scripts** | [util/](./util/) |

### AI Agent

| Project | Documentation |
|---------|---------------|
| **OpenAkita** | [openakita/README.md](./openakita/README.md) |
| **OpenClaw** | [openclaw-main/README.md](./openclaw-main/README.md) |
| **Agent Model System** | [agent-model-system/README.md](./agent-model-system/README.md) |
| **Agent Harness** | [agent-harness/README.md](./agent-harness/README.md) |
| **E-Claw** | [e-claw/README.md](./e-claw/README.md) |
| **DeepSeek QA System** | [deepseek-qa-system/README.md](./deepseek-qa-system/README.md) |
| **AI QA System** | [ai-qa-system/README.md](./ai-qa-system/README.md) |
| **Legal Agent** | [legal-agent/README.md](./legal-agent/README.md) |
| **RecruitOS + HR Agent** | [recruit-agent/README.md](./recruit-agent/README.md) |
| **JIRA System** | [jira-system/](./jira-system/) |

---

## 🛠️ Technology Stack Overview

### Core Technologies
- **Programming Languages**: Python 3.11+, TypeScript, JavaScript, Go
- **Web Frameworks**: FastAPI, Flask, Vue 3, React, Express, Element Plus, Ant Design
- **Databases**: PostgreSQL, MongoDB, SQLite, Redis, Prisma
- **ML/DL Frameworks**: PyTorch, TensorFlow, LangChain, Transformers
- **Containerization & DevOps**: Docker, Kubernetes, Argo CD, Argo Rollouts, Tekton, Gatekeeper
- **Development Tools**: Git, VS Code, JupyterLab

### AI-Related Technologies
- **Vector Databases**: ChromaDB, FAISS
- **Agent Frameworks**: LangChain, OpenClaw
- **AI Safety & Guardrails**: Presidio, Lakera, LlamaGuard, Bedrock, policy-as-code
- **Model Deployment**: LiteLLM, Ollama
- **OCR Engines**: Tesseract, PaddleOCR, EasyOCR, OvisOCR
- **Data Processing**: Pandas, NumPy, Dask

---

## 🌟 Use Cases

### 👨‍💼 Enterprise Applications
- Customer service automation
- Document processing and analysis (OCR, contract review)
- Knowledge management and legal research
- Recruitment management and HR AI assistance
- Workflow automation
- Issue tracking and management
- GPU resource allocation
- HPC job scheduling
- AI gateway with guardrails for financial compliance

### 🎓 Education & Research
- Academic research support
- Experiment tracking
- Model fine-tuning

### 🔄 Developer Tools
- Code generation assistance
- Automated testing
- CI/CD integration (Tekton, Argo CD, GitOps)
- API development
- Multi-agent orchestration

---

## 🤝 Contributing

We welcome all forms of contributions!

### How to Contribute
1. Fork this repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Create a Pull Request

### Code Standards
- **Python**: Follow PEP 8 style guide
- **TypeScript**: Use ESLint and Prettier
- **Comments**: Provide clear documentation
- **Testing**: Write tests for new features

---

## 📝 License

Most projects use the MIT License. Some projects (e.g., OpenAkita uses AGPL-3.0) have their own licenses — please check the LICENSE file in each project for details.

---

## 🙏 Acknowledgments

Special thanks to all contributors in the open-source community, especially:

- **OpenAkita** - Multi-agent AI assistant
- And all other open-source projects that inspired this collection

---

## 📧 Contact

- **Maintainer**: Eric
- **Email**: [yudongeric@gmail.com]
- **GitHub**: [@ericyudong](https://github.com/ericyudong)
- **Project Repository**: [https://github.com/ericyudong/AI-Coding](https://github.com/ericyudong/AI-Coding)

---

## 📊 Project Statistics

- **Total Projects**: 19
- **Categories**: AI Infra (9), AI Agent (10)
- **Language Support**: Python, TypeScript, JavaScript, Go
- **Total Lines of Code**: 100,000+
- **Open Source Licenses**: MIT, AGPL-3.0
- **Highlights**: ClawManager (Kubernetes-native virtual desktop + AI Gateway), OpenAkita (multi-agent), AIGateway (6-layer guardrails)

---

<div align="center">

  **[⬆ Back to Top](#erics-ai-project-collection)**

  <br>

  Made with ❤️ by Eric

  Last updated: 2026-08-12

</div>