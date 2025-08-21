from typing import List, Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Esquema para respuesta de health check"""

    status: str
    environment: str
    version: str
    debug: bool
    timestamp: str


class ReadinessResponse(BaseModel):
    """Esquema para respuesta de readiness check"""

    status: str
    checks: dict


class ErrorResponse(BaseModel):
    """Esquema para respuestas de error"""

    error: bool
    message: str
    status_code: int
    details: Optional[dict] = None


class CutterInfoResponse(BaseModel):
    """Esquema para información del sistema Cutter"""

    message: str
    version: str
    features: List[str]


class CutterStatusResponse(BaseModel):
    """Esquema para estado del sistema Cutter"""

    status: str
    active_processes: int
    last_update: str
