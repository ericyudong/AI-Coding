"""
E-Claw äźä¸çş§AIćşč˝ä˝čżčĄĺšłĺ?- ĺçŤŻĺĽĺŁ
ĺşäşOpenClawćśćčŽžčŽĄďźćŻćĺ¤ç§ćˇéçŚťăć­çšçť­čˇăRAGćŁç´?
"""
import sys
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal

# ćˇťĺ éĄšçŽć šçŽĺ˝ĺ°čˇŻĺž
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.core.database import init_db, close_db
from app.api.v1 import auth, users, tasks, knowledge, admin, system
from app.api.v1 import monitor, logs
from app.api.v1 import gateway
from app.api.v1 import instances
from app.api.websocket import websocket_endpoint
from fastapi import Request
import json


@asynccontextmanager
async def lifespan(app: FastAPI):
    """ĺşç¨çĺ˝ĺ¨ćçŽĄç"""
    # ĺŻĺ¨ćśĺĺ§ĺ
    await init_db()
    
    # Print routes
    print("="*50)
    print("Registered routes:")
    for route in app.routes:
        if isinstance(route, APIRoute):
            print(f"  {list(route.methods)} {route.path}")
    print("="*50)
    
    yield
    # ĺłé­ćść¸ç?
    await close_db()


# ĺĺťşFastAPIĺşç¨
app = FastAPI(
    title="E-Claw Enterprise AI Agent Platform",
    version="1.0.0",
    description="Enterprise AI Agent Platform based on OpenClaw",
    lifespan=lifespan
)

# Print all routes on startup
@app.on_event("startup")
async def print_routes():
    print("="*50)
    print("Registered routes:")
    for route in app.routes:
        if isinstance(route, APIRoute):
            print(f"  {route.methods} {route.path}")
    print("="*50)

# ćˇťĺ CORSä¸­é´äť?
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# NOTE: The local_kw issue is handled by the frontend now
# The problematic query parameter is no longer sent


# ĺ¨ĺąĺźĺ¸¸ĺ¤ç
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail,
            "data": None
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": f"Internal server error: {str(exc)}",
            "data": None
        }
    )


from fastapi import Query

# Test endpoint to debug
@app.get("/test-users")
async def test_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """Test endpoint"""
    return {"page": page, "page_size": page_size, "status": "ok"}


