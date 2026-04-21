"""
E-Claw API v1 路由汇总
"""
from fastapi import APIRouter
from app.api.v1 import auth, users, tasks, knowledge, admin

# 创建主路由
api_router = APIRouter()

# 注册子路由
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["任务"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["知识库"])
api_router.include_router(admin.router, prefix="/admin", tags=["管理"])