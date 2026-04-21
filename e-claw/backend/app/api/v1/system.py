"""
E-Claw 系统配置接口
服务配置、系统参数管理等
"""
import os
import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import get_current_user
from app.models import User, UserRole

router = APIRouter()

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "services.json")

# 确保配置目录存在
os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)


# ============== 响应模型 ==============

class ServiceConfig(BaseModel):
    """服务配置"""
    id: str
    name: str
    service_type: str
    enabled: bool = True
    config: Dict[str, Any]
    description: str = ""
    created_at: str
    updated_at: str


class ServiceConfigUpdate(BaseModel):
    """服务配置更新"""
    name: Optional[str] = None
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    description: Optional[str] = None


class ServiceConfigCreate(BaseModel):
    """服务配置创建"""
    name: str
    service_type: str
    enabled: bool = True
    config: Dict[str, Any]
    description: str = ""


# ============== 配置存储 ==============

def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"services": []}
    return {"services": []}


def save_config(config: Dict[str, Any]) -> None:
    """保存配置文件"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ============== 系统配置接口 ==============

@router.get("/config", response_model=Dict[str, Any])
async def get_system_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取系统配置"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin or ops only"
        )
    return load_config()


@router.get("/config/services", response_model=List[ServiceConfig])
async def list_services(
    service_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取服务配置列表"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS, UserRole.DEPT_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or ops only"
        )
    
    config = load_config()
    services = config.get("services", [])
    
    if service_type:
        services = [s for s in services if s.get("service_type") == service_type]
    
    return services


@router.post("/config/services", response_model=ServiceConfig)
async def create_service(
    request: ServiceConfigCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """创建服务配置"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin or ops only"
        )
    
    import uuid
    from datetime import datetime
    
    config = load_config()
    
    # 检查服务名是否已存在
    for s in config.get("services", []):
        if s.get("name") == request.name:
            raise HTTPException(status_code=400, detail="Service name already exists")
    
    service_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    new_service = {
        "id": service_id,
        "name": request.name,
        "service_type": request.service_type,
        "enabled": request.enabled,
        "config": request.config,
        "description": request.description,
        "created_at": now,
        "updated_at": now
    }
    
    if "services" not in config:
        config["services"] = []
    config["services"].append(new_service)
    save_config(config)
    
    return new_service


@router.get("/config/services/{service_id}", response_model=ServiceConfig)
async def get_service(
    service_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取服务配置详情"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS, UserRole.DEPT_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or ops only"
        )
    
    config = load_config()
    services = config.get("services", [])
    
    for s in services:
        if s.get("id") == service_id:
            return s
    
    raise HTTPException(status_code=404, detail="Service not found")


@router.put("/config/services/{service_id}", response_model=ServiceConfig)
async def update_service(
    service_id: str,
    request: ServiceConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """更新服务配置"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin or ops only"
        )
    
    from datetime import datetime
    
    config = load_config()
    services = config.get("services", [])
    
    for i, s in enumerate(services):
        if s.get("id") == service_id:
            if request.name is not None:
                services[i]["name"] = request.name
            if request.enabled is not None:
                services[i]["enabled"] = request.enabled
            if request.config is not None:
                services[i]["config"] = request.config
            if request.description is not None:
                services[i]["description"] = request.description
            
            services[i]["updated_at"] = datetime.utcnow().isoformat()
            config["services"] = services
            save_config(config)
            return services[i]
    
    raise HTTPException(status_code=404, detail="Service not found")


@router.delete("/config/services/{service_id}")
async def delete_service(
    service_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """删除服务配置"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin only"
        )
    
    config = load_config()
    services = config.get("services", [])
    
    for i, s in enumerate(services):
        if s.get("id") == service_id:
            services.pop(i)
            config["services"] = services
            save_config(config)
            return {"message": "Service deleted successfully"}
    
    raise HTTPException(status_code=404, detail="Service not found")


# ============== LLM配置接口 ==============

class LLMConfig(BaseModel):
    """LLM配置"""
    provider: str
    model: str
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 2000


class LLMConfigResponse(BaseModel):
    """LLM配置响应"""
    provider: str
    model: str
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 2000
    # 不返回api_key


LLM_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "llm.json")


def load_llm_config() -> Dict[str, Any]:
    """加载LLM配置"""
    if os.path.exists(LLM_CONFIG_FILE):
        try:
            with open(LLM_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"provider": "openai", "model": "gpt-4", "api_key": "", "base_url": "", "temperature": 0.7, "max_tokens": 2000}
    return {"provider": "openai", "model": "gpt-4", "api_key": "", "base_url": "", "temperature": 0.7, "max_tokens": 2000}


