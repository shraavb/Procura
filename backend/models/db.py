"""
Async database session management.
Production-ready with connection pooling and health checks.
"""
import os
import ssl
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from config import get_settings
from models.database import Base

settings = get_settings()

# Determine if we need SSL (production/Render)
_is_production = os.getenv("ENVIRONMENT") == "production" or "render.com" in settings.database_url

# SSL configuration for asyncpg
_async_connect_args = {}
if _is_production:
    _async_connect_args["ssl"] = "require"

# Async engine for production use
async_engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=settings.db_pool_pre_ping,
    pool_recycle=settings.db_pool_recycle,
    echo=settings.debug,
    connect_args=_async_connect_args,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# SSL configuration for psycopg2/psycopg (sync)
_sync_connect_args = {}
if _is_production:
    _sync_connect_args["sslmode"] = "require"

# Sync engine for migrations and seeding
sync_engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
    connect_args=_sync_connect_args,
)

SyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine,
)


async def init_db() -> None:
    """Initialize database tables (async)."""
    async with async_engine.begin() as conn:
        # Enable pgvector extension (required for embeddings)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)


def init_db_sync() -> None:
    """Initialize database tables (sync, for migrations)."""
    Base.metadata.create_all(bind=sync_engine)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Sync versions for migrations and seeding scripts
def get_sync_db() -> Session:
    """Get sync database session for migrations/seeding."""
    return SyncSessionLocal()


@contextmanager
def get_sync_db_context():
    """Context manager for sync database session."""
    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def check_db_health() -> bool:
    """Check database connectivity."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception:
        return False


async def close_db() -> None:
    """Close database connections."""
    await async_engine.dispose()
