import base64

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from src.modules.optimizations.proforma import ProformaService
from src.modules.optimizations.schemas import OptimizeRequest, OptimizeResponse
from src.modules.optimizations.service import OptimizationService, optimization_service

router = APIRouter(prefix="/optimize", tags=["optimize"])


@router.post("/", response_model=OptimizeResponse)
def optimize(
    request: OptimizeRequest,
    svc: OptimizationService = Depends(optimization_service),
):
    """Ejecuta una optimización de cortes y devuelve la solución."""
    return svc.execute(request)


@router.get("/{optimization_id}/proforma")
def get_proforma(
    optimization_id: int,
    format: str = Query(
        default="pdf",
        description="Formato de salida: 'pdf' (archivo) o 'base64' (JSON)",
        pattern="^(pdf|base64)$",
    ),
    svc: OptimizationService = Depends(optimization_service),
):
    """Genera la proforma en PDF de una optimización."""
    optimization = svc.get_or_404(optimization_id)
    pdf_buffer = ProformaService.generate_proforma_pdf(optimization)

    if format.lower() == "base64":
        pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode("utf-8")
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
