"""
E-Claw 用户管理接口
"""
from datetime import datetime
from typing import List, Optional, cast
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.database import AsyncSessionLocal
from app.core.security import get_current_user, get_password_hash
from app.models import User, UserRole, Tenant

router = APIRouter()


# ============== 请求/响应模型 ==============

class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None  # 使用普通字符串，避免EmailStr对空字符串的验证问题


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: str = ""
    role: str
    tenant_id: Optional[str] = None
    personal_quota: int
    personal_used: int
    status: str
    created_at: str
    
    class Config:
        from_attributes = True


class QuotaUpdateRequest(BaseModel):
    personal_quota: int


# ============== 用户接口 ==============

@router.get("", response_model=List[UserResponse])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取用户列表 (仅管理员)"""
    # 权限检查
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # 构建查询
    query = select(User)
    
    # 部门管理员只能看到本部门用户
    if current_user.role.value == UserRole.DEPT_ADMIN.value and current_user.tenant_id is not None:
        query = query.where(User.tenant_id == current_user.tenant_id)
    
    # 分页
    query = query.order_by(User.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return [
        UserResponse(
            id=str(u.id),
            username=cast(str, u.username),
            email=cast(str, u.email),
            full_name=cast(str, u.full_name) if u.full_name is not None else "",
            role=cast(str, u.role.value),
            tenant_id=str(u.tenant_id) if u.tenant_id is not None else None,
            personal_quota=cast(int, u.personal_quota),
            personal_used=cast(int, u.personal_used),
            status=cast(str, u.status),
            created_at=u.created_at.isoformat()
        )
        for u in users
    ]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """获取用户详情"""
    # 普通用户只能查看自己
    if current_user.role.value == UserRole.EMPLOYEE.value and str(current_user.id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # 部门管理员只能查看本部门用户
    if current_user.role.value == UserRole.DEPT_ADMIN.value:
        if str(current_user.id) == user_id:
            user = current_user
        else:
            result = await db.execute(
                select(User).where(
                    and_(
                        User.id == user_id,
                        User.tenant_id == current_user.tenant_id
                    )
                )
            )
            user = result.scalar_one_or_none()
    else:
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=str(user.id),
        username=cast(str, user.username),
        email=cast(str, user.email),
        full_name=cast(str, user.full_name) if user.full_name is not None else "",
        role=cast(str, user.role.value),
        tenant_id=str(user.tenant_id) if user.tenant_id is not None else None,
        personal_quota=cast(int, user.personal_quota),
        personal_used=cast(int, user.personal_used),
        status=cast(str, user.status),
        created_at=user.created_at.isoformat()
    )


@router.put("/{user_id}")
async def update_user(
    user_id: str,
    request: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """更新用户信息"""
    # 普通用户只能更新自己
    if current_user.role.value == UserRole.EMPLOYEE.value and str(current_user.id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 更新字段
    if request.full_name is not None:
        user.full_name = request.full_name  # type: ignore[assignment]
    if request.email is not None and request.email != "":
        # 检查邮箱是否已被使用
        existing = await db.execute(
            select(User).where(
                and_(
                    User.email == request.email,
                    User.id != user_id
                )
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Email already in use"
            )
        user.email = request.email  # type: ignore[assignment]
    elif request.email == "":
        # 允许清空邮箱
        user.email = ""  # type: ignore[assignment]
    
    user.updated_at = datetime.utcnow()  # type: ignore[assignment]
    await db.commit()
    
    return {"message": "User updated successfully"}


@router.put("/{user_id}/quota")
async def update_user_quota(
    user_id: str,
    request: QuotaUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """更新用户配额 (仅管理员)"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 部门管理员只能更新本部门用户
    if current_user.role.value == UserRole.DEPT_ADMIN.value:
        if cast(str, user.tenant_id) != cast(str, current_user.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update user in another department"
            )
    
    user.personal_quota = request.personal_quota  # type: ignore[assignment]
    user.updated_at = datetime.utcnow()  # type: ignore[assignment]
    await db.commit()
    
    return {"message": "User quota updated successfully"}


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """删除用户 (仅超级管理员)"""
    if current_user.role.value != UserRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # 不能删除自己
    if str(current_user.id) == user_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete yourself"
        )
    
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.status = "deleted"  # type: ignore[assignment]
    await db.commit()
    
    return {"message": "User deleted successfully"}


@router.post("/{user_id}/disable")
async def disable_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """禁用用户 (仅管理员)"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # 不能禁用自己
    if str(current_user.id) == user_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot disable yourself"
        )
    
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 部门管理员只能操作本部门用户
    if current_user.role.value == UserRole.DEPT_ADMIN.value:
        if cast(str, user.tenant_id) != cast(str, current_user.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update user in another department"
            )
    
    user.status = "disabled"  # type: ignore[assignment]
    user.updated_at = datetime.utcnow()  # type: ignore[assignment]
    await db.commit()
    
    return {"message": "User disabled successfully"}


@router.post("/{user_id}/enable")
async def enable_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """启用用户 (仅管理员)"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 部门管理员只能操作本部门用户
    if current_user.role.value == UserRole.DEPT_ADMIN.value:
        if cast(str, user.tenant_id) != cast(str, current_user.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update user in another department"
            )
    
    user.status = "active"  # type: ignore[assignment]
    user.updated_at = datetime.utcnow()  # type: ignore[assignment]
    await db.commit()
    
    return {"message": "User enabled successfully"}