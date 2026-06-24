from typing import List, Optional, Tuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.branches.model import BranchModel
from src.modules.users.enums import UserRole
from src.modules.users.model import UserModel
from src.modules.users.schemas import ProfileUpdate, UserCreate, UserUpdate
from src.shared.crud import CRUDService
from src.shared.database import get_db
from src.shared.exceptions import (
    AuthenticationError,
    EntityNotFoundError,
    ValidationError,
)
from src.shared.security import hash_password, verify_password


class UserService(CRUDService[UserModel, UserCreate, UserUpdate]):
    """CRUD de usuarios + autenticación. Hashea la contraseña al crear/actualizar."""

    model = UserModel
    conflict_messages = {"email": "El email ya está registrado"}

    def _normalize_branch(
        self, role_value: str, branch_id: Optional[int]
    ) -> Optional[int]:
        """Concilia rol y sucursal: admin global (None); staff exige una válida.

        El administrador ve y opera todas las sucursales, así que su ``branch_id``
        se fuerza a ``None``. Vendedor/operador/canteador deben tener una sucursal
        existente.
        """
        if role_value == UserRole.ADMIN.value:
            return None
        if branch_id is None:
            raise ValidationError(
                "El vendedor, operador o canteador requiere una sucursal "
                "asignada (branchId).",
                field="branchId",
            )
        if self.db.get(BranchModel, branch_id) is None:
            raise EntityNotFoundError("Branch", branch_id)
        return branch_id

    def create(self, data: UserCreate) -> UserModel:
        """Crea un usuario hasheando la contraseña; nunca la persiste en claro."""
        payload = data.model_dump(exclude={"password", "role", "branch_id"})
        user = UserModel(
            **payload,
            role=data.role.value,
            branch_id=self._normalize_branch(data.role.value, data.branch_id),
            hashed_password=hash_password(data.password),
        )
        return self._persist(user)

    def update(self, id: int, data: UserUpdate) -> UserModel:
        """Actualiza un usuario; si llega ``password`` la rehashea."""
        obj = self.get_or_404(id)
        changes = data.model_dump(exclude_unset=True)
        if "password" in changes:
            obj.hashed_password = hash_password(changes.pop("password"))
        if changes.get("role") is not None:
            changes["role"] = UserRole(changes["role"]).value
        for field, value in changes.items():
            setattr(obj, field, value)
        # Concilia rol↔sucursal sobre el estado resultante (cubre cambios de rol y/o
        # de sucursal, y normaliza al admin a sucursal nula).
        obj.branch_id = self._normalize_branch(obj.role, obj.branch_id)
        return self._persist(obj)

    def update_profile(self, user: UserModel, data: ProfileUpdate) -> UserModel:
        """Autoservicio: el propio usuario edita su perfil (solo ``full_name``).

        No toca ``role``/``is_active``/``email``: eso es gestión y vive en el CRUD
        solo-admin. Semántica PATCH: solo aplica los campos enviados.
        """
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        return self._persist(user)

    def change_password(self, user: UserModel, current: str, new: str) -> None:
        """Autoservicio: cambia la propia contraseña verificando la actual.

        Lanza ``AuthenticationError`` (401) si la contraseña actual no coincide.
        El caller revoca los refresh tokens para forzar re-login en otros equipos.
        """
        if not verify_password(current, user.hashed_password):
            raise AuthenticationError("La contraseña actual es incorrecta")
        user.hashed_password = hash_password(new)
        self._persist(user)

    def get_by_email(self, email: str) -> Optional[UserModel]:
        """Obtiene un usuario por email (identificador de login)."""
        return self.db.query(UserModel).filter(UserModel.email == email).first()

    def authenticate(self, email: str, password: str) -> Optional[UserModel]:
        """Valida credenciales; devuelve el usuario si están activas y coinciden."""
        user = self.get_by_email(email)
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def search_paginated(
        self, search: str, limit: int = 20, offset: int = 0
    ) -> Tuple[List[UserModel], int]:
        """Busca usuarios por email o nombre; ``(items, total)``."""
        pattern = f"%{search}%"
        query = self.db.query(UserModel).filter(
            UserModel.email.ilike(pattern) | UserModel.full_name.ilike(pattern)
        )
        return self._paginate(query, limit, offset)


def user_service(db: Session = Depends(get_db)) -> UserService:
    """Provider de ``UserService`` para inyección en rutas."""
    return UserService(db)
