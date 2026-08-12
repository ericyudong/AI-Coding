"""API v1 router."""
from fastapi import APIRouter

from .auth import router as auth_router
from .content import router as content_router
from .contract import router as contract_router
from .cms import router as cms_router
from .legal import router as legal_router
from .admin import router as admin_router
from .performance import router as performance_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(content_router)
router.include_router(legal_router)
router.include_router(contract_router)
router.include_router(cms_router)
router.include_router(admin_router)
router.include_router(performance_router)
