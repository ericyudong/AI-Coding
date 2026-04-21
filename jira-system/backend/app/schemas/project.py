"""Project and Issue schemas"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


# Project schemas
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    key: str
    icon: Optional[str] = None
    is_public: bool = False


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    is_public: Optional[bool] = None


class ProjectResponse(ProjectBase):
    id: str
    owner_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ProjectWithMembers(ProjectResponse):
    members: List["ProjectMemberWithUser"] = []


# Issue schemas
class IssueBase(BaseModel):
    title: str
    description: Optional[str] = None
    issue_type: str = "task"
    priority: str = "medium"
    labels: Optional[str] = None
    components: Optional[str] = None


class IssueCreate(IssueBase):
    assignee_id: Optional[str] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    estimate: Optional[float] = None


class IssueUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    issue_type: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_id: Optional[str] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    estimate: Optional[float] = None
    time_spent: Optional[float] = None
    labels: Optional[str] = None
    components: Optional[str] = None
    resolution: Optional[str] = None


class IssueResponse(IssueBase):
    id: str
    key: str
    status: str
    resolution: Optional[str] = None
    project_id: str
    assignee_id: Optional[str] = None
    reporter_id: str
    sprint_id: Optional[str] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    estimate: Optional[float] = None
    time_spent: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class IssueWithDetails(IssueResponse):
    assignee: Optional["UserResponse"] = None
    reporter: "UserResponse"
    project: "ProjectResponse"
    comments_count: int = 0
    attachments_count: int = 0


# Sprint schemas
class SprintBase(BaseModel):
    name: str
    goal: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class SprintCreate(SprintBase):
    project_id: str


class SprintUpdate(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class SprintResponse(SprintBase):
    id: str
    project_id: str
    status: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Label schemas
class LabelBase(BaseModel):
    name: str
    color: str = "#0079bf"
    description: Optional[str] = None


class LabelCreate(LabelBase):
    pass


class LabelResponse(LabelBase):
    id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Update forward references
from .user import UserResponse, ProjectMemberWithUser
IssueWithDetails.model_rebuild()
ProjectWithMembers.model_rebuild()