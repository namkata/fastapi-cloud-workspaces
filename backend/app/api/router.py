"""
Main API router registry.
"""
from fastapi import APIRouter

from .v1.router import v1_router

# Create main API router
api_router = APIRouter(prefix="/api")

# Include version routers
api_router.include_router(v1_router)


@api_router.get("/health")
async def root_health_check():
    """Root health check endpoint."""
    return {"status": "healthy", "message": "FastAPI Cloud Workspaces API"}


@api_router.get("/versions")
async def api_versions():
    """Get available API versions."""
    return {
        "versions": [
            {
                "version": "v1",
                "status": "stable",
                "path": "/api/v1"
            }
        ],
        "current": "v1"
    }
