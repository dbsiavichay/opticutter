from .boards import router as boards_router
from .clients import router as clients_router
from .cutter import router as cutter_router
from .health import router as health_router
from .optimize import router as optimize_router

__all__ = [
    "boards_router",
    "clients_router",
    "cutter_router",
    "health_router",
    "optimize_router",
]
