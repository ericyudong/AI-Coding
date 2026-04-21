"""E-Claw 管理端接口：租户管理、系统配置、计费日记等"""
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.core.database import AsyncSessionLocal
from app.core.security import get_current_user, get_password_hash
from app.models import User, UserRole, Tenant, Task, AuditLog, TokenUsage, KnowledgeBase

router = APIRouter()


# ============== 请求/响应模型 ==============
class TenantCreate(BaseModel):
    name: str
    code: str
    description: str = ""
    total_quota: int = 1000000
    status: str = "active"


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    total_quota: Optional[int] = None
    status: Optional[str] = None


class TenantResponse(BaseModel):
    id: str
    name: str
    code: str
    description: str = ""
    status: str
    total_quota: int
    used_quota: int
    user_count: int = 0
    created_at: str

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: str
    tenant_id: str = ""
    user_id: str = ""
    action: str
    resource_type: str = ""
    resource_id: str = ""
    method: str = ""
    path: str = ""
    ip_address: str = ""
    response_status: int = 0
    created_at: str


class StatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    total_token_usage: int
    active_tenants: int
    knowledge_bases: int
    documents: int


class UserCreateRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str = ""
    role: str = "employee"
    tenant_id: Optional[str] = None
    personal_quota: int = 100000


# ============== 租户管理接口 ==============
@router.get("/tenants", response_model=List[TenantResponse])
async def list_tenants(
    page: int = 1,
    page_size: int = 20,
    tenant_status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)):
    """获取租户列表 (仅超级管理员)"""
    print(f"[Backend] list_tenants called - user: {current_user.username}, role: {current_user.role}, page: {page}, page_size: {page_size}, tenant_status: {tenant_status}")

    # Use string comparison to avoid Pylance type inference issues with SQLAlchemy Enum columns
    if str(current_user.role) != UserRole.SUPER_ADMIN.value:
        print(f"[Backend] list_tenants - Access denied for user {current_user.username}, role: {current_user.role}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin only"
        )

    # 构建查询
    query = select(Tenant)

    if tenant_status:
        query = query.where(Tenant.status == tenant_status)

    # 分页
    query = query.order_by(Tenant.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    tenants = result.scalars().all()

    # 获取每个租户的用户数
    tenant_responses = []
    for tenant in tenants:
        user_count_result = await db.execute(
            select(func.count(User.id)).where(User.tenant_id == tenant.id)
        )
        user_count = user_count_result.scalar() or 0

        tenant_responses.append(
            TenantResponse(
                id=str(tenant.id),
                name=str(tenant.name),
                code=str(tenant.code),
                description=str(getattr(tenant, 'description', '') or ''),
                status=str(getattr(tenant, 'status', '') or ''),
                total_quota=int(getattr(tenant, 'total_quota', 0) or 0),
                used_quota=int(getattr(tenant, 'used_quota', 0) or 0),
                user_count=user_count,
                created_at=tenant.created_at.isoformat()
            )
        )

    return tenant_responses


@router.post("/tenants", response_model=TenantResponse)
async def create_tenant(
    request: TenantCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)):
    """创建租户 (仅超级管理员)"""
    print(f"[Backend] create_tenant called - user: {current_user.username}, role: {current_user.role}")
    print(f"[Backend] create_tenant request data: {request}")

    # Use string comparison to avoid Pylance type inference issues with SQLAlchemy Enum columns
    if str(current_user.role) != UserRole.SUPER_ADMIN.value:
        print(f"[Backend] create_tenant - Access denied for user {current_user.username}, role: {current_user.role}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin only"
        )

    # 检查租户代码是否已存在
    result = await db.execute(
        select(Tenant).where(Tenant.code == request.code)
    )
    existing_tenant = result.scalar_one_or_none()
    if existing_tenant:
        print(f"[Backend] create_tenant - Tenant code already exists: {request.code}")
        raise HTTPException(
            status_code=400,
            detail="Tenant code already exists"
        )

    # 创建租户
    tenant = Tenant(
        id=uuid.uuid4(),
        name=request.name,
        code=request.code,
        description=request.description,
        total_quota=request.total_quota,
        status="active"
    )
    print(f"[Backend] create_tenant - Creating tenant: {tenant.name} (code: {tenant.code})")
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    print(f"[Backend] create_tenant - Tenant created successfully: id={tenant.id}")

    response = TenantResponse(
        id=str(tenant.id),
        name=str(tenant.name),
        code=str(tenant.code),
        description=str(getattr(tenant, 'description', '') or ''),
        status=str(getattr(tenant, 'status', '') or ''),
        total_quota=int(getattr(tenant, 'total_quota', 0) or 0),
        used_quota=int(getattr(tenant, 'used_quota', 0) or 0),
        user_count=0,
        created_at=tenant.created_at.isoformat()
    )
    print(f"[Backend] create_tenant - Response: {response}")
    return response


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)):
    """获取租户详情"""
    # Use string comparison to avoid Pylance type inference issues with SQLAlchemy Enum columns
    if str(current_user.role) != UserRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin only"
        )

    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # 获取用户数
    user_count_result = await db.execute(
        select(func.count(User.id)).where(User.tenant_id == tenant.id)
    )
    user_count = user_count_result.scalar() or 0

    return TenantResponse(
        id=str(tenant.id),
        name=str(tenant.name),
        code=str(tenant.code),
        description=str(getattr(tenant, 'description', '') or ''),
        status=str(getattr(tenant, 'status', '') or ''),
        total_quota=int(getattr(tenant, 'total_quota', 0) or 0),
        used_quota=int(getattr(tenant, 'used_quota', 0) or 0),
        user_count=user_count,
        created_at=tenant.created_at.isoformat()
    )


@router.put("/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    request: TenantUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)):
    """更新租户"""
    # Use string comparison to avoid Pylance type inference issues with SQLAlchemy Enum columns
    if str(current_user.role) != UserRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin only"
        )

    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if request.name is not None:
        setattr(tenant, "name", request.name)
    if request.description is not None:
        setattr(tenant, "description", request.description)
    if request.total_quota is not None:
        setattr(tenant, "total_quota", request.total_quota)
    if request.status is not None:
        setattr(tenant, "status", request.status)

    setattr(tenant, "updated_at", datetime.utcnow())

    await db.commit()
    await db.refresh(tenant)

    # 获取用户数
    user_count_result = await db.execute(
        select(func.count(User.id)).where(User.tenant_id == tenant.id)
    )
    user_count = user_count_result.scalar() or 0

    return TenantResponse(
        id=str(tenant.id),
        name=str(tenant.name),
        code=str(tenant.code),
        description=str(getattr(tenant, 'description', '') or ''),
        status=str(getattr(tenant, 'status', '') or ''),
        total_quota=int(getattr(tenant, 'total_quota', 0) or 0),
        used_quota=int(getattr(tenant, 'used_quota', 0) or 0),
        user_count=user_count,
        created_at=tenant.created_at.isoformat()
    )


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)):
    """删除租户 (仅超级管理员)"""
    # Use string comparison to avoid Pylance type inference issues with SQLAlchemy Enum columns
    if str(current_user.role) != UserRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin only"
        )

    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # 检查是否有用户
    user_count_result = await db.execute(
        select(func.count(User.id)).where(User.tenant_id == tenant.id)
    )
    user_count = user_count_result.scalar() or 0

    if user_count > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete tenant with users"
        )

    # 软删除
    setattr(tenant, "status", "deleted")
    setattr(tenant, "updated_at", datetime.utcnow())

    await db.commit()

    return {"message": "Tenant deleted successfully"}


# ============== 用户管理接口 (管理员) ==============
@router.post("/users", response_model=dict)
async def create_user(
    request: UserCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)):
    """创建用户 (仅管理员)"""
    # Use string comparison to avoid Pylance type inference issues with SQLAlchemy Enum columns
    if str(current_user.role) not in [UserRole.SUPER_ADMIN.value, UserRole.DEPT_ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only"
        )

    # 部门管理员只能在本部门创建用户
    if str(current_user.role) == UserRole.DEPT_ADMIN.value:
        if request.tenant_id != str(current_user.tenant_id):
            raise HTTPException(
                status_code=403,
                detail="Can only create users in your department"
            )

    # 检查用户名是否已存在
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    # 检查邮箱是否已存在
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )

    # 创建用户
    user = User(
        id=uuid.uuid4(),
        tenant_id=request.tenant_id,
        username=request.username,
        email=request.email,
        full_name=request.full_name,
        hashed_password=get_password_hash(request.password),
        role=UserRole(request.role),
        personal_quota=request.personal_quota,
        status="active"
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {
        "message": "User created successfully",
        "user_id": str(user.id)
    }


# ============== 审计日志接口 ==============
@router.get("/audit", response_model=List[AuditLogResponse])
async def list_audit_logs(
    page: int = 1,
    page_size: int = 50,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)):
    """查询审计日记"""
    # Use string comparison to avoid Pylance type inference issues with SQLAlchemy Enum columns
    if str(current_user.role) not in [UserRole.SUPER_ADMIN.value, UserRole.DEPT_ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only"
        )

    # 构建查询
    query = select(AuditLog)

    # 部门管理员只能看到本部门的日记
    if str(current_user.role) == UserRole.DEPT_ADMIN.value and current_user.tenant_id is not None:
        query = query.where(AuditLog.tenant_id == current_user.tenant_id)
    elif tenant_id:
        query = query.where(AuditLog.tenant_id == tenant_id)

    if user_id:
        query = query.where(AuditLog.user_id == user_id)

    if action:
        query = query.where(AuditLog.action.like(f"%{action}%"))

    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)

    if start_date:
        start_dt = datetime.fromisoformat(start_date)
        query = query.where(AuditLog.created_at >= start_dt)

    if end_date:
        end_dt = datetime.fromisoformat(end_date)
        query = query.where(AuditLog.created_at <= end_dt)

    # 分页
    query = query.order_by(desc(AuditLog.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        AuditLogResponse(
            id=str(log.id),
            tenant_id=str(log.tenant_id) if log.tenant_id is not None else "",
            user_id=str(log.user_id) if log.user_id is not None else "",
            action=str(getattr(log, 'action', '') or ''),
            resource_type=str(getattr(log, 'resource_type', '') or ''),
            resource_id=str(getattr(log, 'resource_id', '') or ''),
            method=str(getattr(log, 'method', '') or ''),
            path=str(getattr(log, 'path', '') or ''),
            ip_address=str(getattr(log, 'ip_address', '') or ''),
            response_status=int(getattr(log, 'response_status', 0) or 0),
            created_at=log.created_at.isoformat()
        )
        for log in logs
    ]


# ============== 统计接口 ==============
@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)):
    """获取系统统计信息"""
    # Use string comparison to avoid Pylance type inference issues with SQLAlchemy Enum columns
    if str(current_user.role) not in [UserRole.SUPER_ADMIN.value, UserRole.DEPT_ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only"
        )

    # 基础查询条件
    base_filter = []
    if str(current_user.role) == UserRole.DEPT_ADMIN.value and current_user.tenant_id is not None:
        base_filter.append(User.tenant_id == current_user.tenant_id)

    # 用户统计
    user_count_result = await db.execute(
        select(func.count(User.id))
    )
    total_users = user_count_result.scalar() or 0

    active_users_result = await db.execute(
        select(func.count(User.id)).where(User.status == "active")
    )
    active_users = active_users_result.scalar() or 0

    # 任务统计
    task_count_result = await db.execute(
        select(func.count(Task.id))
    )
    total_tasks = task_count_result.scalar() or 0

    completed_tasks_result = await db.execute(
        select(func.count(Task.id)).where(Task.status == "completed")
    )
    completed_tasks = completed_tasks_result.scalar() or 0

    failed_tasks_result = await db.execute(
        select(func.count(Task.id)).where(Task.status == "failed")
    )
    failed_tasks = failed_tasks_result.scalar() or 0

    # Token使用统计
    token_usage_result = await db.execute(
        select(func.sum(TokenUsage.total_tokens))
    )
    total_token_usage = token_usage_result.scalar() or 0

    # 租户统计
    tenant_count_result = await db.execute(
        select(func.count(Tenant.id)).where(Tenant.status == "active")
    )
    active_tenants = tenant_count_result.scalar() or 0

    # 知识库统计
    kb_count_result = await db.execute(
        select(func.count(KnowledgeBase.id)).where(KnowledgeBase.status == "active")
    )
    knowledge_bases = kb_count_result.scalar() or 0

    # 文档统计
    from app.models import Document
    doc_count_result = await db.execute(
        select(func.count(Document.id)).where(Document.status != "deleted")
    )
    documents = doc_count_result.scalar() or 0

    return StatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        failed_tasks=failed_tasks,
        total_token_usage=total_token_usage,
        active_tenants=active_tenants,
        knowledge_bases=knowledge_bases,
        documents=documents
    )


