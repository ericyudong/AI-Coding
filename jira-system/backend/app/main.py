"""FastAPI application"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.database import create_db_and_tables
from .api.v1 import api_router


def get_application() -> FastAPI:
    """Create and configure FastAPI application"""
    application = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    )
    
    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Create tables on startup
    @application.on_event("startup")
    def on_startup():
        create_db_and_tables()
    
    # Include API router
    application.include_router(api_router, prefix=settings.API_V1_PREFIX)
    
    @application.get("/health")
    def health_check():
        return {"status": "healthy"}
    
    return application


app = get_application()