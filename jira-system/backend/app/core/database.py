"""Database connection and session management"""
from sqlmodel import SQLModel, create_engine, Session
from typing import Generator

from .config import settings


# Synchronous engine (for SQLModel)
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)


def create_db_and_tables():
    """Create all database tables"""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Get database session"""
    with Session(engine) as session:
        yield session