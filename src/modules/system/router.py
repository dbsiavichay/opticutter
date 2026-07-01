"""Cross-cutting system routes: health checks and API information."""

from fastapi import APIRouter

from src.shared.config import config

router = APIRouter()

health_router = APIRouter(prefix="/health", tags=["health"])
cutter_router = APIRouter(prefix="/cutter", tags=["cutter"])


@health_router.get("/")
async def api_health():
    """Basic service status."""
    return {"status": "healthy", "environment": config.ENVIRONMENT, "version": "1.0.0"}


@health_router.get("/ready")
async def api_ready():
    """Readiness check (service dependencies)."""
    checks = {
        "redis": True,
    }
    return {"status": "ready", "checks": checks}


@cutter_router.get("/")
async def info():
    """General information about the cutting API."""
    return {
        "message": "Cutter API is running",
        "version": "1.0.0",
        "features": [
            "2D guillotine bin packing",
            "Kerf and trims",
            "Grain direction handling",
            "Redis caching",
        ],
    }


@cutter_router.get("/status")
async def status():
    """Operational status of the cutting processes."""
    return {
        "status": "operational",
        "active_processes": 0,
        "last_update": None,
    }


router.include_router(health_router)
router.include_router(cutter_router)
