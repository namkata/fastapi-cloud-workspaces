"""
Application startup and shutdown event handlers.
"""
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from app.core.config import settings
from app.core.database import engine
from app.core.logger import configure_logging, get_logger
from app.core.metrics import update_active_users, update_workspace_count
from app.modules.auth.models import User
from app.modules.workspace.models import Workspace
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("events")


async def startup_tasks():
    """Tasks to run on application startup."""
    logger.info("Starting application startup tasks")

    try:
        # Configure logging
        configure_logging()
        logger.info("Logging configured successfully")

        # Initialize metrics with current counts
        async with AsyncSession(engine) as session:
            # Update workspace count
            workspace_count = await session.scalar(select(func.count(Workspace.id)))
            update_workspace_count(workspace_count or 0)

            # Update active users count
            active_users_count = await session.scalar(
                select(func.count(User.id)).where(User.is_active == True)
            )
            update_active_users(active_users_count or 0)

            logger.info(
                "Initial metrics updated",
                extra={
                    "workspace_count": workspace_count,
                    "active_users": active_users_count
                }
            )

        # Log application info
        logger.info(
            "Application started successfully",
            extra={
                "environment": settings.environment,
                "debug": settings.debug,
                "database_url": settings.database_url.split("@")[-1] if "@" in settings.database_url else "***",
                "redis_url": settings.redis_url.split("@")[-1] if "@" in settings.redis_url else "***"
            }
        )

    except Exception as e:
        logger.error(f"Startup task failed: {str(e)}", exc_info=True)
        raise


async def shutdown_tasks():
    """Tasks to run on application shutdown."""
    logger.info("Starting application shutdown tasks")

    try:
        # Close database connections
        await engine.dispose()
        logger.info("Database connections closed")

        # Log shutdown completion
        logger.info("Application shutdown completed successfully")

    except Exception as e:
        logger.error(f"Shutdown task failed: {str(e)}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.
    Handles startup and shutdown events.
    """
    # Startup
    await startup_tasks()

    try:
        yield
    finally:
        # Shutdown
        await shutdown_tasks()


# Background task for periodic metrics updates
async def periodic_metrics_update():
    """Periodically update metrics that require database queries."""
    while True:
        try:
            async with AsyncSession(engine) as session:
                # Update workspace count
                workspace_count = await session.scalar(select(func.count(Workspace.id)))
                update_workspace_count(workspace_count or 0)

                # Update active users count
                active_users_count = await session.scalar(
                    select(func.count(User.id)).where(User.is_active == True)
                )
                update_active_users(active_users_count or 0)

                logger.debug(
                    "Metrics updated",
                    extra={
                        "workspace_count": workspace_count,
                        "active_users": active_users_count
                    }
                )

        except Exception as e:
            logger.error(f"Failed to update metrics: {str(e)}")

        # Wait 60 seconds before next update
        await asyncio.sleep(60)


def setup_background_tasks(app: FastAPI):
    """Setup background tasks for the application."""

    @app.on_event("startup")
    async def start_background_tasks():
        """Start background tasks on application startup."""
        # Start periodic metrics update task
        asyncio.create_task(periodic_metrics_update())
        logger.info("Background tasks started")


# Health check functions for dependencies
async def check_database_health() -> tuple[bool, str]:
    """Check database connection health."""
    try:
        async with AsyncSession(engine) as session:
            await session.execute(select(1))
            return True, "Database connection successful"
    except Exception as e:
        return False, f"Database connection failed: {str(e)}"


async def check_redis_health() -> tuple[bool, str]:
    """Check Redis connection health."""
    try:
        import redis.asyncio as redis
        redis_client = redis.from_url(settings.redis_url)
        await redis_client.ping()
        await redis_client.close()
        return True, "Redis connection successful"
    except Exception as e:
        return False, f"Redis connection failed: {str(e)}"


async def get_system_stats() -> dict:
    """Get system statistics for monitoring."""
    try:
        async with AsyncSession(engine) as session:
            # Get workspace statistics
            total_workspaces = await session.scalar(select(func.count(Workspace.id)))
            active_workspaces = await session.scalar(
                select(func.count(Workspace.id)).where(Workspace.is_active == True)
            )

            # Get user statistics
            total_users = await session.scalar(select(func.count(User.id)))
            active_users = await session.scalar(
                select(func.count(User.id)).where(User.is_active == True)
            )

            return {
                "workspaces": {
                    "total": total_workspaces or 0,
                    "active": active_workspaces or 0
                },
                "users": {
                    "total": total_users or 0,
                    "active": active_users or 0
                }
            }
    except Exception as e:
        logger.error(f"Failed to get system stats: {str(e)}")
        return {
            "workspaces": {"total": 0, "active": 0},
            "users": {"total": 0, "active": 0}
        }
