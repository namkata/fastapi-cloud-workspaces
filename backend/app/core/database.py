"""
Database configuration and session management.

This module provides:
- Async SQLAlchemy engine setup
- Database session management
- Connection utilities
- Database dependency injection
"""

import asyncio
from typing import AsyncGenerator, Optional

from app.core.config import get_settings
from app.core.models import Base
from sqlalchemy import event, pool
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from structlog import get_logger

logger = get_logger(__name__)
settings = get_settings()


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self) -> None:
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    @property
    def engine(self) -> AsyncEngine:
        """Get the database engine, creating it if necessary."""
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get the session factory, creating it if necessary."""
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
        return self._session_factory

    def _create_engine(self) -> AsyncEngine:
        """Create and configure the async database engine."""
        # Use the database_url directly from settings
        if settings.database_url:
            database_url = settings.database_url
        else:
            # Fallback to constructing URL from individual components
            database_url = (
                f"postgresql+asyncpg://{settings.database_user}:"
                f"{settings.database_password}@{settings.database_host}:"
                f"{settings.database_port}/{settings.database_name}"
            )

        # Engine configuration
        engine_kwargs = {
            "url": database_url,
            "echo": settings.debug,  # Use debug setting for SQL echo
            "echo_pool": settings.is_development,
            "pool_size": 10,  # Default pool size
            "max_overflow": 20,  # Default max overflow
            "pool_timeout": 30,  # Default pool timeout
            "pool_recycle": 3600,  # Default pool recycle (1 hour)
            "pool_pre_ping": True,
            # Don't specify poolclass for async engines - SQLAlchemy will choose the appropriate one
        }

        engine = create_async_engine(**engine_kwargs)

        # Add event listeners for connection management
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """Set database-specific connection parameters."""
            if "postgresql" in str(engine.url):
                # PostgreSQL-specific settings can be added here
                pass

        @event.listens_for(engine.sync_engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Log database connection checkout in development."""
            if settings.is_development:
                logger.debug("Database connection checked out")

        @event.listens_for(engine.sync_engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Log database connection checkin in development."""
            if settings.is_development:
                logger.debug("Database connection checked in")

        logger.info(
            "Database engine created",
            database_url=database_url.split("@")[-1],  # Hide credentials
            pool_size=10,  # Use the same default values we set above
            max_overflow=20,
        )

        return engine

    async def create_tables(self) -> None:
        """Create all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")

    async def drop_tables(self) -> None:
        """Drop all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("Database tables dropped")

    async def close(self) -> None:
        """Close the database engine and all connections."""
        if self._engine:
            await self._engine.dispose()
            logger.info("Database engine closed")

    async def health_check(self) -> bool:
        """Check if the database is accessible."""
        try:
            async with self.session_factory() as session:
                await session.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False


# Global database manager instance
db_manager = DatabaseManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get a database session.

    This function provides a database session for dependency injection
    in FastAPI endpoints. It ensures proper session lifecycle management.

    Yields:
        AsyncSession: Database session for the request

    Example:
        @app.get("/users/")
        async def get_users(db: AsyncSession = Depends(get_db_session)):
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    async with db_manager.session_factory() as session:
        try:
            logger.debug("Database session created")
            yield session
            await session.commit()
            logger.debug("Database session committed")
        except Exception as e:
            await session.rollback()
            logger.error("Database session rolled back", error=str(e))
            raise
        finally:
            await session.close()
            logger.debug("Database session closed")


async def get_db_session_context() -> AsyncSession:
    """
    Get a database session for use in context managers.

    This function provides a database session for use outside of
    FastAPI dependency injection, such as in background tasks
    or startup/shutdown events.

    Returns:
        AsyncSession: Database session

    Example:
        async with get_db_session_context() as db:
            result = await db.execute(select(User))
            users = result.scalars().all()
    """
    return db_manager.session_factory()


# Convenience aliases
SessionLocal = db_manager.session_factory
engine = db_manager.engine


async def init_db() -> None:
    """Initialize the database connection and create tables if needed."""
    try:
        # Test database connection
        health_ok = await db_manager.health_check()
        if not health_ok:
            raise RuntimeError("Database health check failed")

        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise


async def close_db() -> None:
    """Close database connections."""
    await db_manager.close()
