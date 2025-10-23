"""
Workspace context middleware.

This middleware extracts the X-Workspace-ID header from requests and attaches
workspace context to the request state for workspace isolation.
"""
from typing import Optional
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from structlog import get_logger

logger = get_logger(__name__)


class WorkspaceContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle workspace context isolation.

    This middleware:
    1. Extracts X-Workspace-ID header from requests
    2. Validates the workspace ID format
    3. Attaches workspace context to request state
    4. Provides workspace isolation for database operations
    """

    def __init__(self, app, require_workspace_header: bool = False):
        """
        Initialize workspace context middleware.

        Args:
            app: FastAPI application instance
            require_workspace_header: Whether to require X-Workspace-ID header for all requests
        """
        super().__init__(app)
        self.require_workspace_header = require_workspace_header

        # Paths that don't require workspace context
        self.excluded_paths = {
            "/",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/api/v1/auth/logout",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/verify-email",
            "/api/v1/workspaces",  # Workspace listing doesn't require specific workspace context
        }

    async def dispatch(self, request: Request, call_next):
        """
        Process the request and attach workspace context.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint in the chain

        Returns:
            HTTP response
        """
        # Skip workspace context for excluded paths
        if self._should_skip_workspace_context(request):
            return await call_next(request)

        # Extract workspace ID from header
        workspace_id = self._extract_workspace_id(request)

        # Attach workspace context to request state
        request.state.workspace_id = workspace_id
        request.state.has_workspace_context = workspace_id is not None

        # Log workspace context
        if workspace_id:
            logger.debug(
                "Workspace context attached",
                workspace_id=str(workspace_id),
                path=request.url.path,
                method=request.method
            )
        else:
            logger.debug(
                "No workspace context",
                path=request.url.path,
                method=request.method
            )

        # Validate workspace requirement if configured
        if self.require_workspace_header and not workspace_id and not self._should_skip_workspace_context(request):
            logger.warning(
                "Missing required workspace header",
                path=request.url.path,
                method=request.method,
                require_workspace_header=self.require_workspace_header,
                should_skip=self._should_skip_workspace_context(request)
            )
            return Response(
                content='{"detail": "X-Workspace-ID header is required"}',
                status_code=400,
                media_type="application/json"
            )

        # Continue to next middleware/endpoint
        response = await call_next(request)

        # Add workspace ID to response headers for debugging
        if workspace_id:
            response.headers["X-Current-Workspace"] = str(workspace_id)

        return response

    def _should_skip_workspace_context(self, request: Request) -> bool:
        """
        Determine if workspace context should be skipped for this request.

        Args:
            request: HTTP request

        Returns:
            True if workspace context should be skipped, False otherwise
        """
        path = request.url.path

        # Skip for excluded paths
        if path in self.excluded_paths:
            return True

        # Skip for static files and docs
        if path.startswith("/static/") or path.startswith("/docs") or path.startswith("/redoc"):
            return True

        # Skip for health checks and monitoring
        if path.startswith("/health") or path.startswith("/metrics"):
            return True

        # Skip for authentication endpoints
        if path.startswith("/api/v1/auth/"):
            return True

        # Skip for workspace creation and listing (these don't require specific workspace context)
        if path == "/api/v1/workspaces" and request.method in ["GET", "POST"]:
            return True

        return False

    def _extract_workspace_id(self, request: Request) -> Optional[UUID]:
        """
        Extract workspace ID from request headers.

        Args:
            request: HTTP request

        Returns:
            Workspace UUID if valid header present, None otherwise
        """
        # Try different header variations
        workspace_header = (
            request.headers.get("X-Workspace-ID") or
            request.headers.get("x-workspace-id") or
            request.headers.get("Workspace-ID") or
            request.headers.get("workspace-id")
        )

        if not workspace_header:
            return None

        try:
            # Validate UUID format
            workspace_id = UUID(workspace_header)
            return workspace_id
        except (ValueError, TypeError) as e:
            logger.warning(
                "Invalid workspace ID format",
                workspace_header=workspace_header,
                error=str(e),
                path=request.url.path
            )
            return None


def get_workspace_context(request: Request) -> Optional[UUID]:
    """
    Get workspace context from request state.

    Args:
        request: HTTP request

    Returns:
        Workspace UUID if available, None otherwise
    """
    return getattr(request.state, "workspace_id", None)


def has_workspace_context(request: Request) -> bool:
    """
    Check if request has workspace context.

    Args:
        request: HTTP request

    Returns:
        True if workspace context is available, False otherwise
    """
    return getattr(request.state, "has_workspace_context", False)


def require_workspace_context(request: Request) -> UUID:
    """
    Require workspace context from request state.

    Args:
        request: HTTP request

    Returns:
        Workspace UUID

    Raises:
        ValueError: If workspace context is not available
    """
    workspace_id = get_workspace_context(request)
    if not workspace_id:
        raise ValueError("Workspace context is required but not available")
    return workspace_id
