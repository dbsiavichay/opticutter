from typing import List, Optional, Tuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.branches.model import BranchModel
from src.modules.branches.schemas import BranchCreate, BranchUpdate
from src.shared.crud import CRUDService
from src.shared.database import get_db
from src.shared.exceptions import EntityNotFoundError, ValidationError


def branch_letterhead(db: Session, branch_id: Optional[int]) -> Optional[dict]:
    """Membrete de una sucursal para la proforma: ``{"name", "address"}`` o ``None``.

    Acota el listado de sucursales del membrete a la sucursal dueña del documento.
    """
    if branch_id is None:
        return None
    branch = db.get(BranchModel, branch_id)
    if branch is None:
        return None
    return {"name": branch.name, "address": branch.address or ""}


def resolve_branch_for_create(
    db: Session, branch_scope: Optional[int], requested_branch_id: Optional[int]
) -> int:
    """Resuelve y valida la sucursal destino de un alta (orden/pre-orden/borrador).

    - staff (``branch_scope`` no None): siempre su propia sucursal (ignora lo pedido
      en el body, para que no pueda crear en otra sucursal).
    - admin (``branch_scope`` None): exige ``requested_branch_id`` explícito.

    Verifica que la sucursal exista y esté activa.
    """
    branch_id = branch_scope if branch_scope is not None else requested_branch_id
    if branch_id is None:
        raise ValidationError(
            "Debes indicar la sucursal de destino (branchId).", field="branchId"
        )
    branch = db.get(BranchModel, branch_id)
    if branch is None:
        raise EntityNotFoundError("Branch", branch_id)
    if not branch.is_active:
        raise ValidationError("La sucursal indicada está inactiva.", field="branchId")
    return branch_id


class BranchService(CRUDService[BranchModel, BranchCreate, BranchUpdate]):
    """CRUD de sucursales + búsquedas específicas."""

    model = BranchModel
    conflict_messages = {"code": "El código de sucursal ya existe"}

    def get_by_code(self, code: str) -> Optional[BranchModel]:
        """Obtiene una sucursal por su código."""
        return self.db.query(BranchModel).filter(BranchModel.code == code).first()

    def search_paginated(
        self, search: str, limit: int = 20, offset: int = 0
    ) -> Tuple[List[BranchModel], int]:
        """Busca sucursales por código o nombre; ``(items, total)``."""
        pattern = f"%{search}%"
        query = self.db.query(BranchModel).filter(
            BranchModel.code.ilike(pattern) | BranchModel.name.ilike(pattern)
        )
        return self._paginate(query, limit, offset)


def branch_service(db: Session = Depends(get_db)) -> BranchService:
    """Provider de ``BranchService`` para inyección en rutas."""
    return BranchService(db)