# ĺĽĺşˇćŁć?
@app.get("/health")
async def health_check():
    """ĺĽĺşˇćŁćĽćĽĺ?""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "service": "E-Claw"
    }


# Direct login endpoint - uses raw uvicorn route to avoid local_kw issue
@app.post("/api/login")
async def api_login(request: Request):
    """Direct login endpoint that bypasses the local_kw issue"""
    from app.api.v1.auth import verify_user, create_token_response
    from app.core.database import AsyncSessionLocal
    
    # Get database session manually
    async with AsyncSessionLocal() as db:
        try:
            # Use FastAPI's built-in JSON parsing
            data = await request.json()
        except Exception:
            return {"status": "error", "message": "Invalid JSON"}
        
        if not data:
            return {"status": "error", "message": "Request body is empty"}
        
        username = data.get("username")
        password = data.get("password")
        
        if not username or not password:
            return {"status": "error", "message": "Username and password are required"}
        
        # bcrypt éĺśĺŻç ćĺ¤?2ĺ­čďźéčŚćŞć?
        password_bytes = password.encode('utf-8')[:72]
        password = password_bytes.decode('utf-8')
        
        user = await verify_user(username, password, db)
        
        if not user:
            return {"status": "error", "message": "Incorrect username or password"}
        
        return create_token_response(user)


# Direct instance creation endpoint to bypass local_kw issue
@app.post("/api/direct/instances", tags=["instances"])
async def create_instance_direct(request: Request):
    """Direct instance creation endpoint to bypass local_kw issue"""
    from app.api.v1.instances import InstanceService, CreateInstanceRequest, InstanceResponse, create_default_quota
    from app.models import UserQuota
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select
    
    # Get database session manually
    async with AsyncSessionLocal() as db:
        try:
            data = await request.json()
        except Exception:
            return {"status": "error", "message": "Invalid JSON"}
        
        if not data:
            return {"status": "error", "message": "Request body is empty"}
        
        # Get token from header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return {"status": "error", "message": "Invalid authorization header"}
        
        token = auth_header[7:]
        
        # Decode token to get user
        from app.core.security import decode_token
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
            if not user_id:
                return {"status": "error", "message": "Invalid token"}
        except Exception as e:
            return {"status": "error", "message": f"Token decode error: {str(e)}"}
        
        # Get user from database
        from app.models import User
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return {"status": "error", "message": "User not found"}
        
        # Check and create quota
        quota_result = await db.execute(
            select(UserQuota).where(UserQuota.user_id == user_id)
        )
        quota = quota_result.scalar_one_or_none()
        
        if not quota:
            quota = await create_default_quota(db, user_id)
        
        # Create instance
        instance_service = InstanceService(db)
        
        create_req = CreateInstanceRequest(
            name=data.get("name", "unnamed"),
            description=data.get("description"),
            instance_type=data.get("instance_type", "openclaw"),
            cpu_cores=data.get("cpu_cores", 2),
            memory_gb=data.get("memory_gb", 4),
            disk_gb=data.get("disk_gb", 20),
            gpu_enabled=data.get("gpu_enabled", False),
            gpu_count=data.get("gpu_count", 0),
            os_type=data.get("os_type", "linux"),
            os_version=data.get("os_version", "latest")
        )
        
        try:
            result = await instance_service.create_instance(
                user_id=user_id,
                req=create_req
            )
            
            return {
                "status": "success",
                "instance_id": result["instance_id"],
                "instance_name": result["instance_name"],
                "instance_type": result["instance_type"],
                "status": result["status"],
                "pod_name": result.get("pod_name"),
                "service_url": result.get("service_url"),
                "port": result.get("port"),
                "access_token": result.get("access_token"),
                "created_at": result.get("created_at")
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": f"Failed to create instance: {str(e)}"}


# Direct tenant creation endpoint to bypass local_kw issue
@app.post("/api/direct/tenants", tags=["tenants"])
async def create_tenant_direct(request: Request):
    """Direct tenant creation endpoint to bypass local_kw issue"""
    from app.models import Tenant, User, UserRole
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select
    import uuid
    
    # Get database session manually
    async with AsyncSessionLocal() as db:
        try:
            data = await request.json()
        except Exception:
            return {"status": "error", "message": "Invalid JSON"}
        
        if not data:
            return {"status": "error", "message": "Request body is empty"}
        
        # Get token from header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return {"status": "error", "message": "Invalid authorization header"}
        
        token = auth_header[7:]
        
        # Decode token to get user
        from app.core.security import decode_token
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
            if not user_id:
                return {"status": "error", "message": "Invalid token"}
        except Exception as e:
            return {"status": "error", "message": f"Token decode error: {str(e)}"}
        
        # Get user from database
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return {"status": "error", "message": "User not found"}
        
        # Check if user is super admin
        user_role = user.role
        if user_role is None or user_role.value != UserRole.SUPER_ADMIN.value:
            return {"status": "error", "message": "Super admin only"}
        
        # Check if tenant code already exists
        tenant_code = data.get("code")
        if not tenant_code:
            return {"status": "error", "message": "Tenant code is required"}
        
        check_result = await db.execute(
            select(Tenant).where(Tenant.code == tenant_code)
        )
        if check_result.scalar_one_or_none():
            return {"status": "error", "message": "Tenant code already exists"}
        
        # Create tenant
        tenant = Tenant(
            id=uuid.uuid4(),
            name=data.get("name", ""),
            code=tenant_code,
            description=data.get("description", ""),
            total_quota=data.get("total_quota", 1000000),
            status="active"
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        
        return {
            "status": "success",
            "id": str(tenant.id),
            "name": tenant.name,
            "code": tenant.code,
            "description": tenant.description,
            "status": tenant.status,
            "total_quota": tenant.total_quota,
            "used_quota": 0,
            "user_count": 0,
            "created_at": tenant.created_at.isoformat()
        }


# Direct users list endpoint to bypass local_kw issue
@app.get("/api/direct/users", tags=["users"])
async def list_users_direct(
    request: Request,
    page: int = 1,
    page_size: int = 20
):
    """Direct users list endpoint to bypass local_kw issue"""
    from app.models import User, UserRole
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as db:
        # Get token from header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return {"status": "error", "message": "Invalid authorization header"}
        
        token = auth_header[7:]
        
        # Decode token to get user
        from app.core.security import decode_token
        try:
            payload = decode_token(token)
            current_user_id = payload.get("sub")
        except:
            return {"status": "error", "message": "Invalid token"}
        
        # Get current user
        result = await db.execute(
            select(User).where(User.id == current_user_id)
        )
        current_user = result.scalar_one_or_none()
        
        if not current_user:
            return {"status": "error", "message": "User not found"}
        
        # Check permissions
        if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN]:
            return {"status": "error", "message": "Insufficient permissions"}
        
        # Build query
        query = select(User)
        
        # Dept admin can only see users in their department
        user_role = current_user.role
        user_tenant_id = current_user.tenant_id
        # type ignore below is needed because SQLAlchemy's ColumnElement 
        # doesn't implement __bool__ which causes Pylance to complain about "is not None"
        if user_role == UserRole.DEPT_ADMIN and (user_tenant_id is not None):  # type: ignore[comparison]
            query = query.where(User.tenant_id == user_tenant_id)
        
        # Pagination
        query = query.order_by(User.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(query)
        users = result.scalars().all()
        
        return [
            {
                "id": str(u.id),
                "username": u.username,
                "email": u.email,
                "full_name": u.full_name or "",
                "role": u.role.value,
                "tenant_id": str(u.tenant_id) if u.tenant_id is not None else None,
                "personal_quota": u.personal_quota,
                "personal_used": u.personal_used or 0,
                "status": u.status,
                "created_at": u.created_at.isoformat()
            }
            for u in users
        ]


# Direct tasks list endpoint to bypass local_kw issue
@app.get("/api/direct/tasks", tags=["tasks"])
async def list_tasks_direct(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None
):
    """Direct tasks list endpoint to bypass local_kw issue"""
    from app.models import Task, TaskStatus, User, UserRole
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as db:
        # Get token from header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return {"status": "error", "message": "Invalid authorization header"}
        
        token = auth_header[7:]
        
        # Decode token to get user
        from app.core.security import decode_token
        try:
            payload = decode_token(token)
            current_user_id = payload.get("sub")
        except:
            return {"status": "error", "message": "Invalid token"}
        
        # Get current user
        result = await db.execute(
            select(User).where(User.id == current_user_id)
        )
        current_user = result.scalar_one_or_none()
        
        if not current_user:
            return {"status": "error", "message": "User not found"}
        
        # Build query
        query = select(Task)
        
        # Filter by user role
        # type: ignore[comparison] - SQLAlchemy's ColumnElement doesn't implement __bool__
        if current_user.role == UserRole.EMPLOYEE:  # type: ignore[comparison]
            query = query.where(Task.user_id == current_user.id)
        elif current_user.role == UserRole.DEPT_ADMIN and current_user.tenant_id is not None:  # type: ignore[comparison]
            query = query.where(Task.tenant_id == current_user.tenant_id)
        
        # Filter by status
        if status:
            query = query.where(Task.status == TaskStatus(status))
        
        # Pagination
        query = query.order_by(Task.submit_time.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(query)
        tasks = result.scalars().all()
        
        return [
            {
                "id": str(t.id),
                "name": t.name,
                "status": t.status.value,
                "priority": t.priority.value if t.priority is not None else "medium",
                "progress": t.progress or 0,
                "submit_time": t.submit_time.isoformat() if t.submit_time is not None else None,
                "start_time": t.start_time.isoformat() if t.start_time is not None else None,
                "end_time": t.end_time.isoformat() if t.end_time is not None else None,
            }
            for t in tasks
        ]


# Direct knowledge list endpoint to bypass local_kw issue
@app.get("/api/direct/knowledge", tags=["knowledge"])
async def list_knowledge_direct(
    page: int = 1,
    page_size: int = 20,
    request: Request | None = None
):
    """Direct knowledge list endpoint to bypass local_kw issue"""
    from app.models import KnowledgeBase, User, UserRole
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as db:
        # Get token from header
        auth_header = request.headers.get("Authorization", "")  # type: ignore[union-attr]
        if not auth_header.startswith("Bearer "):
            return {"status": "error", "message": "Invalid authorization header"}
        
        token = auth_header[7:]
        
        # Decode token to get user
        from app.core.security import decode_token
        try:
            payload = decode_token(token)
            current_user_id = payload.get("sub")
        except:
            return {"status": "error", "message": "Invalid token"}
        
        # Get current user
        result = await db.execute(
            select(User).where(User.id == current_user_id)
        )
        current_user = result.scalar_one_or_none()
        
        if not current_user:
            return {"status": "error", "message": "User not found"}
        
        # Build query
        query = select(KnowledgeBase)
        
        # Filter by user role
        if current_user.role == UserRole.EMPLOYEE:
            query = query.where(
                (KnowledgeBase.owner_id == current_user.id) | 
                (KnowledgeBase.type == "dept_shared")
            )
            if current_user.tenant_id is not None:
                query = query.where(KnowledgeBase.tenant_id == current_user.tenant_id)
        elif current_user.role == UserRole.DEPT_ADMIN and current_user.tenant_id is not None:
            query = query.where(KnowledgeBase.tenant_id == current_user.tenant_id)
        
        # Pagination
        query = query.order_by(KnowledgeBase.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(query)
        kbs = result.scalars().all()
        
        return [
            {
                "id": str(kb.id),
                "name": kb.name,
                "description": kb.description,
                "type": kb.type,
                "status": kb.status,
                "doc_count": kb.doc_count or 0,
                "created_at": kb.created_at.isoformat() if kb.created_at is not None else None,
            }
            for kb in kbs
        ]


# Direct instances list endpoint to bypass local_kw issue
@app.get("/api/direct/instances", tags=["instances"])
async def list_instances_direct(
    page: int = 1,
    page_size: int = 20,
    request: Request | None = None
):
    """Direct instances list endpoint to bypass local_kw issue"""
    from app.models import Task, User, UserRole
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select, and_
    
    async with AsyncSessionLocal() as db:
        # Get token from header
        auth_header = request.headers.get("Authorization", "")  # type: ignore[union-attr]
        if not auth_header.startswith("Bearer "):
            return {"status": "error", "message": "Invalid authorization header"}
        
        token = auth_header[7:]
        
        # Decode token to get user
        from app.core.security import decode_token
        try:
            payload = decode_token(token)
            current_user_id = payload.get("sub")
        except:
            return {"status": "error", "message": "Invalid token"}
        
        # Get current user
        result = await db.execute(
            select(User).where(User.id == current_user_id)
        )
        current_user = result.scalar_one_or_none()
        
        if not current_user:
            return {"status": "error", "message": "User not found"}
        
        # Build query - get tasks that have docker containers (instances)
        query = select(Task).where(Task.docker_container_id.isnot(None))
        
        # Filter by user role
        if current_user.role == UserRole.EMPLOYEE:
            query = query.where(Task.user_id == current_user.id)
        elif current_user.role == UserRole.DEPT_ADMIN and current_user.tenant_id is not None:
            query = query.where(Task.tenant_id == current_user.tenant_id)
        
        # Pagination
        query = query.order_by(Task.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(query)
        tasks = result.scalars().all()
        
        return [
            {
                "id": str(t.id),
                "name": t.name,
                "status": t.docker_status or "unknown",
                "docker_container_id": t.docker_container_id,
                "docker_url": t.docker_url,
                "docker_port": t.docker_port,
                "created_at": t.submit_time.isoformat() if t.submit_time is not None else None,
            }
            for t in tasks
        ]


# APIčˇŻçą
app.include_router(auth.router, prefix="/api/v1/auth", tags=["čŽ¤čŻ"])
app.include_router(users.router, prefix="/api/v1/users", tags=["ç¨ćˇ"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["äťťĺĄ"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["çĽčŻĺş?])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["çŽĄç"])
app.include_router(system.router, prefix="/api/v1/system", tags=["çłťçťéç˝Ž"])
app.include_router(monitor.router, prefix="/api/v1/system", tags=["çłťçťçć§"])
app.include_router(logs.router, prefix="/api/v1/system", tags=["ćĽĺżćĽčŻ˘"])
app.include_router(gateway.router, prefix="/api/v1", tags=["AI Gateway"])
app.include_router(instances.router, prefix="/api/v1/instances", tags=["ĺŽäžçŽĄç"])

# WebSocketčˇŻçą
app.websocket("/ws")(websocket_endpoint)


# ć ščˇŻĺž?
@app.get("/")
async def root():
    """APIć ščˇŻĺž?""
    return {
        "name": "E-Claw äźä¸çş§AIćşč˝ä˝ĺšłĺ?,
        "version": "1.0.0",
        "docs": "/docs",
        "architecture": "ä¸ĺąčĺćść (ć§čĄĺą?çŽĄçĺą?ééĺą?"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )