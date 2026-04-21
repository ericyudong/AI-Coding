"""API v1 router"""
from fastapi import APIRouter

from .auth import router as auth_router
from .projects import router as projects_router
from .issues import router as issues_router
from .users import router as users_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(projects_router)
api_router.include_router(issues_router)
api_router.include_router(users_router)