# Eric's AI Project Collection

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-Latest-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Projects-26-orange.svg" alt="Project Count">
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

### AI Cluster Gateway 🌐
- **Description**: OpenAI-compatible inference gateway on the shared CNCF OCM Hub: routes traffic to ManagedClusters and deploys models as ManifestWorks.
- **Key Features**:
  - Same OCM objects as k8s-cluster-explorer (`ManagedCluster` / `ManifestWork` / `Placement`)
  - `/v1/chat/completions` with alias, weighted routing, and failover
  - Pin traffic with `X-Cluster-Id` (cluster name) / `X-Region`
  - Deploy vLLM/TGI only after Hub Accept; GPU admission via Placement `gpu-inference`
  - Demo fleet: prod / staging / edge Available + pending `kind-dev`
- **Tech Stack**: FastAPI, kubernetes Python client, httpx, HTML5 + CSS3 + JavaScript

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

### K8s Multi-Cluster Manager 📡
- **Description**: CNCF Open Cluster Management (OCM) Hub–Spoke control plane: ManagedCluster handshake, ManifestWork pull, and Placement decisions, plus inventory on accepted clusters.
- **Key Features**:
  - Double opt-in join (`hubAcceptsClient`) instead of Hub storing spoke kubeconfigs as the core model
  - ManifestWork in the cluster namespace; in-process klusterlet pull/reconcile
  - Placement + PlacementDecision via labelSelector / claimSelector
  - ClusterClaims and OCM conditions (Accepted / Joined / Available)
  - Read-only inventory (nodes, pods, workloads) on accepted clusters
  - Demo Hub with 3 available spokes and 1 pending join
- **Tech Stack**: FastAPI, kubernetes Python client, HTML5 + CSS3 + JavaScript

### Git → GPU AI Factory 🏭
- **Description**: Interactive demo of a production AI/ML platform path — From Git Commit to NVIDIA GPU — with the principle that models are versioned artifacts, not containers.
- **Key Features**:
  - Vertical stack: Git → CI/CD → Kubeflow → Model Registry → KServe → Runtime → NVIDIA GPU
  - End-to-end simulated pipeline producing registry artifacts and InferenceServices
  - S3/MinIO ↔ OCI artifact migration; redeploy with XGBoost / Triton / vLLM
  - GPU generation selector: A100 → H100 → H200 (CUDA Cores → Tensor Cores → HBM → NVLink)
  - Architecture console aligned to the reference diagram
- **Tech Stack**: FastAPI, Pydantic, HTML5 + CSS3 + JavaScript

### AI/ML Factory (Kubeflow + KServe) 🚀
- **Description**: Production-grade Kubernetes AI/ML platform scaffold — editable Kubeflow Pipelines (Scheme B), MinIO/MLflow registry, KServe InferenceServices (XGBoost / Triton / vLLM), GPU overlays, Tekton + Argo CD.
- **Key Features**:
  - **Scheme B editable pipelines**: component library + YAML DAG specs → `from_spec` compile → KFP IR (`pipelines/specs` → `pipelines/compiled`)
  - Default chain: prepare → train → evaluate gate → register versioned S3 artifact
  - Model Registry: MinIO + MLflow; serving never bakes weights into images
  - KServe manifests for classical ML, Triton multi-framework, and vLLM LLM serving
  - Kustomize overlays (dev/staging/prod) for A100 → H100 → H200
  - GitHub Actions + Tekton CI; Argo CD Applications for GitOps
  - Web console on :8006 — architecture, **Pipeline editor**, local train, registry, KServe smoke predict
- **Tech Stack**: Kubeflow Pipelines v2, KServe, MinIO, MLflow, Triton, vLLM, Kustomize, Argo CD, Tekton, FastAPI

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

### OpenAI Codex 🧩
- **Description**: Local coding agent (Codex CLI / app-server) — model-driven command execution, file editing, MCP tools, and sandboxing; distributed via npm with a Rust core.
- **Key Features**:
  - Layered architecture: npm CLI → app-server (JSON-RPC) → codex-core → model / sandbox / MCP
  - TUI, exec (headless), IDE, and TypeScript/Python SDKs
  - MCP server/client integration for external tools
  - Platform sandbox + exec policy + user approval
