"""
Structured logging configuration using structlog and rich.
"""
import logging
import sys
from typing import Any, Dict

import structlog
from rich.console import Console
from rich.logging import RichHandler

from .config import settings


def configure_logging() -> None:
    """Configure structured logging for the application."""

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )

    # Configure processors based on environment
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]

    if settings.is_development:
        # Development: Use rich console output
        processors.extend([
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=True)
        ])

        # Configure rich handler for better development experience
        rich_handler = RichHandler(
            console=Console(stderr=True),
            show_time=True,
            show_path=True,
            markup=True,
            rich_tracebacks=True,
        )

        # Configure root logger with rich handler
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.addHandler(rich_handler)

    else:
        # Production: Use JSON output
        processors.extend([
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ])

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper())
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def log_request_middleware(request_id: str, method: str, url: str, **kwargs: Any) -> Dict[str, Any]:
    """Log HTTP request with structured data."""
    return {
        "request_id": request_id,
        "method": method,
        "url": str(url),
        "event": "http_request",
        **kwargs
    }


def log_response_middleware(
    request_id: str,
    status_code: int,
    duration_ms: float,
    **kwargs: Any
) -> Dict[str, Any]:
    """Log HTTP response with structured data."""
    return {
        "request_id": request_id,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "event": "http_response",
        **kwargs
    }


def log_database_query(query: str, duration_ms: float, **kwargs: Any) -> Dict[str, Any]:
    """Log database query with structured data."""
    return {
        "query": query,
        "duration_ms": round(duration_ms, 2),
        "event": "database_query",
        **kwargs
    }


def log_error(error: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Log error with structured data."""
    return {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context or {},
        "event": "error",
    }


# Initialize logging on module import
configure_logging()

# Export main logger
logger = get_logger(__name__)