def save_llm_config(config: Dict[str, Any]) -> None:
    """保存LLM配置"""
    os.makedirs(os.path.dirname(LLM_CONFIG_FILE), exist_ok=True)
    with open(LLM_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


@router.get("/config/llm", response_model=LLMConfigResponse)
async def get_llm_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取LLM配置"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin or ops only"
        )
    return load_llm_config()


@router.put("/config/llm", response_model=LLMConfigResponse)
async def update_llm_config(
    request: LLMConfig,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """更新LLM配置"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin or ops only"
        )
    
    config = {
        "provider": request.provider,
        "model": request.model,
        "api_key": request.api_key,
        "base_url": request.base_url,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens
    }
    save_llm_config(config)
    
    # 返回不包含api_key的配置
    return {
        "provider": request.provider,
        "model": request.model,
        "base_url": request.base_url,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens
    }


# ============== RAG配置接口 ==============

class RAGConfig(BaseModel):
    """RAG配置"""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k: int = 5
    vector_store_type: str = "faiss"
    embedding_model: str = "sentence-transformers"
    embedding_dim: int = 768


RAG_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "rag.json")


def load_rag_config() -> Dict[str, Any]:
    """加载RAG配置"""
    if os.path.exists(RAG_CONFIG_FILE):
        try:
            with open(RAG_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"chunk_size": 1000, "chunk_overlap": 200, "top_k": 5, "vector_store_type": "faiss", "embedding_model": "sentence-transformers", "embedding_dim": 768}
    return {"chunk_size": 1000, "chunk_overlap": 200, "top_k": 5, "vector_store_type": "faiss", "embedding_model": "sentence-transformers", "embedding_dim": 768}


def save_rag_config(config: Dict[str, Any]) -> None:
    """保存RAG配置"""
    os.makedirs(os.path.dirname(RAG_CONFIG_FILE), exist_ok=True)
    with open(RAG_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


@router.get("/config/rag", response_model=RAGConfig)
async def get_rag_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取RAG配置"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin or ops only"
        )
    return load_rag_config()


@router.put("/config/rag", response_model=RAGConfig)
async def update_rag_config(
    request: RAGConfig,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """更新RAG配置"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin or ops only"
        )
    
    config = {
        "chunk_size": request.chunk_size,
        "chunk_overlap": request.chunk_overlap,
        "top_k": request.top_k,
        "vector_store_type": request.vector_store_type,
        "embedding_model": request.embedding_model,
        "embedding_dim": request.embedding_dim
    }
    save_rag_config(config)
    return config


# ============== MCP服务配置接口 ==============

class MCPConfig(BaseModel):
    """MCP服务配置"""
    enabled: bool = True
    servers: List[Dict[str, Any]] = []


MCP_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "mcp.json")


def load_mcp_config() -> Dict[str, Any]:
    """加载MCP配置"""
    if os.path.exists(MCP_CONFIG_FILE):
        try:
            with open(MCP_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"enabled": True, "servers": []}
    return {"enabled": True, "servers": []}


def save_mcp_config(config: Dict[str, Any]) -> None:
    """保存MCP配置"""
    os.makedirs(os.path.dirname(MCP_CONFIG_FILE), exist_ok=True)
    with open(MCP_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


@router.get("/config/mcp", response_model=MCPConfig)
async def get_mcp_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取MCP配置"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin or ops only"
        )
    return load_mcp_config()


@router.put("/config/mcp", response_model=MCPConfig)
async def update_mcp_config(
    request: MCPConfig,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """更新MCP配置"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.OPS]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin or ops only"
        )
    
    config = {
        "enabled": request.enabled,
        "servers": request.servers
    }
    save_mcp_config(config)
    return config


@router.post("/config/mcp/servers")
async def add_mcp_server(
    server: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """添加MCP服务器"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin only"
        )
    
    import uuid
    config = load_mcp_config()
    
    if "servers" not in config:
        config["servers"] = []
    
    server["id"] = str(uuid.uuid4())
    config["servers"].append(server)
    save_mcp_config(config)
    
    return {"message": "MCP server added", "server": server}


@router.delete("/config/mcp/servers/{server_id}")
async def delete_mcp_server(
    server_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """删除MCP服务器"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin only"
        )
    
    config = load_mcp_config()
    servers = config.get("servers", [])
    
    for i, s in enumerate(servers):
        if s.get("id") == server_id:
            servers.pop(i)
            config["servers"] = servers
            save_mcp_config(config)
            return {"message": "MCP server deleted"}
    
    raise HTTPException(status_code=404, detail="MCP server not found")