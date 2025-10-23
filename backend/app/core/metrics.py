"""
Prometheus metrics configuration for monitoring.
"""
import time
from typing import Any, Dict

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

# Application info
app_info = Info('app_info', 'Application information')
app_info.info({
    'version': '1.0.0',
    'name': 'FastAPI Cloud Workspaces'
})

# Request metrics
request_count = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

request_size = Histogram(
    'http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint']
)

response_size = Histogram(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint']
)

# Active requests gauge
active_requests = Gauge(
    'http_requests_active',
    'Number of active HTTP requests'
)

# Database metrics
db_connections_active = Gauge(
    'db_connections_active',
    'Number of active database connections'
)

db_query_duration = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['operation']
)

db_query_count = Counter(
    'db_queries_total',
    'Total database queries',
    ['operation', 'status']
)

# Celery metrics
celery_task_count = Counter(
    'celery_tasks_total',
    'Total Celery tasks',
    ['task_name', 'status']
)

celery_task_duration = Histogram(
    'celery_task_duration_seconds',
    'Celery task duration in seconds',
    ['task_name']
)

celery_queue_size = Gauge(
    'celery_queue_size',
    'Number of tasks in Celery queue',
    ['queue_name']
)

# Storage metrics
storage_operations = Counter(
    'storage_operations_total',
    'Total storage operations',
    ['operation', 'status']
)

storage_bytes_transferred = Counter(
    'storage_bytes_transferred_total',
    'Total bytes transferred in storage operations',
    ['operation']
)

# Workspace metrics
workspace_count = Gauge(
    'workspaces_total',
    'Total number of workspaces'
)

active_users = Gauge(
    'users_active',
    'Number of active users'
)

# Authentication metrics
auth_attempts = Counter(
    'auth_attempts_total',
    'Total authentication attempts',
    ['status']
)

token_validations = Counter(
    'token_validations_total',
    'Total token validations',
    ['status']
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to collect Prometheus metrics."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip metrics collection for the metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        # Increment active requests
        active_requests.inc()

        # Get request size
        content_length = request.headers.get("content-length")
        if content_length:
            request_size.labels(
                method=request.method,
                endpoint=self._get_endpoint_name(request)
            ).observe(int(content_length))

        # Start timing
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Get endpoint name
            endpoint = self._get_endpoint_name(request)

            # Record metrics
            request_count.labels(
                method=request.method,
                endpoint=endpoint,
                status_code=response.status_code
            ).inc()

            request_duration.labels(
                method=request.method,
                endpoint=endpoint
            ).observe(duration)

            # Get response size
            content_length = response.headers.get("content-length")
            if content_length:
                response_size.labels(
                    method=request.method,
                    endpoint=endpoint
                ).observe(int(content_length))

            return response

        except Exception as e:
            # Calculate duration
            duration = time.time() - start_time

            # Record error metrics
            endpoint = self._get_endpoint_name(request)
            request_count.labels(
                method=request.method,
                endpoint=endpoint,
                status_code=500
            ).inc()

            request_duration.labels(
                method=request.method,
                endpoint=endpoint
            ).observe(duration)

            raise e

        finally:
            # Decrement active requests
            active_requests.dec()

    def _get_endpoint_name(self, request: Request) -> str:
        """Get normalized endpoint name for metrics."""
        path = request.url.path

        # Normalize common patterns
        if path.startswith("/api/v1/"):
            parts = path.split("/")
            if len(parts) >= 4:
                # Replace IDs with placeholder
                normalized_parts = []
                for i, part in enumerate(parts):
                    if i >= 4 and part and not part.isalpha():
                        # This looks like an ID, replace with placeholder
                        normalized_parts.append("{id}")
                    else:
                        normalized_parts.append(part)
                return "/".join(normalized_parts)

        return path


def record_db_query(operation: str, duration: float, success: bool = True):
    """Record database query metrics."""
    status = "success" if success else "error"
    db_query_count.labels(operation=operation, status=status).inc()
    db_query_duration.labels(operation=operation).observe(duration)


def record_celery_task(task_name: str, duration: float, success: bool = True):
    """Record Celery task metrics."""
    status = "success" if success else "error"
    celery_task_count.labels(task_name=task_name, status=status).inc()
    celery_task_duration.labels(task_name=task_name).observe(duration)


def record_storage_operation(operation: str, bytes_transferred: int = 0, success: bool = True):
    """Record storage operation metrics."""
    status = "success" if success else "error"
    storage_operations.labels(operation=operation, status=status).inc()
    if bytes_transferred > 0:
        storage_bytes_transferred.labels(operation=operation).inc(bytes_transferred)


def record_auth_attempt(success: bool = True):
    """Record authentication attempt metrics."""
    status = "success" if success else "failure"
    auth_attempts.labels(status=status).inc()


def record_token_validation(success: bool = True):
    """Record token validation metrics."""
    status = "success" if success else "failure"
    token_validations.labels(status=status).inc()


def update_workspace_count(count: int):
    """Update workspace count gauge."""
    workspace_count.set(count)


def update_active_users(count: int):
    """Update active users gauge."""
    active_users.set(count)


def update_db_connections(count: int):
    """Update database connections gauge."""
    db_connections_active.set(count)


def update_celery_queue_size(queue_name: str, size: int):
    """Update Celery queue size gauge."""
    celery_queue_size.labels(queue_name=queue_name).set(size)


def get_metrics() -> str:
    """Get Prometheus metrics in text format."""
    return generate_latest()


def get_metrics_content_type() -> str:
    """Get Prometheus metrics content type."""
    return CONTENT_TYPE_LATEST
