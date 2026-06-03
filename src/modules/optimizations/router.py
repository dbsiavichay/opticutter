from fastapi import APIRouter, Depends, Query

from src.modules.optimizations.proforma import ProformaService, pdf_response
from src.modules.optimizations.schemas import OptimizeRequest, OptimizeResponse
from src.modules.optimizations.service import OptimizationService, optimization_service

router = APIRouter(prefix="/optimize", tags=["optimize"])


@router.post("/", response_model=OptimizeResponse)
def optimize(
    request: OptimizeRequest,
    svc: OptimizationService = Depends(optimization_service),
):
    """Ejecuta una optimización de cortes (cache-first) y devuelve la solución."""
    return svc.optimize_response(request)


@router.get("/{optimization_hash}/proforma")
def get_proforma(
    optimization_hash: str,
    client_id: int = Query(
        ..., alias="clientId", description="Cliente para el encabezado de la proforma"
    ),
    format: str = Query(
        default="pdf",
        description="Formato de salida: 'pdf' (archivo) o 'base64' (JSON)",
        pattern="^(pdf|base64)$",
    ),
    svc: OptimizationService = Depends(optimization_service),
):
    """Genera la proforma PDF de una optimización cacheada (por hash)."""
    carrier = svc.build_carrier_from_hash(optimization_hash, client_id)
    pdf_buffer = ProformaService.generate_proforma_pdf(carrier)
    return pdf_response(pdf_buffer, f"proforma_{optimization_hash[:8]}.pdf", format)
