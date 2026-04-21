"""Data models for the AI Q&A System."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, Text, Integer, Float, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


# SQLAlchemy Models
class ConversationDB(Base):
    """Database model for conversations."""
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True)
    session_id = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    title = Column(String, default="New Conversation")


class MessageDB(Base):
    """Database model for messages."""
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True)
    conversation_id = Column(String, index=True)
    role = Column(String)  # user, assistant, system
    content = Column(Text)
    msg_metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)


class DocumentDB(Base):
    """Database model for RAG documents."""
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True)
    filename = Column(String)
    content = Column(Text)
    embedding = Column(JSON)  # Store as JSON for simplicity
    doc_metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)


# Pydantic Models for API
class Message(BaseModel):
    """Message model for API."""
    id: str
    role: str
    content: str
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Conversation(BaseModel):
    """Conversation model for API."""
    id: str
    session_id: str
    title: str
    messages: List[Message] = []
    created_at: datetime
    updated_at: datetime


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    session_id: Optional[str] = None
    use_rag: bool = False
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=4096)


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    session_id: str
    message_id: str
    sources: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}


class DocumentUploadResponse(BaseModel):
    """Document upload response."""
    document_id: str
    filename: str
    status: str
    chunks_added: int


class ConversationListResponse(BaseModel):
    """Conversation list response."""
    conversations: List[Dict[str, Any]]
    total: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    llm_provider: str
    rag_enabled: bool