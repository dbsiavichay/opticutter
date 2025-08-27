from fastapi import APIRouter

router = APIRouter(prefix="/cutter", tags=["cutter"])


@router.get("/")
async def info():
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


@router.get("/status")
async def status():
    return {
        "status": "operational",
        "active_processes": 0,
        "last_update": None,
    }
