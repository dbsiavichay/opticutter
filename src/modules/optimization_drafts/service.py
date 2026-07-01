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
    """CRUD for optimizer drafts, branch-scoped.

    No optimization, no anti-abuse, no phone gate or cap: a draft is editable
    work in progress. ``BranchScopedMixin`` isolates work in progress between
    branches (the admin — scope ``None`` — sees all of them).
    """

    model = OptimizationDraftModel

    def create_scoped(
        self,
        data: DraftCreate,
        branch_scope: Optional[int] = None,
        default_branch_id: Optional[int] = None,
    ) -> OptimizationDraftModel:
        """Creates a draft in the branch resolved from the scope.

        The operator is pinned to their own; global roles (admin/seller) use
        ``data.branch_id`` or, if missing, ``default_branch_id`` (the creator's
        base branch — the seller defaults to one, the admin must provide
        ``branchId``).
        """
        branch_id = resolve_branch_for_create(
            self.db, branch_scope, data.branch_id, default_branch_id
        )
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
        """Lists drafts applying branch isolation."""
        query = self._apply_branch_scope(
            self.db.query(OptimizationDraftModel), branch_scope, branch_filter
        )
        return self._paginate(query, limit, offset)

    def update_scoped(
        self, id: int, data: DraftUpdate, branch_scope: Optional[int] = None
    ) -> OptimizationDraftModel:
        """Updates a draft after verifying it belongs to the user's branch."""
        self.get_scoped_or_404(id, branch_scope)
        return self.update(id, data)

    def delete_scoped(self, id: int, branch_scope: Optional[int] = None) -> None:
        """Deletes a draft after verifying it belongs to the user's branch."""
        self.get_scoped_or_404(id, branch_scope)
        self.delete(id)


def optimization_draft_service(
    db: Session = Depends(get_db),
) -> OptimizationDraftService:
    """Provider for ``OptimizationDraftService`` injection in routes."""
    return OptimizationDraftService(db)
