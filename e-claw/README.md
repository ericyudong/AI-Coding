# E-Claw: Enterprise AI Agent Platform

## Project Overview

**E-Claw** is an enterprise-grade AI agent runtime platform based on OpenClaw architecture. It features a three-layer fusion architecture supporting multi-tenant isolation, checkpoint-based resumption, RAG retrieval, and other core capabilities.

## Key Features

### 1. Multi-Tenant Isolation
- Tenant creation, disabling, and deletion
- Tenant resource quota allocation
- Complete data isolation across tenants

### 2. Instance Management
- Support for multiple instance types: OpenClaw, Ubuntu, WebTop, Debian, CentOS, and custom images
- Kubernetes-based orchestration for scaling and management
- GPU-accelerated instances for AI workloads
- Flexible CPU, memory, and disk configurations
- Persistent storage with PVC support

### 3. Task Management
- Multi-modal task submission (documents, images, audio, video)
- Task priority scheduling
- Real-time task status tracking
- Progress monitoring with WebSocket updates

### 4. Knowledge Base (RAG)
- Personal knowledge bases
- Department shared knowledge bases
- RAG retrieval powered by ChromaDB
- Document ingestion (PDF, DOCX, images, Excel)
- Vector similarity search

### 5. User & Permission Management
- RBAC (Role-Based Access Control) model
- Roles: Employee, Department Admin, Super Admin
- Department-level and resource-level permissions
- JWT-based authentication

### 6. Resource Quotas
- Token usage tracking
- Department quota allocation
- Personal quota management
- Usage statistics and reporting

### 7. Audit Logging
- Full operation audit trail
- Multi-dimensional query filters
- Log export functionality

## Technology Stack

### Backend
- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Database**: PostgreSQL + Redis
- **AI Engine**: LangChain + Local LLMs
- **Vector Database**: ChromaDB
- **Communication**: WebSocket + RESTful API
- **Kubernetes**: Python Kubernetes client

### Frontend
- **Framework**: Vue 3 + TypeScript
- **UI Library**: Element Plus
- **State Management**: Pinia
- **Routing**: Vue Router 4
- **Charts**: ECharts
- **HTTP Client**: Axios

### Deployment
- **Containerization**: Docker
- **Orchestration**: Kubernetes
- **Process Manager**: Uvicorn

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Layer                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │ Web UI  │  │ Mobile  │  │ Desktop │  │  API    │       │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │
└───────┼────────────┼────────────┼────────────┼─────────────┘
        └────────────┴────────────┴────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Adapter Layer (E-Claw)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ WebSocket    │  │ Checkpoint    │  │ Knowledge    │     │
│  │ Gateway      │  │ Manager       │  │ Base Manager │     │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘     │
└─────────┼─────────────────┼────────────────────────────────┘
          │                 │
          ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│                Manager Layer (E-Claw)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Multi-Tenant │  │ Resource      │  │ Permissions  │     │
│  │ Manager      │  │ Scheduler     │  │ (RBAC)       │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Audit Logs    │  │ Token         │  │ Alerting     │     │
│  │ Service       │  │ Metering     │  │ Manager      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────┬──────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                Execution Layer (E-Claw)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Task Executor│  │ RAG Retrieval │  │ Tool         │     │
│  │              │  │ Engine        │  │ Invoker      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
e-claw/
├── backend/                    # Backend service
│   ├── app/
│   │   ├── api/               # API routes
│   │   │   ├── v1/
│   │   │   │   ├── auth.py    # Authentication
│   │   │   │   ├── users.py   # User management
│   │   │   │   ├── tasks.py   # Task management
│   │   │   │   ├── knowledge.py # Knowledge base
│   │   │   │   ├── instances.py # Instance management
│   │   │   │   ├── gateway.py # AI Gateway
│   │   │   │   └── admin.py    # Admin endpoints
│   │   │   └── websocket.py   # WebSocket endpoints
│   │   ├── core/              # Core modules
│   │   │   ├── config.py      # Configuration
│   │   │   ├── security.py    # Security & JWT
│   │   │   ├── database.py    # Database
│   │   │   └── mcp.py         # MCP protocol
│   │   ├── models/            # Data models
│   │   ├── services/          # Business services
│   │   │   ├── tenant_service.py   # Multi-tenant service
│   │   │   ├── task_service.py     # Task service
│   │   │   ├── knowledge_service.py # Knowledge base service
│   │   │   ├── k8s_service.py      # Kubernetes service
│   │   │   ├── instance_service.py # Instance service
│   │   │   ├── llm_gateway_service.py # LLM gateway
│   │   │   └── audit_service.py    # Audit service
│   │   └── main.py            # Application entry
│   ├── requirements.txt
│   └── run.bat
├── frontend/                   # Frontend application
│   ├── src/
│   │   ├── api/              # API calls
│   │   ├── components/       # Common components
│   │   ├── views/            # Page views
│   │   ├── stores/           # State management (Pinia)
│   │   ├── router/           # Router configuration
│   │   └── utils/            # Utility functions
│   ├── index.html
│   └── package.json
├── test/                       # Test scripts
└── PROJECT_STRUCTURE.md
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+
- Kubernetes cluster (for production)

