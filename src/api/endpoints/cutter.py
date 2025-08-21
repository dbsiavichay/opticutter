from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_cutter_info():
    """Obtiene información general del sistema Cutter"""
    return {
        "message": "Cutter API - Sistema de gestión para Maderable",
        "version": "1.0.0",
        "features": [
            "Gestión de inventario",
            "Control de cortes",
            "Reportes de producción",
        ],
    }


@router.get("/status")
async def get_cutter_status():
    """Obtiene el estado actual del sistema Cutter"""
    return {
        "status": "operational",
        "active_processes": 0,
        "last_update": "2024-01-01T00:00:00Z",
    }


# Ejemplo de endpoints para futuras funcionalidades
@router.get("/inventory")
async def get_inventory():
    """Obtiene el inventario actual (placeholder)"""
    # TODO: Implementar lógica de inventario
    return {"items": [], "total_count": 0, "message": "Endpoint en desarrollo"}


@router.get("/cuts")
async def get_cuts():
    """Obtiene la lista de cortes (placeholder)"""
    # TODO: Implementar lógica de cortes
    return {"cuts": [], "total_count": 0, "message": "Endpoint en desarrollo"}