- **Docs**: [codex/docs/architecture-analysis/](./codex/docs/architecture-analysis/)

### DeepSeek Harness 🔌
- **Description**: Cordis-based agent harness (DeepSeek Harness) with plugins, skills, MCP client, and headless CLI profiles — used to host vertical agents such as recruit-agent.
- **Key Features**:
  - Plugin system: tools, skills, MCP client (`@deepseek-ai/dsh-mcp-client`)
  - Headless profile for non-interactive agent runs
  - Example plugins including Recruit Agent (`@deepseek-ai/dsh-recruit-agent`)
- **Path**: [deepseek-harness-master/](./deepseek-harness-master/)

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
- **Description**: Recruitment management system (RecruitOS) with an integrated HR Agent AI service providing understanding, generation, and recommendation capabilities. Also packaged as a DeepSeek Harness plugin (`@deepseek-ai/dsh-recruit-agent`) with skills and tools for headless agent runs.
- **Key Features**:
  - Full recruitment workflow: data, rules, permissions, execution, and audit
  - HR Agent with LLM-powered drafting, parsing, dialogue, and analysis
  - JWT authentication with role-based permissions (8 demo roles)
  - Offline mock mode when no API key is configured
  - DeepSeek Harness plugin: skills (`hr-recruitment`, JD/resume/interview/offer) + RecruitOS/HR Agent HTTP tools
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

### Legal Agent MCP 🔗
- **Description**: MCP Server that exposes Legal Agent capabilities to AI hosts (Cursor, Codex, DeepSeek Harness) over stdio. Thin adapter: MCP protocol ↔ HTTP + JWT ↔ Legal Agent backend (`:8010`).
- **Key Features**:
  - Six MCP tools: `legal_search`, `legal_chat`, `contract_draft`, `contract_review_file`, `contract_compare_files`, `legal_capabilities`
  - Lazy JWT auth (`LEGAL_AGENT_TOKEN` or username/password login)
  - Integrates with Cursor (`mcp.json`), Codex (`config.toml`), and DeepSeek Harness MCP client
  - Architecture docs + PPT: [legal-agent-mcp/docs/](./legal-agent-mcp/docs/)
- **Tech Stack**: TypeScript, Node.js ≥ 20, `@modelcontextprotocol/sdk`, Zod
- **Path**: [legal-agent-mcp/](./legal-agent-mcp/)

### AgentScope 🧩
- **Description**: Alibaba AgentScope multi-agent framework (vendored source) plus a Legal Agent runnable example that connects via MCP.
- **Key Features**:
  - Framework source under [agentscope/](./agentscope/)
  - Legal Agent on AgentScope 2.x: [legal-agent/agentscope/](./legal-agent/agentscope/) (`MCPClient` + `legal-agent-mcp`)
- **Tech Stack**: Python 3.10+, AgentScope 2.x, MCP stdio

### BiSheng (毕昇) 🏭
- **Description**: DataElem BiSheng enterprise LLM application platform (workflow / RAG / multi-tenant), runnable via Docker Compose.
- **Key Features**: Frontend `:3001`, backend API `:7860`, MySQL / Redis / Milvus / ES / OpenFGA
- **Path**: [bisheng/](./bisheng/) · start: `cd bisheng/docker && docker compose -f docker-compose.yml -p bisheng up -d`

---

## 🗂️ Project Architecture Overview

