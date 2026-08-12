"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from app.api.v1 import router as v1_router
from app.core.config import get_settings
from app.core.database import init_db


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or not self.html:
                raise
            index = Path(self.directory) / "index.html"
            if not index.is_file():
                raise
            stat = index.stat()
            return self.file_response(str(index.resolve()), stat, scope)


def _resolve_static_dir() -> Path | None:
    settings = get_settings()
    raw = (settings.static_dir or "").strip()
    candidates: list[Path] = []
    if raw:
        p = Path(raw)
        candidates.append(p if p.is_absolute() else (Path(__file__).resolve().parents[1] / p))
    candidates.append(Path(__file__).resolve().parents[1] / "static")
    for path in candidates:
        if path.is_dir() and (path / "index.html").is_file():
            return path.resolve()
    return None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    from app.services.alert_scheduler import start_alert_scheduler, stop_alert_scheduler

    start_alert_scheduler()
    yield
    await stop_alert_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="益慧科技法务Agent系统",
        lifespan=lifespan,
    )

    origins = settings.cors_allow_origins or (["*"] if settings.debug else [])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router)

    @app.get("/health")
    async def health():
        return {"status": "healthy", "version": settings.app_version, "app": settings.app_name}

    static_root = _resolve_static_dir()
    if static_root is not None:
        app.mount("/", SPAStaticFiles(directory=str(static_root), html=True), name="frontend")

    return app


app = create_app()
