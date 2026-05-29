import base64

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.v1.schemas import OptimizeRequest, OptimizeResponse
from src.application.services import OptimizationService
from src.application.services.proforma_service import ProformaService
from src.infrastructure.database import get_db
from src.infrastructure.database.repositories import OptimizationRepository

router = APIRouter(prefix="/optimize", tags=["optimize"])


@router.post("/", response_model=OptimizeResponse)
async def optimize(request: OptimizeRequest, db: Session = Depends(get_db)):
    service = OptimizationService(db)
    return service.execute(request)


@router.get("/{optimization_id}/proforma")
async def get_proforma(
    optimization_id: int,
    format: str = Query(
        default="pdf",
        description="Formato de respuesta: 'pdf' para archivo PDF o 'base64' para JSON con contenido base64",
        pattern="^(pdf|base64)$",
    ),
    db: Session = Depends(get_db),
):
    repository = OptimizationRepository(db)
    optimization = repository.get(optimization_id)

    if not optimization:
        raise HTTPException(
            status_code=404,
            detail=f"Optimización con ID {optimization_id} no encontrada",
        )

    pdf_buffer = ProformaService.generate_proforma_pdf(optimization)

    if format.lower() == "base64":
        pdf_bytes = pdf_buffer.getvalue()
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

        return {
            "optimizationId": optimization_id,
            "format": "base64",
            "content": pdf_base64,
            "filename": f"proforma_{optimization_id}.pdf",
            "mimeType": "application/pdf",
        }

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=proforma_{optimization_id}.pdf"
        },
    )
