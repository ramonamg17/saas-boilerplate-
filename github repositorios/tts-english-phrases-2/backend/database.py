"""
database.py — Async SQLAlchemy engine + session dependency.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args={
        "statement_cache_size": 0,
    },
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    """Create all tables. Called from app lifespan."""
    async with engine.begin() as conn:
        from models import user as _  # noqa: F401 — registers User models
        from models import session_model as _2  # noqa: F401 — registers TtsSession
        await conn.run_sync(Base.metadata.create_all)
        # Add last_played_at if it doesn't exist (migration for existing DBs)
        from sqlalchemy import text
        try:
            await conn.execute(text(
                "ALTER TABLE tts_sessions ADD COLUMN last_played_at TIMESTAMPTZ"
            ))
        except Exception:
            pass  # Column already exists
