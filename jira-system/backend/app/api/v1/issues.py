"""Issue API routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime
import uuid

from ...core.database import get_session
from ...core.security import get_current_user_id
from ...models.user import User, ProjectMember
from ...models.project import Project, Issue
from ...models.comment import Comment
from ...schemas.project import IssueCreate, IssueUpdate, IssueResponse, IssueWithDetails

router = APIRouter(tags=["issues"])


def get_issue_with_permission(issue_id: str, user_id: str, session: Session) -> Issue:
    """Get issue and check permissions"""
    issue = session.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    project = session.get(Project, issue.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if user is member or owner
    member = session.exec(
        select(ProjectMember).where(
            ProjectMember.project_id == issue.project_id,
            ProjectMember.user_id == user_id
        )
    ).first()
    
    if not project.is_public and project.owner_id != user_id and not member:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return issue


@router.get("/projects/{project_id}/issues", response_model=List[IssueResponse])
def list_issues(
    project_id: str,
    status: Optional[str] = None,
    assignee_id: Optional[str] = None,
    issue_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session)
):
    """List issues for a project"""
    # Check project access
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    member = session.exec(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id
        )
    ).first()
    
    if not project.is_public and project.owner_id != user_id and not member:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Build query
    statement = select(Issue).where(Issue.project_id == project_id)
    
    if status:
        statement = statement.where(Issue.status == status)
    if assignee_id:
        statement = statement.where(Issue.assignee_id == assignee_id)
    if issue_type:
        statement = statement.where(Issue.issue_type == issue_type)
    
    statement = statement.offset(skip).limit(limit).order_by(Issue.created_at.desc())
    
    issues = session.exec(statement).all()
    return issues


@router.post("/projects/{project_id}/issues", response_model=IssueResponse)
def create_issue(
    project_id: str,
    issue_data: IssueCreate,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session)
):
    """Create a new issue"""
    # Check project access
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    member = session.exec(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id
        )
    ).first()
    
    if not project.is_public and project.owner_id != user_id and not member:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Generate issue key
    max_key = session.exec(
        select(func.max(Issue.key)).where(Issue.project_id == project_id)
    ).first()
    
    if max_key:
        last_num = int(max_key.split("-")[-1])
        new_num = last_num + 1
    else:
        new_num = 1
    
    issue_key = f"{project.key}-{new_num}"
    
    issue = Issue(
        id=str(uuid.uuid4()),
        key=issue_key,
        title=issue_data.title,
        description=issue_data.description,
        issue_type=issue_data.issue_type,
        priority=issue_data.priority,
        labels=issue_data.labels,
        components=issue_data.components,
        project_id=project_id,
        assignee_id=issue_data.assignee_id,
        reporter_id=user_id,
        start_date=issue_data.start_date,
        due_date=issue_data.due_date,
        estimate=issue_data.estimate,
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


@router.get("/issues/{issue_id}", response_model=IssueWithDetails)
def get_issue(
    issue_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session)
):
    """Get issue details"""
    issue = get_issue_with_permission(issue_id, user_id, session)
    
    # Get assignee and reporter
    assignee = session.get(User, issue.assignee_id) if issue.assignee_id else None
    reporter = session.get(User, issue.reporter_id)
    project = session.get(Project, issue.project_id)
    
    # Get comments and attachments count
    comments_count = session.exec(
        select(func.count(Comment.id)).where(Comment.issue_id == issue_id)
    ).first() or 0
    
    return IssueWithDetails(
        **issue.__dict__,
        assignee=assignee,
        reporter=reporter,
        project=project,
        comments_count=comments_count,
        attachments_count=0
    )


@router.patch("/issues/{issue_id}", response_model=IssueResponse)
def update_issue(
    issue_id: str,
    issue_data: IssueUpdate,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session)
):
    """Update issue"""
    issue = get_issue_with_permission(issue_id, user_id, session)
    
    # Track status change for history
    old_status = issue.status
    
    # Update fields
    update_data = issue_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(issue, field, value)
    
    # Set completed_at if status changed to done
    if issue_data.status == "done" and old_status != "done":
        issue.completed_at = datetime.utcnow()
    
    issue.updated_at = datetime.utcnow()
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


@router.delete("/issues/{issue_id}")
def delete_issue(
    issue_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session)
):
    """Delete issue"""
    issue = get_issue_with_permission(issue_id, user_id, session)
    
    # Check if user is admin or reporter
    project = session.get(Project, issue.project_id)
    member = session.exec(
        select(ProjectMember).where(
            ProjectMember.project_id == issue.project_id,
            ProjectMember.user_id == user_id
        )
    ).first()
    
    is_admin = project.owner_id == user_id or (member and member.role == "admin")
    is_reporter = issue.reporter_id == user_id
    
    if not is_admin and not is_reporter:
        raise HTTPException(status_code=403, detail="Only admin or reporter can delete")
    
    session.delete(issue)
    session.commit()
    return {"message": "Issue deleted"}


@router.get("/issues/{issue_id}/comments", response_model=List[dict])
def list_comments(
    issue_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session)
):
    """List comments for an issue"""
    issue = get_issue_with_permission(issue_id, user_id, session)
    
    comments = session.exec(
        select(Comment).where(Comment.issue_id == issue_id).order_by(Comment.created_at)
    ).all()
    
    result = []
    for c in comments:
        author = session.get(User, c.author_id)
        result.append({
            **c.__dict__,
            "author": author
        })
    
    return result


@router.post("/issues/{issue_id}/comments", response_model=dict)
def create_comment(
    issue_id: str,
    content: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session)
):
    """Add comment to issue"""
    issue = get_issue_with_permission(issue_id, user_id, session)
    
    comment = Comment(
        id=str(uuid.uuid4()),
        content=content,
        issue_id=issue_id,
        author_id=user_id
    )
    session.add(comment)
    session.commit()
    session.refresh(comment)
    
    author = session.get(User, user_id)
    return {**comment.__dict__, "author": author}