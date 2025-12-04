from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.v1.schemas import OptimizeRequest, OptimizeResponse
from src.application.services import OptimizationService
from src.infrastructure.database import get_db

router = APIRouter(prefix="/optimize", tags=["optimize"])


@router.post("/", response_model=OptimizeResponse)
async def optimize(request: OptimizeRequest, db: Session = Depends(get_db)):
    service = OptimizationService(db)
    return service.execute(request)