# ============== 知识库审核接口 ==============
@router.get("/knowledge/review", response_model=List[dict])
async def list_pending_knowledge_bases(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)):
    """获取待审核的知识库列表"""
    # Use string comparison to avoid Pylance type inference issues with SQLAlchemy Enum columns
    if str(current_user.role) not in [UserRole.SUPER_ADMIN.value, UserRole.DEPT_ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only"
        )

    # 构建查询
    query = select(KnowledgeBase).where(KnowledgeBase.review_status == "pending")

    # 部门管理员只能看到本部门的
    if str(current_user.role) == UserRole.DEPT_ADMIN.value and current_user.tenant_id is not None:
        query = query.where(KnowledgeBase.tenant_id == current_user.tenant_id)

    query = query.order_by(KnowledgeBase.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    knowledge_bases = result.scalars().all()

    return [
        {
            "id": str(kb.id),
            "name": kb.name,
            "description": kb.description,
            "type": kb.type,
            "owner_id": str(kb.owner_id),
            "tenant_id": str(kb.tenant_id) if kb.tenant_id is not None else "",
            "doc_count": kb.doc_count,
            "created_at": kb.created_at.isoformat()
        }
        for kb in knowledge_bases
    ]


@router.post("/knowledge/{kb_id}/approve")
async def approve_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)):
    """审核通过知识库"""
    # Use string comparison to avoid Pylance type inference issues with SQLAlchemy Enum columns
    if str(current_user.role) not in [UserRole.SUPER_ADMIN.value, UserRole.DEPT_ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only"
        )

    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    # 部门管理员只能审核本部门的 - use str() to avoid Pylance type error with SQLAlchemy columns
    if str(current_user.role) == UserRole.DEPT_ADMIN.value:
        if current_user.tenant_id is not None and str(kb.tenant_id) != str(current_user.tenant_id):
            raise HTTPException(
                status_code=403,
                detail="Cannot review knowledge base from other department"
            )

    setattr(kb, "review_status", "approved")
    setattr(kb, "updated_at", datetime.utcnow())

    await db.commit()

    return {"message": "Knowledge base approved"}


@router.post("/knowledge/{kb_id}/reject")
async def reject_knowledge_base(
    kb_id: str,
    reason: str = "",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(AsyncSessionLocal)):
    """拒绝知识库"""
    # Use string comparison to avoid Pylance type inference issues with SQLAlchemy Enum columns
    if str(current_user.role) not in [UserRole.SUPER_ADMIN.value, UserRole.DEPT_ADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only"
        )

    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = result.scalar_one_or_none()

    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    # 部门管理员只能审核本部门的 - use str() to avoid Pylance type error with SQLAlchemy columns
    if str(current_user.role) == UserRole.DEPT_ADMIN.value:
        if current_user.tenant_id is not None and str(kb.tenant_id) != str(current_user.tenant_id):
            raise HTTPException(
                status_code=403,
                detail="Cannot review knowledge base from other department"
            )

    current_desc = getattr(kb, 'description', '') or ''
    setattr(kb, "review_status", "rejected")
    setattr(kb, "description", f"{current_desc}\n\nReject reason: {reason}" if current_desc else reason)
    setattr(kb, "updated_at", datetime.utcnow())

    await db.commit()

    return {"message": "Knowledge base rejected"}
