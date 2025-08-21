from fastapi import APIRouter

from config import config

router = APIRouter()


@router.get("/")
async def health_check():
    """Endpoint de verificación de salud detallado"""
    return {
        "status": "healthy",
        "environment": config.ENVIRONMENT,
        "version": "1.0.0",
        "debug": config.DEBUG,
        "timestamp": "2024-01-01T00:00:00Z",  # En producción usar datetime.utcnow()
    }


@router.get("/ready")
async def readiness_check():
    """Endpoint de verificación de preparación"""
    # Aquí puedes agregar verificaciones de dependencias
    # como base de datos, redis, etc.
    return {
        "status": "ready",
        "checks": {
            "database": "ok",  # Implementar verificación real
            "redis": "ok",  # Implementar verificación real
        },
    }
