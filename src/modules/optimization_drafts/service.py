from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.optimization_drafts.model import OptimizationDraftModel
from src.modules.optimization_drafts.schemas import DraftCreate, DraftUpdate
from src.shared.crud import CRUDService
from src.shared.database import get_db


class OptimizationDraftService(
    CRUDService[OptimizationDraftModel, DraftCreate, DraftUpdate]
):
    """CRUD de borradores del optimizador.

    Sin optimización, sin antiabuso, sin gate de teléfono ni cap: un borrador es
    trabajo en progreso editable. La base genérica cubre todas las operaciones.
    """

    model = OptimizationDraftModel


def optimization_draft_service(
    db: Session = Depends(get_db),
) -> OptimizationDraftService:
    """Provider de ``OptimizationDraftService`` para inyección en rutas."""
    return OptimizationDraftService(db)
