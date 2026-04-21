"""Comment model"""
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from .user import User
    from .project import Issue


class Comment(SQLModel, table=True):
    """Comment model"""
    __tablename__ = "comments"
    
    id: Optional[str] = Field(default=None, primary_key=True)
    content: str
    issue_id: str = Field(foreign_key="issues.id")
    author_id: str = Field(foreign_key="users.id")
    parent_id: Optional[str] = Field(foreign_key="comments.id")  # For nested comments
    is_edited: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    issue: "Issue" = Relationship(back_populates="comments")
    author: "User" = Relationship(back_populates="comments")
    parent: Optional["Comment"] = Relationship(sa_relationship_kwargs={"remote_side": "[Comment.id]"})
    replies: list["Comment"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Comment.parent_id]"})


class IssueHistory(SQLModel, table=True):
    """Issue change history"""
    __tablename__ = "issue_history"
    
    id: Optional[str] = Field(default=None, primary_key=True)
    issue_id: str = Field(foreign_key="issues.id")
    user_id: str = Field(foreign_key="users.id")
    field_name: str  # e.g., "status", "assignee", "priority"
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)