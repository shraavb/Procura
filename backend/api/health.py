"""
Health check endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from models.db import get_db
from config import get_settings

router = APIRouter(prefix="/api/health", tags=["health"])
settings = get_settings()


@router.get("")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "service": "procura-api",
        "version": "1.0.0",
    }


@router.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness check including database connectivity."""
    checks = {
        "database": False,
        "llm_configured": False,
        "embeddings_configured": False,
    }

    # Check database
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass

    # Check LLM configuration
    checks["llm_configured"] = bool(settings.anthropic_api_key)

    # Check embeddings configuration
    checks["embeddings_configured"] = bool(settings.openai_api_key)

    all_healthy = all(checks.values())

    return {
        "status": "ready" if all_healthy else "degraded",
        "checks": checks,
    }
