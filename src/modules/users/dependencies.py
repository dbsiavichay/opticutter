"""Dependencias de autenticación y autorización.

``get_current_user`` resuelve el usuario autenticado desde el JWT; ``require_role``
restringe por rol y ``require_permission`` por **área** (clave de la matriz
``RESOURCE_ROLES``). Los endpoints declaran intención con
``Depends(require_permission("orders:write"))`` y la matriz queda como única fuente
de verdad. ``require_role`` valida contra el rol **leído de la BD** (vía
``get_current_user``), así que un cambio de rol surte efecto al instante.
"""

from typing import Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.modules.users.enums import UserRole
from src.modules.users.model import UserModel
from src.modules.users.permissions import RESOURCE_ROLES
from src.modules.users.service import UserService, user_service
from src.shared.exceptions import AuthenticationError, AuthorizationError
from src.shared.security import decode_access_token

# auto_error=False: gestionamos nosotros el 401 vía AuthenticationError para que
# pase por la envoltura uniforme {errors, meta} en lugar del HTTPException de FastAPI.
bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    svc: UserService = Depends(user_service),
) -> UserModel:
    """Resuelve el usuario autenticado a partir del ``Authorization: Bearer <jwt>``."""
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Falta el token de autenticación")
    payload = decode_access_token(credentials.credentials)
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Token de sesión inválido") from exc
    user = svc.get(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Usuario no encontrado o inactivo")
    return user


def require_role(*roles: UserRole):
    """Factory de dependencia: exige que el usuario tenga uno de ``roles``.

    p. ej. ``Depends(require_role(UserRole.ADMIN))``. Prefiere ``require_permission``
    cuando exista una clave de área en ``RESOURCE_ROLES`` (centraliza la política).
    """
    allowed = {role.value for role in roles}

    def dependency(current_user: UserModel = Depends(get_current_user)) -> UserModel:
        if current_user.role not in allowed:
            raise AuthorizationError("No tienes permiso para realizar esta acción")
        return current_user

    return dependency


def require_permission(resource: str):
    """Dependencia de autorización por área, resuelta contra ``RESOURCE_ROLES``.

    ``Depends(require_permission("orders:write"))``. Una clave inexistente revienta
    con ``KeyError`` al **cargar el router** (no en runtime), atrapando typos en CI.
    """
    return require_role(*RESOURCE_ROLES[resource])


def get_branch_scope(
    current_user: UserModel = Depends(get_current_user),
) -> Optional[int]:
    """Resuelve el alcance por sucursal del usuario autenticado.

    ``None`` para los roles **globales** (administrador y vendedor): ven y operan todas
    las sucursales. El ``branch_id`` asignado para los roles de taller (operador y
    canteador), atados a la suya. Como ``get_current_user`` lee el usuario fresco de la
    BD en cada request, reasignar su sucursal surte efecto al instante. Un rol de taller
    sin sucursal asignada es un estado inválido (403). Nota: el vendedor conserva su
    ``branch_id`` como **sucursal base** (default al crear, ver
    ``resolve_branch_for_create``), aunque su lectura sea global.
    """
    if current_user.role in (UserRole.ADMIN.value, UserRole.SELLER.value):
        return None
    if current_user.branch_id is None:
        raise AuthorizationError(
            "Tu usuario no tiene una sucursal asignada; contacta al administrador."
        )
    return current_user.branch_id
