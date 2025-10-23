"""
API v1 router registry.
"""
from fastapi import APIRouter

from .auth import router as auth_router
from .health import router as health_router
from .storage import router as storage_router
from .users import router as users_router
from .workspaces import router as workspaces_router

# Create v1 router
v1_router = APIRouter(prefix="/v1")

# Include all v1 routers
v1_router.include_router(auth_router, tags=["Authentication"])
v1_router.include_router(users_router, prefix="/users", tags=["Users"])
v1_router.include_router(workspaces_router, prefix="/workspaces", tags=["Workspaces"])
v1_router.include_router(storage_router, prefix="/storage", tags=["Storage"])
v1_router.include_router(health_router, tags=["Health & Monitoring"])

# Health check endpoint
@v1_router.get("/health")
async def health_check():
    """Simple health check for v1 API."""
    return {"status": "healthy", "version": "v1"}

# API information endpoint
@v1_router.get("/info")
async def api_info():
    """Get API v1 information."""
    return {
        "version": "v1",
        "name": "FastAPI Cloud Workspaces API",
        "endpoints": {
            "auth": "/api/v1/auth",
            "users": "/api/v1/users",
            "workspaces": "/api/v1/workspaces",
            "storage": "/api/v1/storage",
            "health": "/api/v1/health",
            "metrics": "/api/v1/metrics"
        }
    }
