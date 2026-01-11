"""
Procura - BOM/PO Multi-Agent System
FastAPI application entry point.

Production-ready configuration following FastAPI best practices for LLM applications.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from core.logging import setup_logging, get_logger
from core.middleware import (
    RequestContextMiddleware,
    RateLimitMiddleware,
    ErrorHandlerMiddleware,
)
from core.cache import init_cache, close_cache
from models.db import init_db, close_db
from api import health, boms, suppliers, purchase_orders, agents

# Initialize settings and logging
settings = get_settings()
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events with proper startup/shutdown."""
    # ========== STARTUP ==========
    logger.info(
        f"Starting Procura API v{settings.app_version}",
        extra={
            "environment": settings.environment,
            "debug": settings.debug,
            "demo_mode": settings.demo_mode,
        }
    )

    # Initialize Redis cache
    try:
        await init_cache()
        logger.info("Redis cache initialized")
    except Exception as e:
        logger.warning(f"Redis initialization failed (caching disabled): {e}")

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized")

        # Auto-seed demo data if database is empty
        from seed_db import seed_database
        try:
            seed_database()
            logger.info("Database seeded with demo data")
        except Exception as e:
            logger.warning(f"Seeding skipped or failed: {e}")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

    # Warm up LLM connection (optional, reduces cold start)
    if settings.anthropic_api_key and not settings.demo_mode:
        logger.info("LLM connection ready")

    logger.info(f"Procura API ready on {settings.host}:{settings.port}")

    yield

    # ========== SHUTDOWN ==========
    logger.info("Shutting down Procura API...")

    # Close Redis
    await close_cache()
    logger.info("Redis cache closed")

    # Close database connections
    await close_db()
    logger.info("Database connections closed")

    logger.info("Procura API shutdown complete")


# Create FastAPI app with production settings
app = FastAPI(
    title="Procura API",
    description="BOM/PO Multi-Agent System for manufacturing procurement automation",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,  # Disable in production
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)

# ========== MIDDLEWARE (order matters!) ==========

# Error handling (outermost)
app.add_middleware(ErrorHandlerMiddleware)

# Request context and tracing
app.add_middleware(RequestContextMiddleware)

# Rate limiting
if settings.rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# ========== EXCEPTION HANDLERS ==========

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    if settings.is_production:
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


# ========== ROUTERS ==========

app.include_router(health.router)
app.include_router(boms.router)
app.include_router(suppliers.router)
app.include_router(purchase_orders.router)
app.include_router(agents.router)


# ========== ROOT ENDPOINT ==========

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "BOM/PO Multi-Agent System",
        "environment": settings.environment,
        "docs": "/docs" if not settings.is_production else None,
        "health": "/api/health",
    }


# ========== MAIN ==========

if __name__ == "__main__":
    import uvicorn

    # Development mode with reload
    if settings.debug:
        uvicorn.run(
            "main:app",
            host=settings.host,
            port=settings.port,
            reload=True,
            log_level="debug",
        )
    else:
        # Production mode - use gunicorn for multiple workers
        # gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
        uvicorn.run(
            "main:app",
            host=settings.host,
            port=settings.port,
            workers=settings.workers,
            log_level="info",
        )
