"""Main FastAPI application."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.config import get_settings
from backend.routers import chat

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="DeepSeek Q&A System",
    description="An intelligent Q&A system powered by DeepSeek",
    version="1.0.0"
)

# Add CORS middleware to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router)


@app.on_event("startup")
async def startup_event():
    """Initialize app on startup."""
    logger.info("=" * 50)
    logger.info("DeepSeek Q&A System Starting")
    logger.info(f"Model: {settings.deepseek_model}")
    logger.info(f"API Base URL: {settings.deepseek_base_url}")
    logger.info("=" * 50)


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    from backend.services.deepseek_api import _deepseek_api
    if _deepseek_api:
        await _deepseek_api.close()
    logger.info("Application shutdown")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Welcome to DeepSeek Q&A System",
        "version": "1.0.0",
        "docs": "/docs",
        "model": settings.deepseek_model
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model": settings.deepseek_model,
        "api_url": settings.deepseek_base_url
    }


# Mount static files (frontend)
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
