"""Database setup."""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=settings.debug)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    from app.core.migrations import run_migrations
    from app.models import cms_models, models  # noqa: F401
    from app.models import performance_models  # noqa: F401
    from app.services import audit_service  # noqa: F401
    from app.services.bootstrap import ensure_admin_user, seed_partners
    from app.services.cms_service import refresh_legacy_version_snapshots, seed_cms_data
    from app.services.index_service import reindex_all

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await run_migrations(engine)
    await ensure_admin_user()
    await seed_partners()
    async with SessionLocal() as session:
        from app.services.tag_service import seed_tag_taxonomy

        await seed_tag_taxonomy(session)
        await seed_cms_data(session)
        await refresh_legacy_version_snapshots(session)
        try:
            await reindex_all(session, user_id=1)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Seed reindex skipped: %s", exc)


async def get_db():
    async with SessionLocal() as session:
        yield session
