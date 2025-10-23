"""
FastAPI Cloud Workspaces - Main Application Entry Point
"""
from app.api.router import api_router
from app.core.config import settings
from app.core.events import lifespan, setup_background_tasks
from app.core.exceptions import setup_exception_handlers
from app.core.logger import get_logger
from app.core.metrics import PrometheusMiddleware
from app.core.middleware import setup_middleware
from app.core.openapi import setup_custom_openapi
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

logger = get_logger(__name__)


def create_application() -> FastAPI:
    """Create and configure FastAPI application."""

    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url=None,  # Disable default docs
        redoc_url="/redoc",
        swagger_ui_parameters={
            "tryItOutEnabled": True,
            "persistAuthorization": True,
        },
    )

    # Setup middleware stack
    setup_middleware(app)

    # Setup exception handlers
    setup_exception_handlers(app)

    # Add Prometheus metrics middleware
    app.add_middleware(PrometheusMiddleware)

    # Include API router
    app.include_router(api_router)

    # Mount static files for Swagger UI
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Setup background tasks
    setup_background_tasks(app)

    # Setup custom OpenAPI schema with OPTIONS methods
    setup_custom_openapi(app)

    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "message": "FastAPI Cloud Workspaces API",
            "version": settings.app_version,
            "environment": settings.environment,
            "docs_url": "/docs" if settings.is_development else None,
            "api_version": "v1"
        }

    @app.get("/health")
    async def health():
        """Simple health check."""
        return {"status": "healthy"}

    # Custom Swagger UI endpoint
    from fastapi.openapi.docs import get_swagger_ui_html
    from fastapi.responses import HTMLResponse

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        """Custom Swagger UI with local assets."""
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=app.title + " - Swagger UI",
            swagger_js_url="/static/swagger-ui-bundle.js",
            swagger_css_url="/static/swagger-ui.css",
            swagger_ui_parameters={
                "tryItOutEnabled": True,
                "persistAuthorization": True,
            }
        )

    logger.info("FastAPI application created and configured")
    return app


# Create application instance
app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_config=None,  # Use our custom logging
    )