```
Eric's AI Project Collection
│
├── 🏗️ AI Infra
│   ├── 🛡️ Inference Gateway & Guardrails
│   │   ├── AIGateway/                # LiteLLM gateway + 6-layer guardrails
│   │   ├── ai-cluster-gateway/       # OCM-based inference routing + ManifestWork deploy
│   │   └── DevGuard/                 # AI guardrails GitOps (Argo CD)
│   │
│   ├── ☸️ Cloud-Native DevOps
│   │   ├── k8sdevops/                # Tekton CI + Argo CD GitOps
│   │   ├── k8s-cluster-explorer/     # OCM Hub-Spoke multi-cluster manager
│   │   ├── git-to-gpu/               # Git→Kubeflow→KServe→GPU narrative demo
│   │   └── ai-ml-factory/            # Production Kubeflow + editable specs + KServe + MinIO/MLflow
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
    │   ├── openclaw-main/            # AI agent framework
    │   ├── agentscope/               # Alibaba AgentScope multi-agent framework
    │   ├── codex/                    # OpenAI Codex CLI / app-server
    │   └── deepseek-harness-master/  # Cordis agent harness + MCP client
    │
    ├── 🤖 Multi-Agent Collaboration
    │   ├── agent-model-system/       # Three-agent collaboration system
    │   └── agent-harness/            # Agent runtime + memory + self-evolution
    │
    ├── 🏢 Enterprise AI Platforms
    │   ├── e-claw/                   # Enterprise AI agent platform
    │   ├── recruit-agent/            # RecruitOS + HR Agent (+ DSH plugin)
    │   ├── bisheng/                  # BiSheng LLM app platform (Docker)
    │   └── jira-system/              # Project management system
    │
    └── 💬 Intelligent Q&A & Vertical Agents
        ├── deepseek-qa-system/       # DeepSeek Q&A system
        ├── ai-qa-system/             # Intelligent Q&A system
        ├── legal-agent/              # Intelligent legal agent (+ AgentScope demo)
        └── legal-agent-mcp/          # MCP Server for Legal Agent (Cursor/Codex/DSH)
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

### 📡 Launch K8s Multi-Cluster Manager

```bash
cd k8s-cluster-explorer
pip install -r requirements.txt
python backend/main.py
# Visit http://localhost:8003
```

### 🌐 Launch AI Cluster Gateway

```bash
cd ai-cluster-gateway
pip install -r requirements.txt
python backend/main.py
# Visit http://localhost:8004
```

### 🏭 Launch Git → GPU AI Factory

```bash
cd git-to-gpu
pip install -r requirements.txt
python backend/main.py
# Visit http://localhost:8005
```

### 🚀 Bootstrap AI/ML Factory (Kubeflow + KServe)

```bash
cd ai-ml-factory
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q tests/
python console/main.py
# Visit http://localhost:8006
# Pipeline editor tab → edit specs → validate → compile KFP IR
# CLI: python -m pipelines.compiler fraud-default
# Cluster deploy: see ai-ml-factory/docs/deploy.md · modules: docs/MODULES.md
```

### 🔌 Local demo ports (Cloud-Native stack)

| Port | Project | What it is |
|------|---------|------------|
| **8003** | [k8s-cluster-explorer](./k8s-cluster-explorer/) | OCM Hub–Spoke multi-cluster manager |
| **8004** | [ai-cluster-gateway](./ai-cluster-gateway/) | OpenAI-compatible gateway on the same OCM Hub |
| **8005** | [git-to-gpu](./git-to-gpu/) | Narrative Git→GPU demo console |
| **8006** | [ai-ml-factory](./ai-ml-factory/) | Production scaffold console + editable Pipeline editor |

### ⚖️ Launch Legal Agent + MCP Server

```bash
# 1) Start Legal Agent backend
cd legal-agent/backend
uvicorn app.main:app --host 127.0.0.1 --port 8010