### Backend Setup

1. **Navigate to backend directory**
   ```bash
   cd backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # or
   source venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   Create a `.env` file with your database and Redis settings:
   ```env
   DATABASE_URL=postgresql+asyncpg://user:password@localhost/eclaw
   REDIS_URL=redis://localhost:6379/0
   SECRET_KEY=your-secret-key
   ```

5. **Initialize database**
   ```bash
   python backend/setup_db.py
   ```

6. **Run backend server**
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   Or use the provided batch file:
   ```bash
   start_backend.bat
   ```

### Frontend Setup

1. **Navigate to frontend directory**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Start development server**
   ```bash
   npm run dev
   ```

4. **Build for production**
   ```bash
   npm run build
   ```

## API Documentation

### Authentication
- `POST /api/login` - User login
- `POST /api/v1/auth/logout` - User logout
- `GET /api/v1/auth/me` - Get current user info

### Instance Management
- `GET /api/direct/instances` - List instances
- `POST /api/direct/instances` - Create instance
- `GET /api/image-templates` - Get available image templates
- `DELETE /api/v1/instances/{id}` - Delete instance

### Task Management
- `GET /api/direct/tasks` - List tasks
- `POST /api/v1/tasks` - Submit task
- `GET /api/v1/tasks/{id}` - Get task details
- `DELETE /api/v1/tasks/{id}` - Cancel task

### Knowledge Base
- `GET /api/direct/knowledge` - List knowledge bases
- `POST /api/v1/knowledge` - Upload document
- `DELETE /api/v1/knowledge/{id}` - Delete document
- `GET /api/v1/knowledge/search` - Search knowledge base

### Admin
- `GET /api/direct/users` - List users
- `POST /api/direct/tenants` - Create tenant
- `GET /api/v1/admin/tenants` - List tenants
- `GET /api/v1/admin/audit` - Query audit logs

### System
- `GET /health` - Health check
- `GET /api/v1/system/status` - System status
- `GET /api/v1/system/monitor` - System monitoring
- `GET /api/v1/system/logs` - System logs

### AI Gateway
- `POST /api/v1/gateway/query` - LLM query interface
- `POST /api/v1/gateway/rag` - RAG query interface

## Instance Types

E-Claw supports the following instance templates:

1. **OpenClaw**: Full-featured AI workspace with LLM gateway
   - Default port: 18789
   - Includes AI task processing capabilities

2. **Linux (Ubuntu)**: General-purpose Linux workspace
   - Image: ubuntu:22.04
   - Default port: 22 (SSH)

3. **WebTop**: Web-based Linux desktop environment
   - Image: lscr.io/linuxserver/webtop:latest
   - Default port: 3000
   - Provides graphical interface

## Configuration

### Environment Variables

Key environment variables for the backend:

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `SECRET_KEY`: JWT signing key
- `KUBECONFIG`: Path to Kubernetes config (optional)
- `CORS_ORIGINS`: Allowed CORS origins

### System Requirements

### Minimum Configuration
- CPU: 4 cores
- Memory: 16GB
- Storage: 200GB SSD

### Recommended Configuration
- CPU: 8 cores
- Memory: 32GB
- Storage: 500GB SSD
- GPU: NVIDIA GPU with CUDA support (for AI workloads)

## Development

### Testing
Test scripts are available in the `test/` directory:
- `test_login.py` - Test authentication
- `test_create_instance.py` - Test instance creation
- `test_status.py` - Check system status
- `test_k8s_connection.py` - Test Kubernetes connectivity

### Code Style
- Backend: Follow PEP 8 guidelines
- Frontend: Use TypeScript strict mode
- Use meaningful variable and function names

## Production Deployment

### Docker Deployment

```bash
# Build backend image
docker build -t e-claw-backend:latest -f backend/Dockerfile .

# Build frontend image
docker build -t e-claw-frontend:latest -f frontend/Dockerfile .

# Run with docker-compose
docker-compose up -d
```

### Kubernetes Deployment

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/
```

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Check PostgreSQL is running
   - Verify DATABASE_URL in .env file

2. **Instance Creation Fails**
   - Verify Kubernetes cluster connectivity
   - Check if namespace exists
   - Ensure sufficient cluster resources

3. **RAG Search Returns Empty**
   - Verify ChromaDB is accessible
   - Check if documents are indexed
   - Review embedding model configuration

## License

This project is proprietary software. All rights reserved.

## Support

For issues, questions, or contributions, please contact the development team.
