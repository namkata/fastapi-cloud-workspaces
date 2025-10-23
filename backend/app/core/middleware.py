"""
Middleware stack for the FastAPI application.
"""
import json
import time
import uuid
from typing import Callable, Optional

from app.core.config import settings
from app.core.database import get_db_session
from app.core.logger import logger
from app.core.rate_limiting import RateLimitMiddleware
from app.modules.auth.service import AuthService
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

security = HTTPBearer(auto_error=False)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Start timing
        start_time = time.time()

        # Log request
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "content_length": request.headers.get("content-length")
            }
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Log response
            logger.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "response_size": response.headers.get("content-length")
                }
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Calculate duration
            duration = time.time() - start_time

            # Log error
            logger.error(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "duration_ms": round(duration * 1000, 2)
                },
                exc_info=True
            )

            # Return error response
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error", "request_id": request_id},
                headers={"X-Request-ID": request_id}
            )


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware for authentication and user context."""

    # Paths that don't require authentication
    EXEMPT_PATHS = {
        "/health",
        "/versions",
        "/api/v1/health",
        "/api/v1/info",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/verify-email",
        "/docs",
        "/redoc",
        "/openapi.json"
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip authentication for exempt paths
        if request.url.path in self.EXEMPT_PATHS or request.url.path.startswith("/static"):
            return await call_next(request)

        # Extract token from Authorization header
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            # For non-API paths, just continue without user context
            if not request.url.path.startswith("/api/"):
                return await call_next(request)

            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid authorization header"}
            )

        token = authorization.split(" ")[1]

        try:
            # Get database session
            db_gen = get_db_session()
            session = await anext(db_gen)

            try:
                auth_service = AuthService(session)
                user = await auth_service.get_current_user(token)

                if not user:
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Invalid token"}
                    )

                if not user.is_active:
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "User account is disabled"}
                    )

                # Add user to request state
                request.state.current_user = user

                # Log authenticated request
                logger.info(
                    "Authenticated request",
                    extra={
                        "request_id": getattr(request.state, "request_id", None),
                        "user_id": user.id,
                        "user_email": user.email
                    }
                )

                return await call_next(request)

            finally:
                await session.close()

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication failed"}
            )


class WorkspaceContextMiddleware(BaseHTTPMiddleware):
    """Middleware for workspace context extraction."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract workspace_id from path parameters
        path_parts = request.url.path.split("/")
        workspace_id = None

        # Look for workspace_id in path (e.g., /api/v1/workspaces/{workspace_id}/...)
        if "workspaces" in path_parts:
            try:
                workspace_idx = path_parts.index("workspaces")
                if workspace_idx + 1 < len(path_parts):
                    workspace_id = path_parts[workspace_idx + 1]
            except (ValueError, IndexError):
                pass

        # Also check storage paths (e.g., /api/v1/storage/{workspace_id}/...)
        elif "storage" in path_parts:
            try:
                storage_idx = path_parts.index("storage")
                if storage_idx + 1 < len(path_parts):
                    workspace_id = path_parts[storage_idx + 1]
            except (ValueError, IndexError):
                pass

        # Add workspace context to request state
        if workspace_id:
            request.state.workspace_id = workspace_id

            logger.debug(
                "Workspace context set",
                extra={
                    "request_id": getattr(request.state, "request_id", None),
                    "workspace_id": workspace_id
                }
            )

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Add CSP header for non-API requests
        if not request.url.path.startswith("/api/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self'"
            )

        return response


def setup_middleware(app: FastAPI) -> None:
    """Setup all middleware for the FastAPI application."""

    # Security headers (first)
    app.add_middleware(SecurityHeadersMiddleware)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"]
    )

    # Trusted host middleware
    if settings.allowed_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_hosts
        )

    # Custom middleware (in order of execution)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware, default_requests_per_minute=120, burst_capacity=20)
    app.add_middleware(AuthenticationMiddleware)
    app.add_middleware(WorkspaceContextMiddleware)

    logger.info("Middleware stack configured successfully")