# 2) Build & run MCP Server (stdio; usually spawned by Cursor/Codex)
cd ../../legal-agent-mcp
npm install && npm run build
# Configure in ~/.cursor/mcp.json — see legal-agent-mcp/README.md
```

---

## 📖 Detailed Documentation

### AI Infra

| Project | Documentation |
|---------|---------------|
| **AIGateway** | [AIGateway/README.md](./AIGateway/README.md) |
| **AI Cluster Gateway** | [ai-cluster-gateway/README.md](./ai-cluster-gateway/README.md) |
| **DevGuard** | [DevGuard/README.md](./DevGuard/README.md) |
| **K8s DevOps** | [k8sdevops/README.md](./k8sdevops/README.md) |
| **K8s Multi-Cluster Manager** | [k8s-cluster-explorer/README.md](./k8s-cluster-explorer/README.md) |
| **Git → GPU AI Factory** | [git-to-gpu/README.md](./git-to-gpu/README.md) |
| **AI/ML Factory (Kubeflow + KServe)** | [ai-ml-factory/README.md](./ai-ml-factory/README.md) · [模块对照](./ai-ml-factory/docs/MODULES.md) · [部署](./ai-ml-factory/docs/deploy.md) |
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
| **Legal Agent** | [legal-agent/README.md](./legal-agent/README.md) · [AgentScope 示例](./legal-agent/agentscope/) |
| **Legal Agent MCP** | [legal-agent-mcp/README.md](./legal-agent-mcp/README.md) · [架构文档](./legal-agent-mcp/docs/architecture.md) · [PPT](./legal-agent-mcp/docs/architecture.pptx) |
| **AgentScope** | [agentscope/](./agentscope/) |
| **BiSheng** | [bisheng/](./bisheng/) · [README_CN](./bisheng/README_CN.md) |
| **RecruitOS + HR Agent** | [recruit-agent/README.md](./recruit-agent/README.md) · [Harness 插件说明](./recruit-agent/docs/deepseek-harness-plugin.md) |
| **DeepSeek Harness** | [deepseek-harness-master/](./deepseek-harness-master/) |
| **OpenAI Codex** | [codex/](./codex/) · [架构分析](./codex/docs/architecture-analysis/) |
| **JIRA System** | [jira-system/](./jira-system/) |

---

## 🛠️ Technology Stack Overview

### Core Technologies
- **Programming Languages**: Python 3.11+, TypeScript, JavaScript, Go
- **Web Frameworks**: FastAPI, Flask, Vue 3, React, Express, Element Plus, Ant Design
- **Databases**: PostgreSQL, MongoDB, SQLite, Redis, Prisma
- **ML/DL Frameworks**: PyTorch, TensorFlow, LangChain, Transformers
- **Containerization & DevOps**: Docker, Kubernetes, OCM (Open Cluster Management), Argo CD, Argo Rollouts, Tekton, Gatekeeper, Kustomize
- **Development Tools**: Git, VS Code, JupyterLab

### AI-Related Technologies
- **Vector Databases**: ChromaDB, FAISS
- **Agent Frameworks**: LangChain, OpenClaw, OpenAI Codex, DeepSeek Harness (Cordis)
- **Agent Protocols**: Model Context Protocol (MCP) — stdio / tools/list · tools/call
- **AI Safety & Guardrails**: Presidio, Lakera, LlamaGuard, Bedrock, policy-as-code
- **Model Training & Serving**: Kubeflow Pipelines v2, KServe, Triton, vLLM, XGBoost, MLflow, MinIO/S3
- **Model Deployment / Gateways**: LiteLLM, Ollama, OpenAI-compatible cluster gateway
- **OCR Engines**: Tesseract, PaddleOCR, EasyOCR, OvisOCR
- **Data Processing**: Pandas, NumPy, Dask

---

## 🌟 Use Cases

### 👨‍💼 Enterprise Applications
- Customer service automation
- Document processing and analysis (OCR, contract review)
- Knowledge management and legal research
- Legal Agent via MCP in Cursor / Codex / DeepSeek Harness
- Recruitment management and HR AI assistance (including Harness headless plugin)
- Workflow automation
- Issue tracking and management
- GPU resource allocation
- HPC job scheduling
- AI gateway with guardrails for financial compliance
- Multi-cluster OCM Hub–Spoke control and inference routing
- Git→GPU ML platforms (editable Kubeflow pipelines → versioned artifacts → KServe → NVIDIA GPU)

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

- **Total Projects**: 28
- **Categories**: AI Infra (13), AI Agent (15)
- **Language Support**: Python, TypeScript, JavaScript, Go, Rust (Codex)
- **Total Lines of Code**: 100,000+
- **Open Source Licenses**: MIT, AGPL-3.0
- **Highlights**: Legal Agent MCP + AgentScope demo, BiSheng platform, DeepSeek Harness + Recruit Agent plugin, OpenAI Codex architecture, AI/ML Factory (KFP → KServe → GPU), ClawManager, OpenAkita, AIGateway (6-layer guardrails), OCM Hub–Spoke explorer + cluster gateway

---

<div align="center">

  **[⬆ Back to Top](#erics-ai-project-collection)**

  <br>

  Made with ❤️ by Eric

  Last updated: 2026-08-31

</div>