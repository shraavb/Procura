"""
Production middleware for FastAPI.
Includes rate limiting, request context, and error handling.
"""
import time
import uuid
from typing import Callable
from collections.abc import Awaitable

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.logging import request_id_ctx, get_logger
from core.cache import get_cache
from core.validation import SECURITY_HEADERS
from config import get_settings

settings = get_settings()
logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Add request context for tracing and logging.
    Sets request ID and tracks request duration.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Generate or get request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_ctx.set(request_id)

        # Track timing
        start_time = time.perf_counter()

        try:
            response = await call_next(request)

            # Add headers
            response.headers["X-Request-ID"] = request_id
            duration = time.perf_counter() - start_time
            response.headers["X-Response-Time"] = f"{duration:.3f}s"

            # Add security headers
            for header, value in SECURITY_HEADERS.items():
                response.headers[header] = value

            # Log request (skip health checks)
            if not request.url.path.startswith("/api/health"):
                logger.info(
                    f"{request.method} {request.url.path} - {response.status_code} ({duration:.3f}s)"
                )

            return response

        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(
                f"{request.method} {request.url.path} - Error ({duration:.3f}s): {e}",
                exc_info=True,
            )
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Redis-based rate limiting middleware.
    Implements sliding window rate limiting per IP address.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        # Skip rate limiting for health checks
        if request.url.path.startswith("/api/health"):
            return await call_next(request)

        # Get client IP
        client_ip = self._get_client_ip(request)
        cache = get_cache()

        if cache:
            # Check rate limit
            key = f"ratelimit:{client_ip}"
            current = await cache.get(key)

            if current and int(current) >= settings.rate_limit_requests:
                logger.warning(f"Rate limit exceeded for {client_ip}")
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded",
                        "retry_after": settings.rate_limit_window,
                    },
                    headers={
                        "Retry-After": str(settings.rate_limit_window),
                        "X-RateLimit-Limit": str(settings.rate_limit_requests),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            # Increment counter
            await cache.incr(key)
            if not current:
                await cache.expire(key, settings.rate_limit_window)

            remaining = settings.rate_limit_requests - (int(current or 0) + 1)
        else:
            remaining = settings.rate_limit_requests

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, handling proxies."""
        # Check X-Forwarded-For header (reverse proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client
        return request.client.host if request.client else "unknown"


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware.
    Catches unhandled exceptions and returns proper JSON responses.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            return await call_next(request)
        except HTTPException:
            # Let FastAPI handle HTTP exceptions
            raise
        except Exception as e:
            request_id = request_id_ctx.get()
            logger.error(f"Unhandled error: {e}", exc_info=True)

            # Don't expose internal errors in production
            if settings.is_production:
                detail = "Internal server error"
            else:
                detail = str(e)

            return JSONResponse(
                status_code=500,
                content={
                    "detail": detail,
                    "request_id": request_id,
                },
            )
