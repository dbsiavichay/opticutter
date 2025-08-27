from fastapi import APIRouter

from src.api.cutter import router as cutter_router
from src.api.health import router as health_router
from src.api.optimize import router as optimize_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(cutter_router)
api_router.include_router(optimize_router)
