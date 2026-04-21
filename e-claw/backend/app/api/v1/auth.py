"""
E-Claw 认证接口
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import (
    verify_password, 
    create_access_token, 
    get_password_hash,
    get_current_user
)
from app.models import User, UserRole, Tenant

router = APIRouter()


# Debug test endpoint in router
@router.post("/debug-login")
async def debug_login(
    request: Request,
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """Debug login endpoint - also performs real authentication"""
    body = await request.body()
    if not body:
        return {"status": "error", "message": "Request body is empty"}
    
    import json
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON"}
    
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        return {"status": "error", "message": "Username and password are required"}
    
    user = await verify_user(username, password, db)
    
    if not user:
        return {"status": "error", "message": "Incorrect username or password"}
    
    return create_token_response(user)


# ============== 请求/响应模型 ==============

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str = ""
    tenant_id: str = None  # 可选，超级管理员可以指定


class UserInfo(BaseModel):
    id: str
    username: str
    email: str
    full_name: str = ""
    role: str
    tenant_id: str = None
    personal_quota: int
    personal_used: int
    
    class Config:
        from_attributes = True


# ============== 认证接口 ==============

async def verify_user(username: str, password: str, db: AsyncSession):
    """验证用户并返回用户对象"""
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    
    # 如果没有用户，自动创建管理员用户
    if not user:
        # 检查是否需要创建默认租户
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.code == "DEFAULT")
        )
        tenant = tenant_result.scalar_one_or_none()
        
        if not tenant:
            tenant = Tenant(
                id=uuid.uuid4(),
                name="Default Tenant",
                code="DEFAULT",
                description="Default tenant",
                status="active",
                total_quota=1000000,
                used_quota=0
            )
            db.add(tenant)
            await db.flush()
        
        # 创建管理员用户
        # bcrypt 限制密码最多72字节，需要截断
        password_bytes = password.encode('utf-8')[:72]
        user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            username=username,
            email=f"{username}@eclaw.local",
            full_name="Administrator",
            hashed_password=get_password_hash(password_bytes.decode('utf-8')),
            role=UserRole.SUPER_ADMIN,
            status="active",
            personal_quota=100000,
            personal_used=0,
            login_failed_count=0
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    
    if not verify_password(password, user.hashed_password):
        return None
    
    # 检查用户状态
    if user.status != "active":
        return None
    
    # 检查账号锁定
    if user.locked_until and user.locked_until > datetime.utcnow():
        return None
    
    # Skip updating last_login to avoid the StaleDataError issue
    # The user is authenticated, that's what matters

    return user


def create_token_response(user: User) -> LoginResponse:
    """创建登录响应"""
    token_data = {
        "sub": str(user.id),
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        "role": user.role.value
    }
    access_token = create_access_token(token_data)
    
    return LoginResponse(
        access_token=access_token,
        user={
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name or "",
            "role": user.role.value,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "personal_quota": user.personal_quota,
            "personal_used": user.personal_used
        }
    )


@router.post("/authenticate-user")
async def authenticate_user(
    request: Request,
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """用户登录 - 支持JSON格式"""
    body = await request.body()
    if not body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body is empty"
        )
    
    import json
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON"
        )
    
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required"
        )
    
    user = await verify_user(username, password, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    return create_token_response(user)


# Simple test endpoint
@router.get("/test")
async def test_endpoint():
    """Test endpoint"""
    return {"status": "ok", "message": "Server is working"}


@router.post("/login/form", response_model=LoginResponse)
async def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """用户登录 - 表单格式 (OAuth2)"""
    user = await verify_user(form_data.username, form_data.password, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return create_token_response(user)


@router.post("/register", response_model=LoginResponse)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """用户注册"""
    # 检查用户名是否已存在
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # 检查邮箱是否已存在
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # 创建用户
    import uuid
    new_user = User(
        id=uuid.uuid4(),
        tenant_id=request.tenant_id,
        username=request.username,
        email=request.email,
        full_name=request.full_name,
        hashed_password=get_password_hash(request.password),
        role="employee",
        status="active",
        personal_quota=100000,
        personal_used=0
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # 生成令牌
    token_data = {
        "sub": str(new_user.id),
        "tenant_id": str(new_user.tenant_id) if new_user.tenant_id else None,
        "role": new_user.role.value
    }
    access_token = create_access_token(token_data)
    
    return LoginResponse(
        access_token=access_token,
        user={
            "id": str(new_user.id),
            "username": new_user.username,
            "email": new_user.email,
            "full_name": new_user.full_name or "",
            "role": new_user.role.value,
            "tenant_id": str(new_user.tenant_id) if new_user.tenant_id else None,
            "personal_quota": new_user.personal_quota,
            "personal_used": new_user.personal_used
        }
    )


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """获取当前用户信息"""
    return UserInfo(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name or "",
        role=current_user.role.value,
        tenant_id=str(current_user.tenant_id) if current_user.tenant_id else None,
        personal_quota=current_user.personal_quota,
        personal_used=current_user.personal_used
    )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """用户登出"""
    return {"message": "Logout successful"}


@router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)
):
    """修改密码"""
    if not verify_password(old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password"
        )
    
    current_user.hashed_password = get_password_hash(new_password)
    await db.commit()
    
    return {"message": "Password changed successfully"}