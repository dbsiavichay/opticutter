from fastapi import APIRouter

from src.core.config import config

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def api_health():
    return {"status": "healthy", "environment": config.ENVIRONMENT, "version": "1.0.0"}


@router.get("/ready")
async def api_ready():
    checks = {
        "redis": True,
    }
    return {"status": "ready", "checks": checks}
