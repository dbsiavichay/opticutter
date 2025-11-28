from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db import get_db
from src.models.schemas import OptimizationImageResponse
from src.schemas.optimization import OptimizeRequest, OptimizeResponse
from src.services.optimization_service import OptimizationService
from src.services.visualization import visualization_service

router = APIRouter(prefix="/optimize", tags=["optimize"])


# @router.post("/", response_model=OptimizeResponse)
# async def optimize(
#     req: OptimizeRequest, db: Session = Depends(get_db)
# ) -> OptimizeResponse:
#     # return await optimize_cuts(req, db)
#     pieces = [
#         {
#             "id": c.label,
#             "width": c.width,
#             "height": c.length,
#             "quantity": c.quantity,
#             "material_id": c.board_code,
#         }
#         for c in req.cuts
#     ]
#     return OptimizationService.execute(db, pieces)


@router.post("/", response_model=OptimizeResponse)
async def optimize(request: OptimizeRequest, db: Session = Depends(get_db)):
    return OptimizationService.execute(request, db)


@router.get("/visualize/{request_hash}", response_model=OptimizationImageResponse)
async def visualize_optimization(request_hash: str):
    """
    Generate and return a visual representation of the optimization result.

    Args:
        request_hash: The hash ID of the cached optimization result

    Returns:
        OptimizationImageResponse with the image in base64 format
    """
    # Get the cached optimization result
    # cache_entry = await get_cached_by_hash(request_hash)
    cache_entry = None

    if not cache_entry:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró optimización con hash: {request_hash}",
        )

    optimization_result = cache_entry.result

    # Extract and estimate materials info from the boards layout
    materials = {}
    if (
        hasattr(optimization_result, "boards_layout")
        and optimization_result.boards_layout
    ):
        for board in optimization_result.boards_layout:
            if board.material not in materials:
                # Calculate board dimensions from cuts and waste pieces
                all_pieces = []

                # Add cuts
                for cut in board.cuts_placed:
                    all_pieces.append(
                        {
                            "x": cut.x,
                            "y": cut.y,
                            "width": cut.width,
                            "height": cut.height,
                        }
                    )

                # Add waste pieces
                for waste in board.waste_pieces:
                    all_pieces.append(
                        {
                            "x": waste.x,
                            "y": waste.y,
                            "width": waste.width,
                            "height": waste.height,
                        }
                    )

                # Calculate the maximum bounds
                if all_pieces:
                    max_x = max(piece["x"] + piece["width"] for piece in all_pieces)
                    max_y = max(piece["y"] + piece["height"] for piece in all_pieces)

                    # Estimate board dimensions with reasonable margins
                    # Common melamine board sizes
                    estimated_width = max_x
                    estimated_height = max_y

                    # Round up to common board sizes
                    common_widths = [1220, 1830, 2440, 3050]
                    common_heights = [610, 915, 1220, 1830, 2440]

                    estimated_width = next(
                        (w for w in common_widths if w >= estimated_width),
                        estimated_width + 100,
                    )
                    estimated_height = next(
                        (h for h in common_heights if h >= estimated_height),
                        estimated_height + 100,
                    )

                else:
                    # Default board size if no pieces found
                    estimated_width = 1220
                    estimated_height = 2440

                # Create material object
                materials[board.material] = type(
                    "Material",
                    (),
                    {
                        "code": board.material,
                        "width": estimated_width,
                        "height": estimated_height,
                        "price": 0.0,
                    },
                )()

    if not materials:
        raise HTTPException(
            status_code=400, detail="No se encontraron tableros para visualizar"
        )

    try:
        # Generate the visualization
        image_base64 = visualization_service.create_optimization_image(
            optimization_result.boards_layout, materials
        )

        return OptimizationImageResponse(
            image_base64=image_base64,
            request_hash=request_hash,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generando la visualización: {str(e)}"
        )
