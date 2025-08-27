from fastapi import APIRouter, Query

from src.models.schemas import (
    OptimizationsListResponse,
    OptimizeRequest,
    OptimizeResponse,
    RetrieveOptimizationResponse,
)
from src.services.optimization import (
    get_cached_by_hash,
    list_recent_optimizations,
    optimize_with_cache,
)

router = APIRouter(prefix="/optimize", tags=["optimize"])


@router.post("/", response_model=OptimizeResponse)
async def optimize(req: OptimizeRequest) -> OptimizeResponse:
    return await optimize_with_cache(req.model_dump())


@router.get("/by-hash/{request_hash}", response_model=RetrieveOptimizationResponse)
async def get_by_hash(request_hash: str):
    item = await get_cached_by_hash(request_hash)
    return RetrieveOptimizationResponse(cached=item is not None, item=item)


@router.get("/recent", response_model=OptimizationsListResponse)
async def recent(offset: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=50)):
    items = await list_recent_optimizations(offset=offset, limit=limit)
    return OptimizationsListResponse(total=len(items), items=items)
