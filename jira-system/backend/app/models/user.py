"""User models"""
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, String, DateTime, Boolean


class User(SQLModel, table=True):
    """User model"""
    __tablename__ = "users"
    
    id: Optional[str] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    username: str = Field(unique=True, index=True)
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    hashed_password: Optional[str] = None
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    oauth_provider: Optional[str] = None  # github, google
    oauth_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    issues: list["Issue"] = Relationship(back_populates="assignee", sa_relationship_kwargs={"foreign_keys": "[Issue.assignee_id]"})
    projects: list["ProjectMember"] = Relationship(back_populates="user")
    comments: list["Comment"] = Relationship(back_populates="author")


class ProjectMember(SQLModel, table=True):
    """Project member association table"""
    __tablename__ = "project_members"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: str = Field(foreign_key="projects.id")
    user_id: str = Field(foreign_key="users.id")
    role: str = Field(default="member")  # admin, member, viewer
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    project: "Project" = Relationship(back_populates="members")
    user: "User" = Relationship(back_populates="projects")