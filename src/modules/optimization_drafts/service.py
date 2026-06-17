from typing import List, Optional, Tuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.branches.service import resolve_branch_for_create
from src.modules.optimization_drafts.model import OptimizationDraftModel
from src.modules.optimization_drafts.schemas import DraftCreate, DraftUpdate
from src.shared.branch_scope import BranchScopedMixin
from src.shared.crud import CRUDService
from src.shared.database import get_db


class OptimizationDraftService(
    BranchScopedMixin, CRUDService[OptimizationDraftModel, DraftCreate, DraftUpdate]
):
    """CRUD de borradores del optimizador, aislado por sucursal.

    Sin optimización, sin antiabuso, sin gate de teléfono ni cap: un borrador es
    trabajo en progreso editable. El ``BranchScopedMixin`` aísla el trabajo en curso
    entre sucursales (el admin —scope ``None``— ve todos).
    """

    model = OptimizationDraftModel

    def create_scoped(
        self, data: DraftCreate, branch_scope: Optional[int] = None
    ) -> OptimizationDraftModel:
        """Crea un borrador en la sucursal resuelta desde el scope (no del body)."""
        branch_id = resolve_branch_for_create(self.db, branch_scope, data.branch_id)
        draft = OptimizationDraftModel(
            **data.model_dump(exclude={"branch_id"}), branch_id=branch_id
        )
        return self._persist(draft)

    def list_scoped(
        self,
        branch_scope: Optional[int] = None,
        branch_filter: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[OptimizationDraftModel], int]:
        """Lista borradores aplicando el aislamiento por sucursal."""
        query = self._apply_branch_scope(
            self.db.query(OptimizationDraftModel), branch_scope, branch_filter
        )
        return self._paginate(query, limit, offset)

    def update_scoped(
        self, id: int, data: DraftUpdate, branch_scope: Optional[int] = None
    ) -> OptimizationDraftModel:
        """Actualiza un borrador verificando antes que sea de la sucursal del usuario."""
        self.get_scoped_or_404(id, branch_scope)
        return self.update(id, data)

    def delete_scoped(self, id: int, branch_scope: Optional[int] = None) -> None:
        """Elimina un borrador verificando antes que sea de la sucursal del usuario."""
        self.get_scoped_or_404(id, branch_scope)
        self.delete(id)


def optimization_draft_service(
    db: Session = Depends(get_db),
) -> OptimizationDraftService:
    """Provider de ``OptimizationDraftService`` para inyección en rutas."""
    return OptimizationDraftService(db)
