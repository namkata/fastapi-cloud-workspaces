"""
Health check and metrics endpoints.
"""
import asyncio
from datetime import datetime
from typing import Any, Dict

import redis.asyncio as redis
from app.core.config import settings
from app.core.database import get_db_session
from app.core.metrics import (
    get_metrics,
    get_metrics_content_type,
    update_active_users,
    update_db_connections,
    update_workspace_count,
)
from app.modules.auth.models import User
from app.modules.workspace.models import Workspace
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


@router.get("/health/detailed")
async def detailed_health_check(
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Detailed health check with dependency status."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "checks": {}
    }

    overall_healthy = True

    # Database health check
    try:
        result = await db.execute(text("SELECT 1"))
        result.fetchone()
        health_status["checks"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful"
        }
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}"
        }
        overall_healthy = False

    # Redis health check
    try:
        redis_client = redis.from_url(settings.redis_url)
        await redis_client.ping()
        await redis_client.close()
        health_status["checks"]["redis"] = {
            "status": "healthy",
            "message": "Redis connection successful"
        }
    except Exception as e:
        health_status["checks"]["redis"] = {
            "status": "unhealthy",
            "message": f"Redis connection failed: {str(e)}"
        }
        overall_healthy = False

    # Update overall status
    if not overall_healthy:
        health_status["status"] = "unhealthy"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_status
        )

    return health_status


@router.get("/health/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Readiness check for Kubernetes."""
    try:
        # Check database connection
        await db.execute(text("SELECT 1"))

        # Check Redis connection
        redis_client = redis.from_url(settings.redis_url)
        await redis_client.ping()
        await redis_client.close()

        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/health/live")
async def liveness_check():
    """Liveness check for Kubernetes."""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/metrics")
async def get_prometheus_metrics(
    db: AsyncSession = Depends(get_db_session)
):
    """Prometheus metrics endpoint."""
    try:
        # Update dynamic metrics before returning
        await update_dynamic_metrics(db)

        # Return metrics in Prometheus format
        metrics_data = get_metrics()
        return Response(
            content=metrics_data,
            media_type=get_metrics_content_type()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate metrics: {str(e)}"
        )


@router.get("/stats")
async def get_application_stats(
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Get application statistics."""
    try:
        # Get workspace count
        workspace_count_result = await db.execute(
            select(func.count(Workspace.id))
        )
        workspace_count = workspace_count_result.scalar() or 0

        # Get active users count (users who logged in within last 30 days)
        thirty_days_ago = datetime.utcnow().replace(day=datetime.utcnow().day - 30)
        active_users_result = await db.execute(
            select(func.count(User.id)).where(
                User.is_active == True,
                User.last_login >= thirty_days_ago
            )
        )
        active_users_count = active_users_result.scalar() or 0

        # Get total users count
        total_users_result = await db.execute(
            select(func.count(User.id))
        )
        total_users_count = total_users_result.scalar() or 0

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "workspaces": {
                "total": workspace_count
            },
            "users": {
                "total": total_users_count,
                "active": active_users_count
            },
            "system": {
                "environment": settings.environment,
                "version": "1.0.0"
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )


async def update_dynamic_metrics(db: AsyncSession):
    """Update dynamic Prometheus metrics."""
    try:
        # Update workspace count
        workspace_count_result = await db.execute(
            select(func.count(Workspace.id))
        )
        workspace_count = workspace_count_result.scalar() or 0
        update_workspace_count(workspace_count)

        # Update active users count
        thirty_days_ago = datetime.utcnow().replace(day=max(1, datetime.utcnow().day - 30))
        active_users_result = await db.execute(
            select(func.count(User.id)).where(
                User.is_active == True,
                User.last_login >= thirty_days_ago
            )
        )
        active_users_count = active_users_result.scalar() or 0
        update_active_users(active_users_count)

        # Update database connections (approximate)
        # In a real scenario, you'd get this from the connection pool
        update_db_connections(5)  # Placeholder value

    except Exception as e:
        # Log error but don't fail the metrics endpoint
        print(f"Error updating dynamic metrics: {e}")
        pass
