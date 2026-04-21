"""Project API routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from typing import List
import uuid

from ...core.database import get_session
from ...core.security import get_current_user_id
from ...models.user import User, ProjectMember
from ...models.project import Project
from ...schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectWithMembers
)

router = APIRouter(prefix="/projects", tags=["projects"])


def get_project_with_permission(project_id: str, user_id: str, session: Session) -> Project:
    """Get project and check permissions"""
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if user is member or owner
    member = session.exec(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id
        )
    ).first()
    
    if not project.is_public and project.owner_id != user_id and not member:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return project


@router.get("", response_model=List[ProjectResponse])
def list_projects(
    skip: int = 0,
    limit: int = 20,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session)
):
    """List all projects for current user"""
    # Get projects where user is member or owner, or public
    statement = select(Project).where(
        (Project.owner_id == user_id) | 
        (Project.id.in_(
            select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)
        )) |
        (Project.is_public == True)
    ).offset(skip).limit(limit)
    
    projects = session.exec(statement).all()
    return projects


@router.post("", response_model=ProjectResponse)
def create_project(
    project_data: ProjectCreate,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session)
):
    """Create a new project"""
    # Check if project key exists
    existing = session.exec(
        select(Project).where(Project.key == project_data.key)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project key already exists"
        )
    
    project = Project(
        id=str(uuid.uuid4()),
        name=project_data.name,
        description=project_data.description,
        key=project_data.key,
        icon=project_data.icon,
        is_public=project_data.is_public,
        owner_id=user_id,
    )
    session.add(project)
    
    # Add owner as admin member
    member = ProjectMember(
        project_id=project.id,
        user_id=user_id,
        role="admin"
    )
    session.add(member)
    
    session.commit()
    session.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectWithMembers)
def get_project(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session)
):
    """Get project details"""
    project = get_project_with_permission(project_id, user_id, session)
    
    # Get members
    members = session.exec(
        select(ProjectMember).where(ProjectMember.project_id == project_id)
    ).all()
    
    # Get user details for each member
    member_list = []
    for m in members:
        user = session.get(User, m.user_id)
        if user:
            member_list.append({
                "id": m.id,
                "user_id": m.user_id,
                "role": m.role,
                "created_at": m.created_at,
                "user": user
            })
    
    return {"members": member_list, **project.__dict__}


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session)
):
    """Update project"""
    project = get_project_with_permission(project_id, user_id, session)
    
    # Check admin permission
    member = session.exec(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id
        )
    ).first()
    
    if project.owner_id != user_id and (not member or member.role != "admin"):
        raise HTTPException(status_code=403, detail="Admin permission required")
    
    # Update fields
    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session)
):
    """Delete project"""
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only owner can delete project")
    
    session.delete(project)
    session.commit()
    return {"message": "Project deleted"}


@router.post("/{project_id}/members", response_model=dict)
def add_member(
    project_id: str,
    user_id: str,
    role: str = "member",
    current_user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session)
):
    """Add member to project"""
    project = get_project_with_permission(project_id, current_user_id, session)
    
    # Check admin permission
    member = session.exec(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user_id
        )
    ).first()
    
    if project.owner_id != current_user_id and (not member or member.role != "admin"):
        raise HTTPException(status_code=403, detail="Admin permission required")
    
    # Check if user exists
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already member
    existing = session.exec(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id
        )
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="User is already a member")
    
    new_member = ProjectMember(
        project_id=project_id,
        user_id=user_id,
        role=role
    )
    session.add(new_member)
    session.commit()
    
    return {"message": "Member added"}


@router.delete("/{project_id}/members/{member_user_id}")
def remove_member(
    project_id: str,
    member_user_id: str,
    current_user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session)
):
    """Remove member from project"""
    project = get_project_with_permission(project_id, current_user_id, session)
    
    # Check admin permission
    member = session.exec(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user_id
        )
    ).first()
    
    if project.owner_id != current_user_id and (not member or member.role != "admin"):
        raise HTTPException(status_code=403, detail="Admin permission required")
    
    # Can't remove owner
    if member_user_id == project.owner_id:
        raise HTTPException(status_code=400, detail="Cannot remove project owner")
    
    member = session.exec(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == member_user_id
        )
    ).first()
    
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    session.delete(member)
    session.commit()
    
    return {"message": "Member removed"}