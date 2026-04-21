"""Project and Issue models"""
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from .user import User, ProjectMember
    from .comment import Comment


class Project(SQLModel, table=True):
    """Project model"""
    __tablename__ = "projects"
    
    id: Optional[str] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = None
    key: str = Field(unique=True, index=True)  # e.g., "PROJ", "JIRA"
    icon: Optional[str] = None
    owner_id: Optional[str] = Field(foreign_key="users.id")
    is_public: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    members: list["ProjectMember"] = Relationship(back_populates="project", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    issues: list["Issue"] = Relationship(back_populates="project", sa_relationship_kwargs={"cascade": "all, delete-orphan"})


class Issue(SQLModel, table=True):
    """Issue/Ticket model"""
    __tablename__ = "issues"
    
    id: Optional[str] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)  # e.g., "PROJ-1", "PROJ-2"
    title: str = Field(index=True)
    description: Optional[str] = None
    issue_type: str = Field(default="task")  # task, bug, story, epic
    status: str = Field(default="todo")  # todo, in_progress, in_review, done
    priority: str = Field(default="medium")  # low, medium, high, critical
    resolution: Optional[str] = None  # fixed, won't fix, duplicate, etc.
    
    # Project & Assignee
    project_id: str = Field(foreign_key="projects.id")
    assignee_id: Optional[str] = Field(foreign_key="users.id")
    reporter_id: str = Field(foreign_key="users.id")
    
    # Dates
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    estimate: Optional[float] = None  # Story points / time estimate
    time_spent: Optional[float] = None  # Time spent in hours
    
    # Labels & Components
    labels: Optional[str] = None  # Comma-separated labels
    components: Optional[str] = None  # Comma-separated components
    
    # Sprint
    sprint_id: Optional[str] = Field(foreign_key="sprints.id")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Relationships
    project: "Project" = Relationship(back_populates="issues")
    assignee: Optional["User"] = Relationship(back_populates="issues", sa_relationship_kwargs={"foreign_keys": "[Issue.assignee_id]"})
    comments: list["Comment"] = Relationship(back_populates="issue", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    attachments: list["Attachment"] = Relationship(back_populates="issue", sa_relationship_kwargs={"cascade": "all, delete-orphan"})


class Sprint(SQLModel, table=True):
    """Sprint model for agile"""
    __tablename__ = "sprints"
    
    id: Optional[str] = Field(default=None, primary_key=True)
    name: str
    project_id: str = Field(foreign_key="projects.id")
    goal: Optional[str] = None
    status: str = Field(default="planned")  # planned, active, completed
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Attachment(SQLModel, table=True):
    """Attachment model"""
    __tablename__ = "attachments"
    
    id: Optional[str] = Field(default=None, primary_key=True)
    filename: str
    file_url: str
    file_size: int
    mime_type: Optional[str] = None
    issue_id: str = Field(foreign_key="issues.id")
    uploaded_by: str = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    issue: "Issue" = Relationship(back_populates="attachments")


class Label(SQLModel, table=True):
    """Label model"""
    __tablename__ = "labels"
    
    id: Optional[str] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    color: str = Field(default="#0079bf")  # Default blue
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)