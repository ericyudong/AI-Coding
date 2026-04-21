"""
E-Claw 配置管理
"""
import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用基础配置
    APP_NAME: str = "E-Claw"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    HOST: str = "0.0.0.0"
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # CORS配置
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    
    # 数据库配置
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://eclaw:eclaw@localhost:5432/eclaw"
    )
    
    # Redis配置
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # JWT配置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "e-claw-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天
    
    # 多租户配置
    DEFAULT_TENANT_QUOTA: int = 1000000  # 默认Token配额
    MAX_TENANTS: int = 100  # 最大租户数
    
    # 任务配置
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_FILE_TYPES: List[str] = [
        "doc", "docx", "pdf", "ppt", "pptx", "xls", "xlsx",
        "jpg", "jpeg", "png", "gif", "mp3", "mp4", "wav", "txt"
    ]
    MAX_TASK_INPUT_LENGTH: int = 4000
    
    # 断点续跑配置
    CHECKPOINT_INTERVAL: int = 1  # 秒
    CHECKPOINT_DIR: str = "/var/lib/e-claw/checkpoints"
    
    # RAG配置
    RAG_CHUNK_SIZE: int = 1000
    RAG_CHUNK_OVERLAP: int = 200
    RAG_TOP_K: int = 5
    VECTOR_DB_PATH: str = "/var/lib/e-claw/vector_db"
    
    # 知识库配置
    KNOWLEDGE_BASE_DIR: str = "/var/lib/e-claw/knowledge"
    MAX_KNOWLEDGE_SIZE: int = 10 * 1024 * 1024 * 1024  # 10GB
    
    # 审计日志配置
    AUDIT_LOG_RETENTION_DAYS: int = 365
    
    # LLM配置
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")
    
    # MCP配置
    MCP_ENABLED: bool = True
    MCP_SERVERS: List[str] = []
    
    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = "/var/log/e-claw/app.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()