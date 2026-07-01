from fastapi import APIRouter, Depends

from src.modules.optimizations.schemas import OptimizeRequest, OptimizeResponse
from src.modules.optimizations.service import OptimizationService, optimization_service
from src.modules.users.dependencies import require_permission
from src.shared.responses import ERROR_RESPONSES, DataResponse, ok

# Optimizer: "administrador" and "vendedor" (RESOURCE_ROLES["optimizer"]).
router = APIRouter(
    prefix="/optimize",
    tags=["optimize"],
    responses=ERROR_RESPONSES,
    dependencies=[Depends(require_permission("optimizer"))],
)


@router.post("/", response_model=DataResponse[OptimizeResponse])
def optimize(
    request: OptimizeRequest,
    svc: OptimizationService = Depends(optimization_service),
):
    """Runs a cutting optimization (cache-first) and returns the solution."""
    return ok(svc.optimize_response(request))
