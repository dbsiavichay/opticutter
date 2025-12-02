from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db import get_db
from src.schemas.optimization import OptimizeRequest, OptimizeResponse
from src.services.optimization_service import OptimizationService

router = APIRouter(prefix="/optimize", tags=["optimize"])


@router.post("/", response_model=OptimizeResponse)
async def optimize(request: OptimizeRequest, db: Session = Depends(get_db)):
    return OptimizationService.execute(request, db)
