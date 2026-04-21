"""User API routes"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List

from ...core.database import get_session
from ...core.security import get_current_user_id
from ...models.user import User
from ...schemas.user import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=List[UserResponse])
def list_users(
    q: str = "",
    skip: int = 0,
    limit: int = 20,
    session: Session = Depends(get_session)
):
    """List users (for autocomplete, etc.)"""
    statement = select(User).where(User.is_active == True)
    
    if q:
        statement = statement.where(
            (User.username.ilike(f"%{q}%")) | 
            (User.email.ilike(f"%{q}%")) |
            (User.full_name.ilike(f"%{q}%"))
        )
    
    statement = statement.offset(skip).limit(limit)
    users = session.exec(statement).all()
    return users


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: str, session: Session = Depends(get_session)):
    """Get user by ID"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user