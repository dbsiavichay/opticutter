from fastapi import APIRouter

from .endpoints import cutter, health

# Router principal de la API
api_router = APIRouter()

# Incluir routers de endpoints
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(cutter.router, prefix="/cutter", tags=["cutter"])
