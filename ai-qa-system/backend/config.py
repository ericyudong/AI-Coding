"""Configuration management for the AI Q&A System."""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from loguru import logger


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # LLM Provider
    llm_provider: str = Field(default="openai", description="LLM provider: openai, anthropic, google, minimax")
    
    # OpenAI
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    openai_model: str = Field(default="gpt-4", description="OpenAI model name")
    openai_base_url: str = Field(default="https://api.openai.com/v1", description="OpenAI base URL")
    
    # Anthropic
    anthropic_api_key: str = Field(default="", description="Anthropic API Key")
    anthropic_model: str = Field(default="claude-3-opus-20240229", description="Anthropic model name")
    
    # Google
    google_api_key: str = Field(default="", description="Google API Key")
    google_model: str = Field(default="gemini-pro", description="Google model name")
    
    # MiniMax
    minimax_api_key: str = Field(default="", description="MiniMax API Key")
    minimax_model: str = Field(default="abab5.5-chat", description="MiniMax model name")
    minimax_base_url: str = Field(default="https://api.minimax.chat/v1", description="MiniMax base URL")
    
    # Database
    database_url: str = Field(default="sqlite+aiosqlite:///./qa_system.db", description="Database URL")
    
    # Vector Store
    embedding_model: str = Field(default="Qwen3-Embedding-8B", description="Embedding model")
    embedding_base_url: str = Field(default="http://maas1.ehuidata.com:30067/openai/v1", description="Embedding API base URL")
    embedding_api_key: str = Field(default="", description="Embedding API Key")
    vector_store_type: str = Field(default="faiss", description="Vector store type")
    faiss_index_path: str = Field(default="./faiss_index", description="FAISS index path")
    
    # RAG
    rag_enabled: bool = Field(default=True, description="Enable RAG")
    rag_top_k: int = Field(default=5, description="Number of documents to retrieve")
    rag_chunk_size: int = Field(default=1000, description="Chunk size for text splitting")
    rag_chunk_overlap: int = Field(default=200, description="Chunk overlap")
    
    # Server
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    log_level: str = Field(default="INFO", description="Log level")
    debug: bool = Field(default=True, description="Debug mode")
    
    # Session
    session_expiry_hours: int = Field(default=24, description="Session expiry in hours")
    max_conversation_history: int = Field(default=50, description="Max conversation history")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


# Global settings instance
settings = Settings()


def configure_logging():
    """Configure logging based on settings."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )


import sys
configure_logging()
logger.info("Configuration loaded successfully")