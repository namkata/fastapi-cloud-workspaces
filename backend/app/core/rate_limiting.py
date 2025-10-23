"""
Rate limiting middleware and utilities for FastAPI application.

This module provides rate limiting functionality to protect against abuse
and ensure fair usage of API resources.
"""
import asyncio
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, Optional

from app.core.exceptions import RateLimitException
from app.core.logger import get_logger
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = get_logger(__name__)


class TokenBucket:
    """Token bucket algorithm implementation for rate limiting."""

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum number of tokens in the bucket
            refill_rate: Number of tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False otherwise
        """
        now = time.time()

        # Add tokens based on time elapsed
        time_passed = now - self.last_refill
        self.tokens = min(
            self.capacity,
            self.tokens + time_passed * self.refill_rate
        )
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class SlidingWindowCounter:
    """Sliding window counter for rate limiting."""

    def __init__(self, window_size: int, max_requests: int):
        """
        Initialize sliding window counter.

        Args:
            window_size: Window size in seconds
            max_requests: Maximum requests allowed in the window
        """
        self.window_size = window_size
        self.max_requests = max_requests
        self.requests = deque()

    def is_allowed(self) -> bool:
        """
        Check if a request is allowed.

        Returns:
            True if request is allowed, False otherwise
        """
        now = time.time()

        # Remove old requests outside the window
        while self.requests and self.requests[0] <= now - self.window_size:
            self.requests.popleft()

        # Check if we're under the limit
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True

        return False


class RateLimiter:
    """Main rate limiter class managing different algorithms."""

    def __init__(self):
        self.buckets: Dict[str, TokenBucket] = {}
        self.counters: Dict[str, SlidingWindowCounter] = {}
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()

    def _cleanup_old_entries(self):
        """Clean up old rate limiting entries."""
        now = time.time()
        if now - self.last_cleanup < self.cleanup_interval:
            return

        # Clean up token buckets that haven't been used recently
        keys_to_remove = []
        for key, bucket in self.buckets.items():
            if now - bucket.last_refill > self.cleanup_interval:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.buckets[key]

        # Clean up sliding window counters
        keys_to_remove = []
        for key, counter in self.counters.items():
            if not counter.requests or now - counter.requests[-1] > counter.window_size:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.counters[key]

        self.last_cleanup = now

    def check_rate_limit_bucket(
        self,
        identifier: str,
        capacity: int,
        refill_rate: float,
        tokens: int = 1
    ) -> bool:
        """
        Check rate limit using token bucket algorithm.

        Args:
            identifier: Unique identifier for the rate limit
            capacity: Bucket capacity
            refill_rate: Tokens per second refill rate
            tokens: Number of tokens to consume

        Returns:
            True if request is allowed, False otherwise
        """
        self._cleanup_old_entries()

        if identifier not in self.buckets:
            self.buckets[identifier] = TokenBucket(capacity, refill_rate)

        return self.buckets[identifier].consume(tokens)

    def check_rate_limit_window(
        self,
        identifier: str,
        window_size: int,
        max_requests: int
    ) -> bool:
        """
        Check rate limit using sliding window algorithm.

        Args:
            identifier: Unique identifier for the rate limit
            window_size: Window size in seconds
            max_requests: Maximum requests in the window

        Returns:
            True if request is allowed, False otherwise
        """
        self._cleanup_old_entries()

        if identifier not in self.counters:
            self.counters[identifier] = SlidingWindowCounter(window_size, max_requests)

        return self.counters[identifier].is_allowed()


# Global rate limiter instance
rate_limiter = RateLimiter()


def get_client_identifier(request: Request) -> str:
    """
    Get client identifier for rate limiting.

    Args:
        request: FastAPI request object

    Returns:
        Client identifier string
    """
    # Try to get user ID from request state (if authenticated)
    user = getattr(request.state, 'user', None)
    if user:
        return f"user:{user.id}"

    # Fall back to IP address
    client_ip = request.client.host if request.client else "unknown"

    # Check for forwarded IP headers
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        client_ip = real_ip

    return f"ip:{client_ip}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for applying rate limits to requests."""

    def __init__(
        self,
        app,
        default_requests_per_minute: int = 60,
        burst_capacity: int = 10,
        excluded_paths: Optional[list] = None
    ):
        """
        Initialize rate limit middleware.

        Args:
            app: FastAPI application
            default_requests_per_minute: Default rate limit per minute
            burst_capacity: Burst capacity for token bucket
            excluded_paths: Paths to exclude from rate limiting
        """
        super().__init__(app)
        self.default_requests_per_minute = default_requests_per_minute
        self.burst_capacity = burst_capacity
        self.excluded_paths = set(excluded_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json"
        ])

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""

        # Skip rate limiting for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # Get client identifier
        client_id = get_client_identifier(request)

        # Apply rate limiting using token bucket
        refill_rate = self.default_requests_per_minute / 60.0  # tokens per second

        if not rate_limiter.check_rate_limit_bucket(
            identifier=f"global:{client_id}",
            capacity=self.burst_capacity,
            refill_rate=refill_rate
        ):
            logger.warning(
                "Rate limit exceeded",
                client_id=client_id,
                path=request.url.path,
                method=request.method
            )

            raise RateLimitException("Rate limit exceeded. Please try again later.")

        # Add rate limit headers to response
        response = await call_next(request)

        # Add rate limiting headers
        response.headers["X-RateLimit-Limit"] = str(self.default_requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, int(rate_limiter.buckets.get(f"global:{client_id}", TokenBucket(self.burst_capacity, refill_rate)).tokens))
        )
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + 60))

        return response


def rate_limit(
    requests_per_minute: int = 60,
    window_size: int = 60,
    per_user: bool = True,
    key_func: Optional[Callable[[Request], str]] = None
):
    """
    Decorator for applying rate limits to specific endpoints.

    Args:
        requests_per_minute: Number of requests allowed per minute
        window_size: Window size in seconds
        per_user: Whether to apply rate limit per user or per IP
        key_func: Custom function to generate rate limit key
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find the request object in the arguments
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if not request:
                # If no request found, proceed without rate limiting
                return await func(*args, **kwargs)

            # Generate rate limit key
            if key_func:
                rate_limit_key = key_func(request)
            else:
                client_id = get_client_identifier(request)
                endpoint = f"{request.method}:{request.url.path}"
                rate_limit_key = f"{endpoint}:{client_id}"

            # Check rate limit
            if not rate_limiter.check_rate_limit_window(
                identifier=rate_limit_key,
                window_size=window_size,
                max_requests=requests_per_minute
            ):
                logger.warning(
                    "Endpoint rate limit exceeded",
                    key=rate_limit_key,
                    path=request.url.path,
                    method=request.method
                )

                raise RateLimitException(
                    f"Rate limit exceeded for this endpoint. "
                    f"Maximum {requests_per_minute} requests per minute allowed."
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


# Predefined rate limit decorators for common use cases
strict_rate_limit = rate_limit(requests_per_minute=10, window_size=60)
auth_rate_limit = rate_limit(requests_per_minute=5, window_size=300)  # 5 requests per 5 minutes
api_rate_limit = rate_limit(requests_per_minute=100, window_size=60)
